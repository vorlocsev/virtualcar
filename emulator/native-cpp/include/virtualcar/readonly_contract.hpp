#pragma once
// M5D-1: standalone read-only synthetic request/reply contract.
// No J2534, IPC, device, ECU, or CAN transmission capability is linked here.
// The caller MUST authenticate the Host and sealed synthetic scenario (M5C-2)
// before binding a Ledger. A Ledger bind is NOT an authentication primitive.

#include <array>
#include <cstddef>
#include <cstdint>
#include <mutex>
#include <span>

namespace virtualcar::readonly {

enum class Kind : std::uint16_t {
    read_request = 1,
    read_response = 2
};

enum class Result : std::uint8_t {
    ok, invalid, denied, not_ready, capacity, duplicate,
    stale, expired, clock_regressed, exhausted
};

struct Identity final {
    std::uint64_t session_id{};
    std::uint64_t generation{};
    std::uint32_t server_pid{};
    std::uint64_t server_created_100ns{};
};

struct Route final {
    std::uint32_t request_can_id{};
    std::uint32_t response_can_id{};
    bool extended{};
};

struct Envelope final {
    Kind kind{Kind::read_request};
    Identity owner{};
    std::uint64_t operation_id{};
    Route route{};
    std::uint8_t length{};
    std::array<std::uint8_t, 64> payload{};
};

// VCRD v1 is an OFFLINE PROPOSAL, distinct from existing VCLB v1 control IPC.
// LE 60-byte fixed header + exactly length bytes (0..64).
// 0 magic[4], 4 version:u16, 6 kind:u16, 8 length:u16,
// 10 flags:u16 (bit0 extended only), 12 operation:u64,
// 20 session:u64, 28 generation:u64, 36 Host PID:u32,
// 40 Host creation FILETIME:u64, 48 request CAN:u32,
// 52 response CAN:u32, 56 reserved:u32 (must be 0).
class Codec final {
public:
    static constexpr std::uint16_t version = 1;
    static constexpr std::size_t header_size = 60;
    static constexpr std::size_t maximum_payload = 64;
    static constexpr std::size_t maximum_wire_size = header_size + maximum_payload;

    [[nodiscard]] static bool encode(
        const Envelope& value,
        std::array<std::uint8_t, maximum_wire_size>& output,
        std::size_t& used) noexcept;
    [[nodiscard]] static bool decode(
        std::span<const std::uint8_t> wire, Envelope& value) noexcept;
    [[nodiscard]] static bool valid(const Envelope& value) noexcept;
    [[nodiscard]] static bool valid_route(Route route) noexcept;
};

// Fixed-capacity correlation ledger, not a socket. Sessions/requests must
// come from an already authenticated, synthetic-only M5C-2 wrapper.
// No response is generated from a request by this class.
// Every operation uses caller-provided monotonic milliseconds.
class Ledger final {
public:
    static constexpr std::size_t maximum_pending = 8;
    static constexpr std::uint64_t minimum_timeout_ms = 100;
    static constexpr std::uint64_t maximum_timeout_ms = 5000;

    Ledger() noexcept = default;
    Ledger(const Ledger&) = delete;
    Ledger& operator=(const Ledger&) = delete;

    [[nodiscard]] Result bind(Identity owner, Route route,
                              std::uint64_t now_ms,
                              std::uint64_t timeout_ms) noexcept;
    [[nodiscard]] Result submit(const Envelope& request,
                                std::uint64_t now_ms) noexcept;
    [[nodiscard]] Result complete(const Envelope& response,
                                  std::uint64_t now_ms) noexcept;
    [[nodiscard]] Result cancel(Identity owner, std::uint64_t operation_id,
                                std::uint64_t now_ms) noexcept;
    [[nodiscard]] Result tick(std::uint64_t now_ms,
                              std::size_t& expired_count) noexcept;
    void revoke() noexcept;
    [[nodiscard]] bool active() const noexcept;
    [[nodiscard]] std::size_t pending() const noexcept;

private:
    struct Slot final {
        std::uint64_t operation_id{};
        std::uint64_t expires_at_ms{};
        std::uint16_t did{};
    };

    [[nodiscard]] Result touch_locked(std::uint64_t now_ms) noexcept;
    void expire_locked(std::uint64_t now_ms, std::size_t& count) noexcept;
    void revoke_locked() noexcept;
    [[nodiscard]] bool matches_locked(const Envelope& frame) const noexcept;
    [[nodiscard]] bool owner_matches_locked(Identity owner) const noexcept;

    mutable std::mutex mutex_;
    std::array<Slot, maximum_pending> pending_{};
    Identity owner_{};
    Route route_{};
    std::uint64_t timeout_ms_{};
    std::uint64_t last_now_ms_{};
    std::uint64_t last_issued_operation_id_{};
    bool active_{};
};

} // namespace virtualcar::readonly
