#pragma once

// M5C-1: fail-closed synthetic LAB lifecycle bookkeeping only.
// No J2534/ECU/CAN routing is exposed or enabled by this API.

#include <array>
#include <cstddef>
#include <cstdint>
#include <mutex>

namespace virtualcar::lifecycle {

struct SessionKey final {
    std::uint64_t id{};
    std::uint64_t generation{};
};

enum class Result : std::uint8_t {
    ok,
    invalid,
    not_authenticated,
    expired,
    clock_regressed,
    capacity,
    exhausted
};

enum class ChannelKind : std::uint8_t {
    can = 1,
    iso15765 = 2
};

struct Snapshot final {
    bool active{};
    std::size_t channels{};
    std::uint64_t expires_at_ms{};
};

// Caller MUST verify the M5A/M5B host, scenario and session token before
// calling begin(). The 'approved_synthetic' parameter is NOT an authentication
// mechanism. All times must come from one monotonic millisecond clock.
class BoundedSession final {
public:
    static constexpr std::size_t maximum_channels = 8;
    static constexpr std::uint64_t minimum_lease_ms = 100;
    static constexpr std::uint64_t maximum_lease_ms = 60000;

    explicit BoundedSession(std::uint64_t lease_ms) noexcept;

    BoundedSession(const BoundedSession&) = delete;
    BoundedSession& operator=(const BoundedSession&) = delete;

    [[nodiscard]] Result begin(SessionKey key, bool approved_synthetic,
                               std::uint64_t now_ms);
    [[nodiscard]] Result heartbeat(SessionKey key, std::uint64_t now_ms);
    [[nodiscard]] Result reserve_channel(SessionKey key, ChannelKind kind,
                                         std::uint64_t now_ms,
                                         std::uint32_t& channel_id);
    [[nodiscard]] Result close_channel(SessionKey key, std::uint32_t channel_id,
                                       std::uint64_t now_ms);
    void reset();
    [[nodiscard]] Snapshot snapshot() const;

private:
    struct Slot final {
        std::uint32_t id{};
        ChannelKind kind{ChannelKind::can};
    };

    [[nodiscard]] Result validate_locked(SessionKey key,
                                         std::uint64_t now_ms);
    void invalidate_locked() noexcept;
    [[nodiscard]] bool can_extend(std::uint64_t now_ms) const noexcept;

    mutable std::mutex mutex_;
    const std::uint64_t lease_ms_{};
    SessionKey key_{};
    std::uint64_t last_now_ms_{};
    std::uint64_t expires_at_ms_{};
    std::array<Slot, maximum_channels> slots_{};
    std::uint32_t next_channel_id_{1};
    bool active_{};
};

} // namespace virtualcar::lifecycle
