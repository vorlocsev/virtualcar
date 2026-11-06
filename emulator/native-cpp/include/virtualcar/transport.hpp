#pragma once
// M4A isolated, deterministic, read-only CAN/ISO-TP laboratory transport.
// This module has no hardware, J2534 DLL, IPC, database, or ECU write API.
// The caller must separately authorize a sealed synthetic scenario (M2).

#include <array>
#include <cstddef>
#include <cstdint>
#include <span>

namespace virtualcar::transport {

enum class Result : std::uint8_t {
    ok, invalid, blocked, queue_full, busy, no_pending,
    wrong_route, timed_out, aborted, not_ready
};

enum class RuleKind : std::uint8_t { pass, block };

struct Route {
    std::uint32_t request_id{};
    std::uint32_t response_id{};
    std::uint32_t bitrate{};
    bool extended{};
};

struct Frame {
    std::uint32_t can_id{};
    bool extended{};
    std::uint8_t length{};
    std::array<std::uint8_t, 8> data{};
    std::uint64_t ready_us{};
    std::uint64_t generation{};
};

class Engine final {
public:
    static constexpr std::size_t fifo_capacity = 64;
    static constexpr std::size_t filter_capacity = 24;
    static constexpr std::size_t payload_capacity = 4095;
    static constexpr std::uint64_t fc_deadline_us = 1000000;

    // Own one synthetic ECU route at a time. No shared response IDs.
    // Reconfiguration discards all queue/filter/session state.
    [[nodiscard]] bool configure(Route route) noexcept;
    void reset() noexcept;

    [[nodiscard]] Result add_filter(RuleKind action,
                                    std::uint32_t mask,
                                    std::uint32_t pattern) noexcept;
    // Only exact request CAN ID is accepted as the return FC route.
    [[nodiscard]] Result enable_flow_control(std::uint32_t response_id,
                                              std::uint32_t request_id) noexcept;

    // Enqueue explicitly provided synthetic raw CAN RX (<=8 bytes).
    // Never sends to a physical CAN adapter.
    [[nodiscard]] Result ingest_synthetic(std::uint32_t can_id, bool extended,
                                          std::span<const std::uint8_t> bytes,
                                          std::uint64_t now_us) noexcept;

    // Serialize read-only synthetic ISO-TP response over the CAN FIFO.
    // Requires an exact flow-control filter for multi-frame transfer.
    [[nodiscard]] Result begin_readonly_reply(
        std::span<const std::uint8_t> payload, std::uint64_t now_us) noexcept;
    [[nodiscard]] Result receive_flow_control(
        std::uint32_t from_can_id, bool extended,
        std::span<const std::uint8_t> bytes, std::uint64_t now_us) noexcept;

    // No sleeping or real-time threads: caller provides monotonic microseconds.
    // Backpressure never consumes a pending Consecutive Frame.
    [[nodiscard]] Result pump(std::uint64_t now_us) noexcept;

    [[nodiscard]] bool pop(Frame& frame) noexcept;
    [[nodiscard]] std::size_t queued() const noexcept { return count_; }
    [[nodiscard]] std::size_t filters() const noexcept { return filters_count_; }
    [[nodiscard]] std::uint64_t generation() const noexcept { return generation_; }
    [[nodiscard]] bool pending() const noexcept { return pending_.active; }
    [[nodiscard]] bool configured() const noexcept { return configured_; }

private:
    struct Filter {
        RuleKind action{};
        std::uint32_t mask{};
        std::uint32_t pattern{};
    };
    struct Pending {
        std::array<std::uint8_t, payload_capacity> bytes{};
        std::size_t total{};
        std::size_t offset{};
        std::uint8_t next_seq{1};
        std::uint8_t credit{};
        std::uint8_t block_size{};
        std::uint8_t wait_frames{};
        bool active{};
        bool cts{};
        std::uint64_t next_due_us{};
        std::uint64_t fc_due_us{};
        std::uint32_t stmin_us{};
    };

    [[nodiscard]] bool valid_id(std::uint32_t id, bool extended) const noexcept;
    [[nodiscard]] bool allowed(std::uint32_t id) const noexcept;
    [[nodiscard]] Result enqueue(Frame frame) noexcept;
    void invalidate_pending() noexcept { pending_ = Pending{}; }

    Route route_{};
    bool configured_{};
    bool flow_enabled_{};
    std::array<Filter, filter_capacity> filters_{};
    std::size_t filters_count_{};
    std::array<Frame, fifo_capacity> fifo_{};
    std::size_t head_{};
    std::size_t count_{};
    Pending pending_{};
    std::uint64_t generation_{1};
};

} // namespace virtualcar::transport
