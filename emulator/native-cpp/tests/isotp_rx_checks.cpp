// M4B-1: exact J2534 v04.04 ISO15765 RX metadata regression.
// Source-derived oracle: legacy emulator/src/virtualcar.c::enqueue_status,
// strict_iso_fc_route_matches and emit_response. This is not yet a
// black-box executable old C / new C++ output comparison.

#include "virtualcar/isotp_rx.hpp"

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <vector>

using virtualcar::j2534::PASSTHRU_MSG;
using virtualcar::transport::Iso15765Rx;
using virtualcar::transport::Result;
using virtualcar::transport::Route;

namespace {
constexpr Route ecu_a{0x7e0U, 0x7e8U, 500000U, false};
constexpr Route ecu_b{0x7e1U, 0x7e9U, 500000U, false};
constexpr Route ecu_ext{0x18daf110U, 0x18da10f1U, 500000U, true};
constexpr std::array<std::uint8_t, 3> positive{0x62U, 0xf1U, 0x87U};

bool add_exact(Iso15765Rx& rx, const Route& route)
{
    return rx.add_route(route) == Result::ok &&
        rx.bind_flow_filter(rx.route_count() - 1U, 0xffffffffU,
                            route.response_id, route.request_id) == Result::ok;
}

std::vector<std::uint8_t> big_payload(std::size_t count = 21U)
{
    std::vector<std::uint8_t> data(count, 0x55U);
    data[0] = 0x62U;
    data[1] = 0xf1U;
    data[2] = 0x87U;
    return data;
}

bool group01_route_bounds()
{
    Iso15765Rx rx;
    if (rx.add_route({0x800U, 0x7e8U, 500000U, false}) != Result::invalid ||
        rx.add_route({0x7e0U, 0x7e0U, 500000U, false}) != Result::invalid ||
        rx.add_route({0x7e0U, 0x7e8U, 333333U, false}) != Result::invalid)
        return false;
    for (std::size_t i = 0; i < Iso15765Rx::route_capacity; ++i) {
        if (rx.add_route({static_cast<std::uint32_t>(0x700U + i),
                          static_cast<std::uint32_t>(0x750U + i),
                          500000U, false}) != Result::ok)
            return false;
    }
    return rx.route_count() == 8U &&
        rx.add_route({0x710U, 0x760U, 500000U, false}) == Result::queue_full;
}

bool group02_filter_ownership()
{
    Iso15765Rx rx;
    if (!add_exact(rx, ecu_a) || !add_exact(rx, ecu_b)) return false;
    if (rx.bind_flow_filter(0, 0xffffffffU, ecu_a.response_id,
                            ecu_a.request_id) != Result::invalid)
        return false;
    if (rx.bind_flow_filter(1, 0xffffffffU, ecu_b.response_id,
                            ecu_a.request_id) != Result::invalid)
        return false;
    if (rx.bind_flow_filter(8, 0xffffffffU, ecu_b.response_id,
                            ecu_b.request_id) != Result::wrong_route)
        return false;
    if (rx.add_route({ecu_b.response_id, 0x799U, 500000U, false})
            != Result::invalid)
        return false;
    return rx.filter_count() == 2U && rx.route_count() == 2U;
}

bool group03_legacy_iso_single_metadata()
{
    Iso15765Rx rx;
    if (!add_exact(rx, ecu_a)) return false;
    if (rx.emit_verified_readonly_reply(0, positive, true, 1234567U) != Result::ok)
        return false;
    if (rx.queued() != 1U) return false;
    PASSTHRU_MSG msg{};
    std::size_t owner = 9U;
    if (!rx.pop(msg, owner) || owner != 0U) return false;
    // Expected fields and big-endian CAN ID follow legacy enqueue_status().
    return msg.ProtocolID == 6U &&
        msg.RxStatus == 0U && msg.TxFlags == 0U &&
        msg.Timestamp == 1234567U &&
        msg.DataSize == 7U && msg.ExtraDataIndex == 7U &&
        msg.Data[0] == 0x00U && msg.Data[1] == 0x00U &&
        msg.Data[2] == 0x07U && msg.Data[3] == 0xe8U &&
        std::equal(positive.begin(), positive.end(), msg.Data + 4) &&
        !rx.pop(msg, owner);
}

bool group04_extended_and_clock_wrap()
{
    Iso15765Rx rx;
    if (!add_exact(rx, ecu_ext)) return false;
    if (rx.emit_verified_readonly_reply(0, positive, false,
        0x100000005ULL) != Result::ok) return false;
    PASSTHRU_MSG msg{};
    std::size_t owner{};
    return rx.pop(msg, owner) && owner == 0U &&
        msg.ProtocolID == 6U &&
        msg.RxStatus == Iso15765Rx::can_29bit_id &&
        msg.Timestamp == 5U &&
        msg.Data[0] == 0x18U && msg.Data[1] == 0xdaU &&
        msg.Data[2] == 0x10U && msg.Data[3] == 0xf1U &&
        msg.ExtraDataIndex == msg.DataSize;
}

bool group05_atomic_start_and_payload()
{
    Iso15765Rx rx;
    if (!add_exact(rx, ecu_a)) return false;
    for (std::size_t i = 0; i < 63U; ++i)
        if (rx.emit_verified_readonly_reply(0, positive, false, i) != Result::ok)
            return false;
    const auto longer = big_payload();
    if (rx.emit_verified_readonly_reply(0, longer, true, 200U)
        != Result::queue_full || rx.queued() != 63U || rx.dropped() != 1U)
        return false;
    PASSTHRU_MSG msg{};
    std::size_t owner{};
    if (!rx.pop(msg, owner) || msg.RxStatus != 0U) return false;
    if (rx.emit_verified_readonly_reply(0, longer, true, 201U)
        != Result::ok || rx.queued() != 64U) return false;
    for (std::size_t i = 0; i < 62U; ++i) {
        if (!rx.pop(msg, owner) || msg.RxStatus != 0U)
            return false;
    }
    if (!rx.pop(msg, owner) ||
        msg.RxStatus != Iso15765Rx::start_of_message ||
        msg.DataSize != 4U || msg.ExtraDataIndex != 0U ||
        msg.Timestamp != 201U || owner != 0U)
        return false;
    if (!rx.pop(msg, owner) || msg.RxStatus != 0U ||
        msg.DataSize != longer.size() + 4U ||
        msg.ExtraDataIndex != msg.DataSize ||
        !std::equal(longer.begin(), longer.end(), msg.Data + 4))
        return false;
    return rx.queued() == 0U;
}

bool group06_broad_filter_cannot_authorize_segmented()
{
    Iso15765Rx rx;
    if (rx.add_route(ecu_a) != Result::ok) return false;
    // A broad exact-length CAN mask may accept an isolated single
    // reply but MUST NOT authorize physical FC for a multi-frame one.
    if (rx.bind_flow_filter(0, 0xfffffff0U, 0x7e0U, ecu_a.request_id)
        != Result::ok) return false;
    if (rx.emit_verified_readonly_reply(0, positive, false, 1U) != Result::ok)
        return false;
    if (rx.emit_verified_readonly_reply(0, big_payload(), true, 2U)
        != Result::blocked || rx.queued() != 1U)
        return false;
    // No wildcard inheritance of another ECU.
    return rx.add_route(ecu_b) == Result::invalid;
}

bool group07_multi_ecu_isolation()
{
    Iso15765Rx rx;
    if (!add_exact(rx, ecu_a) || !add_exact(rx, ecu_b))
        return false;
    const auto long_reply = big_payload(32U);
    if (rx.emit_verified_readonly_reply(1, long_reply, true, 3U)
        != Result::ok ||
        rx.emit_verified_readonly_reply(0, positive, false, 4U)
        != Result::ok)
        return false;
    PASSTHRU_MSG msg{};
    std::size_t owner = 99U;
    if (!rx.pop(msg, owner) || owner != 1U ||
        msg.Data[2] != 0x07U || msg.Data[3] != 0xe9U ||
        msg.RxStatus != 2U) return false;
    if (!rx.pop(msg, owner) || owner != 1U ||
        msg.DataSize != long_reply.size() + 4U ||
        msg.Data[3] != 0xe9U) return false;
    if (!rx.pop(msg, owner) || owner != 0U ||
        msg.Data[3] != 0xe8U || msg.DataSize != 7U) return false;
    return !rx.pop(msg, owner);
}

bool group08_readonly_failclosed_and_generation()
{
    Iso15765Rx rx;
    if (!add_exact(rx, ecu_a)) return false;
    const std::array<std::uint8_t, 3> security{0x67U, 0x01U, 0U};
    const std::array<std::uint8_t, 3> write{0x6eU, 0xf1U, 0x90U};
    if (rx.emit_verified_readonly_reply(0, security, false, 1U)
        != Result::invalid ||
        rx.emit_verified_readonly_reply(0, write, false, 1U)
        != Result::invalid ||
        rx.emit_verified_readonly_reply(1, positive, false, 1U)
        != Result::wrong_route)
        return false;
    if (rx.emit_verified_readonly_reply(0, big_payload(4096U),
        true, 1U) != Result::invalid) return false;
    if (rx.emit_verified_readonly_reply(0, positive, false, 2U)
        != Result::ok) return false;
    const auto old_generation = rx.generation();
    rx.reset();
    PASSTHRU_MSG stale{};
    std::size_t owner = 0U;
    if (rx.queued() != 0U || rx.route_count() != 0U ||
        rx.filter_count() != 0U || rx.generation() == old_generation ||
        rx.pop(stale, owner))
        return false;
    return rx.emit_verified_readonly_reply(0, positive, false, 3U)
        == Result::wrong_route && add_exact(rx, ecu_a);
}
} // namespace

