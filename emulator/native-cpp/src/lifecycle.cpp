#include "virtualcar/lifecycle.hpp"

#include <algorithm>
#include <limits>

namespace virtualcar::lifecycle {
namespace {
[[nodiscard]] bool valid_key(SessionKey key) noexcept
{
    return key.id != 0 && key.generation != 0 &&
           key.server_pid != 0 && key.server_creation_time_100ns != 0;
}

[[nodiscard]] bool same_key(SessionKey left, SessionKey right) noexcept
{
    return left.id == right.id && left.generation == right.generation &&
           left.server_pid == right.server_pid &&
           left.server_creation_time_100ns == right.server_creation_time_100ns;
}

[[nodiscard]] bool valid_kind(ChannelKind kind) noexcept
{
    return kind == ChannelKind::can || kind == ChannelKind::iso15765;
}
} // namespace

BoundedSession::BoundedSession(std::uint64_t lease_ms) noexcept
    : lease_ms_(lease_ms)
{
}

void BoundedSession::invalidate_locked() noexcept
{
    key_ = {};
    last_now_ms_ = 0;
    expires_at_ms_ = 0;
    slots_.fill({});
    active_ = false;
    // Preserve next_channel_id_. No channel ID is recycled during process life.
}

bool BoundedSession::can_extend(std::uint64_t now_ms) const noexcept
{
    return lease_ms_ >= minimum_lease_ms &&
           lease_ms_ <= maximum_lease_ms &&
           now_ms <= std::numeric_limits<std::uint64_t>::max() - lease_ms_;
}

Result BoundedSession::begin(SessionKey key, bool approved_synthetic,
                             std::uint64_t now_ms)
{
    const std::lock_guard<std::mutex> lock(mutex_);
    if (active_ && now_ms < last_now_ms_) {
        invalidate_locked();
        return Result::clock_regressed;
    }
    if (active_ && same_key(key_, key)) {
        invalidate_locked();
        return Result::invalid; // Duplicate HELLO is not a fresh generation.
    }
    // Every new attempt invalidates any prior session and its channel slots.
    invalidate_locked();
    if (!approved_synthetic || !valid_key(key) || !can_extend(now_ms))
        return Result::invalid;
    key_ = key;
    last_now_ms_ = now_ms;
    expires_at_ms_ = now_ms + lease_ms_;
    active_ = true;
    return Result::ok;
}

Result BoundedSession::validate_locked(SessionKey key, std::uint64_t now_ms)
{
    if (!active_)
        return Result::not_authenticated;
    if (!valid_key(key) || !same_key(key, key_)) {
        invalidate_locked();
        return Result::not_authenticated;
    }
    if (now_ms < last_now_ms_) {
        invalidate_locked();
        return Result::clock_regressed;
    }
    if (now_ms >= expires_at_ms_) {
        invalidate_locked();
        return Result::expired;
    }
    last_now_ms_ = now_ms;
    return Result::ok;
}

Result BoundedSession::validate(SessionKey key, std::uint64_t now_ms)
{
    const std::lock_guard<std::mutex> lock(mutex_);
    return validate_locked(key, now_ms);
}

Result BoundedSession::heartbeat(SessionKey key, std::uint64_t now_ms)
{
    const std::lock_guard<std::mutex> lock(mutex_);
    const auto status = validate_locked(key, now_ms);
    if (status != Result::ok)
        return status;
    if (!can_extend(now_ms)) {
        invalidate_locked();
        return Result::invalid;
    }
    expires_at_ms_ = now_ms + lease_ms_;
    return Result::ok;
}

Result BoundedSession::reserve_channel(SessionKey key, ChannelKind kind,
                                       std::uint64_t now_ms,
                                       std::uint32_t& channel_id)
{
    channel_id = 0;
    const std::lock_guard<std::mutex> lock(mutex_);
    const auto status = validate_locked(key, now_ms);
    if (status != Result::ok)
        return status;
    if (!valid_kind(kind))
        return Result::invalid;
    const auto free = std::find_if(slots_.begin(), slots_.end(),
                                   [](const Slot& slot) { return slot.id == 0; });
    if (free == slots_.end())
        return Result::capacity;
    if (next_channel_id_ == std::numeric_limits<std::uint32_t>::max())
        return Result::exhausted; // Refuse wrap or reuse.
    free->id = next_channel_id_++;
    free->kind = kind;
    channel_id = free->id;
    return Result::ok;
}

Result BoundedSession::close_channel(SessionKey key,
                                     std::uint32_t channel_id,
                                     std::uint64_t now_ms)
{
    const std::lock_guard<std::mutex> lock(mutex_);
    const auto status = validate_locked(key, now_ms);
    if (status != Result::ok)
        return status;
    if (channel_id == 0)
        return Result::invalid;
    const auto slot = std::find_if(slots_.begin(), slots_.end(),
                                  [channel_id](const Slot& candidate) {
                                      return candidate.id == channel_id;
                                  });
    if (slot == slots_.end())
        return Result::invalid;
    *slot = {};
    return Result::ok;
}

void BoundedSession::reset()
{
    const std::lock_guard<std::mutex> lock(mutex_);
    invalidate_locked();
}

Snapshot BoundedSession::snapshot() const
{
    const std::lock_guard<std::mutex> lock(mutex_);
    return {active_, static_cast<std::size_t>(std::count_if(
                slots_.begin(), slots_.end(),
                [](const Slot& slot) { return slot.id != 0; })),
            expires_at_ms_};
}

} // namespace virtualcar::lifecycle
