#include "virtualcar/isotp_rx.hpp"

#include <algorithm>
#include <limits>

namespace virtualcar::transport {
namespace {
constexpr std::uint32_t max_standard_id = 0x7ffU;
constexpr std::uint32_t max_extended_id = 0x1fffffffU;
constexpr std::uint32_t exact_mask = 0xffffffffU;

bool valid_bitrate(std::uint32_t bitrate) noexcept
{
    return bitrate == 125000U || bitrate == 250000U ||
           bitrate == 500000U || bitrate == 1000000U;
}
bool valid_can_id(std::uint32_t id, bool extended) noexcept
{
    return id <= (extended ? max_extended_id : max_standard_id);
}
} // namespace

bool Iso15765Rx::valid_route(const Route& route) const noexcept
{
    if (!valid_bitrate(route.bitrate) ||
        !valid_can_id(route.request_id, route.extended) ||
        !valid_can_id(route.response_id, route.extended) ||
        route.request_id == route.response_id)
        return false;
    if (route_count_ > 0 && routes_[0].bitrate != route.bitrate)
        return false;

    for (std::size_t i = 0; i < route_count_; ++i) {
        const Route& existing = routes_[i];
        // Deliberately prohibit duplicates and cross-role collisions
        // even when one ID is standard and the other extended.
        if (route.request_id == existing.request_id ||
            route.request_id == existing.response_id ||
            route.response_id == existing.request_id ||
            route.response_id == existing.response_id)
            return false;
    }

    // Do not let a later route inherit an earlier broad RX filter.
    for (std::size_t i = 0; i < filter_count_; ++i) {
        const Filter& existing = filters_[i];
        if ((route.response_id & existing.mask) == existing.pattern)
            return false;
    }
    return true;
}

Result Iso15765Rx::add_route(Route route) noexcept
{
    if (!valid_route(route)) return Result::invalid;
    if (route_count_ >= route_capacity) return Result::queue_full;
    routes_[route_count_++] = route;
    return Result::ok;
}

Result Iso15765Rx::bind_flow_filter(
    std::size_t route_index,
    std::uint32_t mask,
    std::uint32_t pattern,
    std::uint32_t flow_request_id) noexcept
{
    if (route_index >= route_count_) return Result::wrong_route;
    if (filter_count_ >= filter_capacity) return Result::queue_full;
    const Route& route = routes_[route_index];
    if (pattern > (route.extended ? max_extended_id : max_standard_id) ||
        (pattern & ~mask) != 0U ||
        (route.response_id & mask) != pattern ||
        flow_request_id != route.request_id)
        return Result::invalid;

    for (std::size_t i = 0; i < filter_count_; ++i) {
        const Filter& old = filters_[i];
        // Exactly the legacy strict-mask ambiguity predicate:
        // filters whose masked response IDs overlap are not unique.
        if (((old.pattern ^ pattern) & old.mask & mask) == 0U)
            return Result::invalid;
    }

    // All routes must remain isolated, including one added before
    // this broader mask was installed.
    for (std::size_t i = 0; i < route_count_; ++i) {
        if (i == route_index) continue;
        if ((routes_[i].response_id & mask) == pattern)
            return Result::invalid;
    }

    filters_[filter_count_++] = Filter{route_index, mask, pattern, flow_request_id};
    return Result::ok;
}

bool Iso15765Rx::filter_allows(std::size_t index,
                               bool segmented) const noexcept
{
    if (index >= route_count_) return false;
    const Route& route = routes_[index];
    for (std::size_t i = 0; i < filter_count_; ++i) {
        const Filter& filter = filters_[i];
        if (filter.owner != index ||
            filter.flow_request_id != route.request_id ||
            (route.response_id & filter.mask) != filter.pattern)
            continue;
        // Broad ISO15765 Flow Control masks must NEVER grant a
        // segmented answer from an ambiguous physical CTS origin.
        if (segmented && filter.mask != exact_mask) continue;
        return true;
    }
    return false;
}

j2534::PASSTHRU_MSG Iso15765Rx::make_message(
    const Route& route,
    std::span<const std::uint8_t> payload,
    bool start,
    std::uint64_t time_us) noexcept
{
    j2534::PASSTHRU_MSG msg{};
    msg.ProtocolID = protocol_id;
    msg.RxStatus = (route.extended ? can_29bit_id : 0U) |
        (start ? start_of_message : 0U);
    msg.TxFlags = 0U;
    msg.Timestamp = static_cast<std::uint32_t>(time_us);
    msg.DataSize = static_cast<j2534::DWORD>(payload.size() + 4U);
    msg.ExtraDataIndex = start ? 0U : msg.DataSize;
    msg.Data[0] = static_cast<std::uint8_t>(route.response_id >> 24);
    msg.Data[1] = static_cast<std::uint8_t>(route.response_id >> 16);
    msg.Data[2] = static_cast<std::uint8_t>(route.response_id >> 8);
    msg.Data[3] = static_cast<std::uint8_t>(route.response_id);
    if (!payload.empty())
        std::copy(payload.begin(), payload.end(), msg.Data + 4);
    return msg;
}

Result Iso15765Rx::emit_verified_readonly_reply(
    std::size_t route_index,
    std::span<const std::uint8_t> synthetic_payload,
    bool include_start,
    std::uint64_t timestamp_us) noexcept
{
    if (route_index >= route_count_) return Result::wrong_route;
    // Only the approved read-only UDS response service can be staged.
    // This is a secondary guard, not a replacement for M2 SHA validation.
    if (synthetic_payload.size() < 3 ||
        synthetic_payload.size() > payload_capacity ||
        synthetic_payload[0] != 0x62U)
        return Result::invalid;

    const bool segmented = synthetic_payload.size() > 7U;
    if (!filter_allows(route_index, segmented))
        return Result::blocked;
    const std::size_t needed = (segmented && include_start) ? 2U : 1U;

    // One logical ISO15765 response: no half START_OF_MESSAGE admission.
    if (count_ > fifo_capacity - needed) {
        if (dropped_ < (std::numeric_limits<std::uint64_t>::max)())
            ++dropped_;
        return Result::queue_full;
    }

    const Route& route = routes_[route_index];
    const std::size_t tail = (head_ + count_) % fifo_capacity;
    if (needed == 2U) {
        fifo_[tail] = Entry{make_message(route, {}, true, timestamp_us),
                            route_index, generation_};
        fifo_[(tail + 1U) % fifo_capacity] =
            Entry{make_message(route, synthetic_payload, false, timestamp_us),
                  route_index, generation_};
    } else {
        fifo_[tail] = Entry{make_message(route, synthetic_payload, false,
                                         timestamp_us), route_index, generation_};
    }
    count_ += needed;
    return Result::ok;
}

bool Iso15765Rx::pop(j2534::PASSTHRU_MSG& message,
                     std::size_t& route_index) noexcept
{
    if (count_ == 0) return false;
    const Entry& entry = fifo_[head_];
    if (entry.generation != generation_) {
        // This should never happen because reset clears the queue.
        reset();
        return false;
    }
    message = entry.msg;
    route_index = entry.owner;
    head_ = (head_ + 1U) % fifo_capacity;
    --count_;
    return true;
}

void Iso15765Rx::reset() noexcept
{
    route_count_ = 0;
    filter_count_ = 0;
    head_ = 0;
    count_ = 0;
    dropped_ = 0;
    if (generation_ == (std::numeric_limits<std::uint64_t>::max)())
        generation_ = 1;
    else
        ++generation_;
}

} // namespace virtualcar::transport