int main()
{
    using Gate = bool (*)();
    constexpr std::array<std::pair<const char*, Gate>, 8> checks{{
        {"01 bounded CAN route IDs, baud, capacity", group01_route_bounds},
        {"02 strict FC filter ownership and overlap", group02_filter_ownership},
        {"03 source-derived J2534 ISO15765 single RX metadata", group03_legacy_iso_single_metadata},
        {"04 extended 29bit metadata and 32bit timestamp wrap", group04_extended_and_clock_wrap},
        {"05 atomic START_OF_MESSAGE and complete response admission", group05_atomic_start_and_payload},
        {"06 broad filter cannot authorize ISO-TP segmented response", group06_broad_filter_cannot_authorize_segmented},
        {"07 two synthetic ECUs retain distinct CAN IDs and owners", group07_multi_ecu_isolation},
        {"08 only read-only responses, reset and stale-frame fencing", group08_readonly_failclosed_and_generation}
    }};
    int passed = 0;
    for (const auto& [name, gate] : checks) {
        const bool ok = gate();
        std::printf("%s %s\n", ok ? "PASS" : "FAIL", name);
        if (ok) ++passed;
    }
    std::printf("M4B-1 isolated J2534 ISO15765 RX gates: %d/8\n", passed);
    return passed == 8 ? 0 : 1;
}
