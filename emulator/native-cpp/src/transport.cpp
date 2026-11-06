#include "virtualcar/transport.hpp"

#include <algorithm>
#include <limits>

namespace virtualcar::transport {
namespace {
constexpr std::uint32_t max_standard_id = 0x7ffU;
constexpr std::uint32_t max_extended_id = 0x1fffffffU;
constexpr std::uint8_t pci_flow = 0x30U;

bool valid_bitrate(std::uint32_t value) noexcept
{
    return value == 125000U || value == 250000U ||
        value == 500000U || value == 1000000U;
}

bool add_safe(std::uint64_t left, std::uint64_t right,
              std::uint64_t& result) noexcept
{
    if (left > (std::numeric_limits<std::uint64_t>::max)() - right)
        return false;
    result = left + right;
    return true;
}
} // namespace

bool Engine::valid_id(std::uint32_t id, bool extended) const noexcept
{
    return id <= (extended ? max_extended_id : max_standard_id);
}

bool Engine::configure(Route route) noexcept
{
    if (!valid_bitrate(route.bitrate) ||
        !valid_id(route.request_id, route.extended) ||
        !valid_id(route.response_id, route.extended) ||
        route.request_id == route.response_id)
        return false;
    reset();
    route_ = route;
    configured_ = true;
    return true;
}

void Engine::reset() noexcept
{
    head_ = 0;
    count_ = 0;
    filters_count_ = 0;
    flow_enabled_ = false;
    invalidate_pending();
    // A wrapped generation must never accidentally validate an old frame.
    // For the practically unreachable max case, disable the route.
    if (generation_ == (std::numeric_limits<std::uint64_t>::max)()) {
        configured_ = false;
        generation_ = 1;
    } else {
        ++generation_;
    }
}

Result Engine::add_filter(RuleKind action, std::uint32_t mask,
                          std::uint32_t pattern) noexcept
{
    if (!configured_) return Result::not_ready;
    const std::uint32_t max_id = route_.extended ?
        max_extended_id : max_standard_id;
    if (mask > max_id || pattern > max_id || (pattern & ~mask) != 0U)
        return Result::invalid;
    if (filters_count_ >= filter_capacity) return Result::queue_full;
    for (std::size_t i = 0; i < filters_count_; ++i) {
        const Filter& old = filters_[i];
        if (old.action == action && old.mask == mask &&
            old.pattern == pattern)
            return Result::invalid;
    }
    filters_[filters_count_++] = Filter{action, mask, pattern};
    return Result::ok;
}

Result Engine::enable_flow_control(std::uint32_t response_id,
                                    std::uint32_t request_id) noexcept
{
    if (!configured_) return Result::not_ready;
    if (response_id != route_.response_id ||
        request_id != route_.request_id)
        return Result::wrong_route;
    if (flow_enabled_) return Result::invalid;
    // The flow filter is bound to this exact ECU pair, not a wildcard ID.
    flow_enabled_ = true;
    return Result::ok;
}

bool Engine::allowed(std::uint32_t id) const noexcept
{
    if (!configured_ || id != route_.response_id) return false;
    bool pass = false;
    for (std::size_t i = 0; i < filters_count_; ++i) {
        const Filter& filter = filters_[i];
        if ((id & filter.mask) != filter.pattern) continue;
        if (filter.action == RuleKind::block) return false;
        pass = true;
    }
    return pass;
}

Result Engine::enqueue(Frame frame) noexcept
{
    if (count_ >= fifo_capacity) return Result::queue_full;
    frame.generation = generation_;
    fifo_[(head_ + count_) % fifo_capacity] = frame;
    ++count_;
    return Result::ok;
}

Result Engine::ingest_synthetic(
    std::uint32_t can_id, bool extended,
    std::span<const std::uint8_t> bytes, std::uint64_t now_us) noexcept
{
    if (!configured_) return Result::not_ready;
    if (!valid_id(can_id, extended) || extended != route_.extended ||
        bytes.empty() || bytes.size() > 8)
        return Result::invalid;
    if (!allowed(can_id)) return Result::blocked;
    Frame frame{};
    frame.can_id = can_id;
    frame.extended = extended;
    frame.length = static_cast<std::uint8_t>(bytes.size());
    frame.ready_us = now_us;
    std::copy(bytes.begin(), bytes.end(), frame.data.begin());
    return enqueue(frame);
}

Result Engine::begin_readonly_reply(
    std::span<const std::uint8_t> payload, std::uint64_t now_us) noexcept
{
    if (!configured_) return Result::not_ready;
    if (payload.empty() || payload.size() > payload_capacity)
        return Result::invalid;
    if (pending_.active) return Result::busy;
    if (!allowed(route_.response_id)) return Result::blocked;
    if (count_ >= fifo_capacity) return Result::queue_full;
    if (payload.size() > 7 && !flow_enabled_) return Result::not_ready;

    Frame first{};
    first.can_id = route_.response_id;
    first.extended = route_.extended;
    first.length = 8;
    first.ready_us = now_us;
    if (payload.size() <= 7) {
        first.data[0] = static_cast<std::uint8_t>(payload.size());
        std::copy(payload.begin(), payload.end(), first.data.begin() + 1);
        return enqueue(first);
    }

    std::uint64_t deadline{};
    if (!add_safe(now_us, fc_deadline_us, deadline)) return Result::invalid;
    first.data[0] = static_cast<std::uint8_t>(
        0x10U | ((payload.size() >> 8U) & 0x0fU));
    first.data[1] = static_cast<std::uint8_t>(payload.size() & 0xffU);
    std::copy_n(payload.begin(), 6, first.data.begin() + 2);
    const Result result = enqueue(first);
    if (result != Result::ok) return result;

    invalidate_pending();
    pending_.active = true;
    pending_.total = payload.size();
    pending_.offset = 6;
    pending_.next_seq = 1;
    pending_.fc_due_us = deadline;
    std::copy(payload.begin(), payload.end(), pending_.bytes.begin());
    return Result::ok;
}

Result Engine::receive_flow_control(
    std::uint32_t from_can_id, bool extended,
    std::span<const std::uint8_t> bytes, std::uint64_t now_us) noexcept
{
    if (!configured_) return Result::not_ready;
    if (!pending_.active) return Result::no_pending;
    if (from_can_id != route_.request_id || extended != route_.extended)
        return Result::wrong_route;
    if (pending_.fc_due_us && !pending_.cts &&
        now_us > pending_.fc_due_us) {
        invalidate_pending();
        return Result::timed_out;
    }
    if (bytes.size() < 3 || bytes.size() > 8 ||
        (bytes[0] & 0xf0U) != pci_flow)
        return Result::invalid;

    const std::uint8_t flow = bytes[0] & 0x0fU;
    if (flow == 2U) {
        invalidate_pending();
        return Result::aborted;
    }
    if (flow == 1U) {
        if (++pending_.wait_frames > 3U) {
            invalidate_pending();
            return Result::aborted;
        }
        pending_.cts = false;
        pending_.credit = 0;
        return Result::ok;
    }
    if (flow != 0U) return Result::invalid;

    const std::uint8_t encoded_stmin = bytes[2];
    std::uint32_t stmin_us{};
    if (encoded_stmin <= 0x7fU) {
        stmin_us = static_cast<std::uint32_t>(encoded_stmin) * 1000U;
    } else if (encoded_stmin >= 0xf1U && encoded_stmin <= 0xf9U) {
        stmin_us = static_cast<std::uint32_t>(encoded_stmin - 0xf0U) * 100U;
    } else {
        return Result::invalid; // Reserved STmin must not grant credit.
    }
    pending_.cts = true;
    pending_.block_size = bytes[1];
    pending_.credit = bytes[1];
    pending_.stmin_us = stmin_us;
    pending_.next_due_us = now_us;
    pending_.wait_frames = 0;
    return Result::ok;
}

Result Engine::pump(std::uint64_t now_us) noexcept
{
    if (!configured_) return Result::not_ready;
    if (!pending_.active) return Result::no_pending;
    if (!pending_.cts) {
        if (now_us > pending_.fc_due_us) {
            invalidate_pending();
            return Result::timed_out;
        }
        return Result::not_ready;
    }

    while (pending_.active && pending_.cts &&
           pending_.next_due_us <= now_us) {
        if (count_ >= fifo_capacity) return Result::queue_full;

        Frame frame{};
        frame.can_id = route_.response_id;
        frame.extended = route_.extended;
        frame.ready_us = pending_.next_due_us;
        frame.length = 8;
        frame.data[0] = static_cast<std::uint8_t>(
            0x20U | (pending_.next_seq & 0x0fU));
        const std::size_t remaining = pending_.total - pending_.offset;
        const std::size_t transfer = (std::min)(remaining, std::size_t{7});
        std::copy_n(pending_.bytes.begin() + pending_.offset, transfer,
                    frame.data.begin() + 1);

        std::uint64_t next_due{};
        if (!add_safe(pending_.next_due_us, pending_.stmin_us, next_due))
            return Result::invalid;
        if (enqueue(frame) != Result::ok) return Result::queue_full;

        pending_.offset += transfer;
        pending_.next_seq = static_cast<std::uint8_t>(
            (pending_.next_seq + 1U) & 0x0fU);
        pending_.next_due_us = next_due;
        if (pending_.offset >= pending_.total) {
            invalidate_pending();
            return Result::ok;
        }
        if (pending_.block_size != 0U) {
            if (--pending_.credit == 0U) {
                std::uint64_t deadline{};
                if (!add_safe(now_us, fc_deadline_us, deadline)) {
                    invalidate_pending();
                    return Result::timed_out;
                }
                pending_.fc_due_us = deadline;
                pending_.cts = false;
                return Result::ok;
            }
        }
    }
    return Result::ok;
}

bool Engine::pop(Frame& frame) noexcept
{
    if (count_ == 0) return false;
    frame = fifo_[head_];
    head_ = (head_ + 1) % fifo_capacity;
    --count_;
    // Reset clears the FIFO; this is an additional generation fence.
    if (frame.generation != generation_) return false;
    return true;
}

} // namespace virtualcar::transport
