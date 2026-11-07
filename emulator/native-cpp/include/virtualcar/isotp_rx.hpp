#pragma once
// M4B-1: isolated J2534 v04.04 ISO15765 RX framing and strict multi-ECU
// routing. Synthetic data ONLY; no CAN device, IPC or DLL integration.
// Intentionally not thread-safe; the future host must serialize per channel.

#include "virtualcar/j2534_abi.hpp"
#include "virtualcar/transport.hpp"

#include <array>
#include <cstddef>
#include <cstdint>
#include <span>

namespace virtualcar::transport {

class Iso15765Rx final {
public:
    static constexpr std::size_t route_capacity = 8;
    static constexpr std::size_t filter_capacity = 24;
    static constexpr std::size_t fifo_capacity = 64;
    static constexpr std::size_t payload_capacity = 4095;
    static constexpr std::uint32_t protocol_id = 6U;
    static constexpr std::uint32_t start_of_message = 0x00000002U;
    static constexpr std::uint32_t can_29bit_id = 0x00000100U;

    // Routes share a single bitrate/channel. Every request/response CAN ID
    // must have one owner; cross-ECU overlaps are explicitly forbidden.
    [[nodiscard]] Result add_route(Route route) noexcept;

    // Strict ISO15765 FLOW_CONTROL_FILTER only. The full 32-bit
    // mask must match the exact response CAN ID for segmented replies.
    // A broader mask may match synthetic SingleFrame-sized replies,
    // but overlaps and cross-ECU ambiguous masks are always rejected.
    [[nodiscard]] Result bind_flow_filter(
        std::size_t route_index,
        std::uint32_t mask,
        std::uint32_t pattern,
        std::uint32_t flow_request_id) noexcept;

    // Call only after the C# ScenarioCompiler independently verifies
    // source bytes, SHA-256 and read-only provenance. As another defense,
    // this method only accepts a positive synthetic UDS 0x62 reply.
    // If a two-message START_OF_MESSAGE indication is requested, admission
    // is atomic: BOTH or NEITHER. No CAN frames are ever transmitted.
    [[nodiscard]] Result emit_verified_readonly_reply(
        std::size_t route_index,
        std::span<const std::uint8_t> synthetic_payload,
        bool include_start,
        std::uint64_t timestamp_us) noexcept;

    // The consumer receives the exact J2534 04.04 PASSTHRU_MSG layout.
    // Owner index identifies one configured ECU without inference by DID.
    [[nodiscard]] bool pop(j2534::PASSTHRU_MSG& message,
                           std::size_t& route_index) noexcept;

    void reset() noexcept;
    [[nodiscard]] std::size_t queued() const noexcept { return count_; }
    [[nodiscard]] std::size_t route_count() const noexcept { return route_count_; }
    [[nodiscard]] std::size_t filter_count() const noexcept { return filter_count_; }
    [[nodiscard]] std::uint64_t generation() const noexcept { return generation_; }
    [[nodiscard]] std::uint64_t dropped() const noexcept { return dropped_; }

private:
    struct Filter {
        std::size_t owner{};
        std::uint32_t mask{};
        std::uint32_t pattern{};
        std::uint32_t flow_request_id{};
    };
    struct Entry {
        j2534::PASSTHRU_MSG msg{};
        std::size_t owner{};
        std::uint64_t generation{};
    };

    [[nodiscard]] bool filter_allows(std::size_t index,
                                     bool segmented) const noexcept;
    [[nodiscard]] bool valid_route(const Route& route) const noexcept;
    [[nodiscard]] static j2534::PASSTHRU_MSG make_message(
        const Route& route, std::span<const std::uint8_t> payload,
        bool start, std::uint64_t time_us) noexcept;

    std::array<Route, route_capacity> routes_{};
    std::size_t route_count_{};
    std::array<Filter, filter_capacity> filters_{};
    std::size_t filter_count_{};
    std::array<Entry, fifo_capacity> fifo_{};
    std::size_t head_{};
    std::size_t count_{};
    std::uint64_t dropped_{};
    std::uint64_t generation_{1};
};

} // namespace virtualcar::transport
