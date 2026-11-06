// Eight deterministic C++20 read-only ISO-TP transport groups.
// Both Win32 and x64 run the same behavioral checks in an isolated process.
// No physical CAN API, J2534 adapter registration or source-car data.

#include "virtualcar/transport.hpp"

#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdio>
#include <vector>

using virtualcar::transport::Engine;
using virtualcar::transport::Frame;
using virtualcar::transport::Result;
using virtualcar::transport::Route;
using virtualcar::transport::RuleKind;

namespace {
constexpr Route route11{0x7e0U, 0x7e8U, 500000U, false};
constexpr Route route29{0x18daf110U, 0x18da10f1U, 500000U, true};
constexpr std::array<std::uint8_t, 3> cts{0x30U, 0U, 0U};

bool configured(Engine& engine, Route route = route11)
{
    return engine.configure(route) &&
        engine.add_filter(RuleKind::pass,
            route.extended ? 0x1fffffffU : 0x7ffU,
            route.response_id) == Result::ok;
}

std::vector<std::uint8_t> payload(std::size_t length)
{
    std::vector<std::uint8_t> out(length);
    for (std::size_t i = 0; i < length; ++i)
        out[i] = static_cast<std::uint8_t>((i % 241U) + 1U);
    return out;
}

bool group01_routes()
{
    Engine e;
    if (e.configure({0x800U, 0x7e8U, 500000U, false})) return false;
    if (e.configure({0x7e0U, 0x7e0U, 500000U, false})) return false;
    if (e.configure({0x7e0U, 0x7e8U, 333333U, false})) return false;
    if (!configured(e)) return false;
    constexpr std::array<std::uint8_t, 1> frame{0x55U};
    if (e.ingest_synthetic(route11.response_id, true, frame, 1U) != Result::invalid)
        return false;
    if (e.ingest_synthetic(0x1fffffffU, false, frame, 1U) != Result::invalid)
        return false;
    Engine big;
    return configured(big, route29) && big.configured() && e.configured();
}

bool group02_filters_and_ownership()
{
    Engine e;
    if (!e.configure(route11)) return false;
    constexpr std::array<std::uint8_t, 2> frame{0x03U, 0x44U};
    if (e.ingest_synthetic(route11.response_id, false, frame, 1U) != Result::blocked)
        return false;
    if (e.add_filter(RuleKind::pass, 0x7ffU, route11.response_id) != Result::ok)
        return false;
    if (e.add_filter(RuleKind::pass, 0x7ffU, route11.response_id) != Result::invalid)
        return false;
    if (e.ingest_synthetic(0x7e9U, false, frame, 1U) != Result::blocked)
        return false;
    if (e.enable_flow_control(0x7e9U, route11.request_id) != Result::wrong_route)
        return false;
    if (e.enable_flow_control(route11.response_id, 0x7e1U) != Result::wrong_route)
        return false;
    if (e.add_filter(RuleKind::block, 0x7ffU, route11.response_id) != Result::ok)
        return false;
    return e.ingest_synthetic(route11.response_id, false, frame, 1U)
        == Result::blocked;
}

bool group03_fifo_atomic_order_and_backpressure()
{
    Engine e;
    if (!configured(e)) return false;
    const auto gen = e.generation();
    for (std::size_t i = 0; i < Engine::fifo_capacity; ++i) {
        const std::array<std::uint8_t, 2> bytes{
            0x22U, static_cast<std::uint8_t>(i)};
        if (e.ingest_synthetic(route11.response_id, false, bytes,
                               static_cast<std::uint64_t>(i))
                != Result::ok) return false;
    }
    constexpr std::array<std::uint8_t, 1> extra{0xaaU};
    if (e.ingest_synthetic(route11.response_id, false, extra, 65U) !=
        Result::queue_full) return false;
    if (e.queued() != Engine::fifo_capacity) return false;
    for (std::size_t i = 0; i < Engine::fifo_capacity; ++i) {
        Frame f{};
        if (!e.pop(f) || f.length != 2 || f.data[0] != 0x22U ||
            f.data[1] != static_cast<std::uint8_t>(i) ||
            f.ready_us != i || f.generation != gen) return false;
    }
    Frame f{};
    return !e.pop(f) && e.queued() == 0;
}

bool group04_first_frame_cts_and_sequence()
{
    Engine e;
    if (!configured(e) ||
        e.enable_flow_control(route11.response_id, route11.request_id) != Result::ok)
        return false;
    const auto p = payload(22); // FF(6) + CF(7) + CF(7) + CF(2)
    if (e.begin_readonly_reply(p, 100U) != Result::ok) return false;
    if (e.pump(100U) != Result::not_ready) return false;
    Frame ff{};
    if (!e.pop(ff) || ff.length != 8 || ff.data[0] != 0x10U ||
        ff.data[1] != 22U || ff.can_id != route11.response_id)
        return false;
    if (!std::equal(p.begin(), p.begin() + 6, ff.data.begin() + 2))
        return false;
    if (e.receive_flow_control(route11.request_id, false, cts, 150U) != Result::ok)
        return false;
    if (e.pump(150U) != Result::ok || e.pending() || e.queued() != 3)
        return false;
    std::vector<std::uint8_t> decoded(ff.data.begin() + 2, ff.data.end());
    for (std::uint8_t seq = 1; seq <= 3; ++seq) {
        Frame cf{};
        if (!e.pop(cf) || cf.data[0] != static_cast<std::uint8_t>(0x20U | seq) ||
            cf.can_id != route11.response_id || cf.length != 8) return false;
        const std::size_t take = (std::min)(p.size() - decoded.size(), std::size_t{7});
        decoded.insert(decoded.end(), cf.data.begin() + 1,
                       cf.data.begin() + 1 + take);
    }
    return decoded == p;
}

bool group05_blocksize_stmin_and_grant()
{
    Engine e;
    if (!configured(e) ||
        e.enable_flow_control(route11.response_id, route11.request_id) != Result::ok)
        return false;
    const auto p = payload(28); // FF + 4 CF
    if (e.begin_readonly_reply(p, 100U) != Result::ok) return false;
    Frame ff{};
    if (!e.pop(ff)) return false;
    const std::array<std::uint8_t, 3> single_grant{0x30U, 1U, 0xf3U};
    if (e.receive_flow_control(route11.request_id, false, single_grant, 200U)
            != Result::ok) return false;
    if (e.pump(200U) != Result::ok || e.queued() != 1 || !e.pending())
        return false;
    Frame first{};
    if (!e.pop(first) || first.data[0] != 0x21U || first.ready_us != 200U)
        return false;
    if (e.pump(201U) != Result::not_ready) return false;

    // Repeated CTS cannot accelerate the next CF below 300us STmin.
    if (e.receive_flow_control(route11.request_id, false, single_grant, 250U)
            != Result::ok) return false;
    if (e.pump(499U) != Result::ok || e.queued() != 0) return false;
    if (e.pump(500U) != Result::ok || e.queued() != 1) return false;
    Frame second{};
    if (!e.pop(second) || second.data[0] != 0x22U || second.ready_us != 500U)
        return false;
    return e.pending();
}

bool group06_wait_overflow_reserved_stmin()
{
    Engine e;
    if (!configured(e) ||
        e.enable_flow_control(route11.response_id, route11.request_id) != Result::ok)
        return false;
    const auto p = payload(21);
    if (e.begin_readonly_reply(p, 0U) != Result::ok) return false;
    constexpr std::array<std::uint8_t, 3> reserved{0x30U, 0U, 0x80U};
    constexpr std::array<std::uint8_t, 3> wait{0x31U, 0U, 0U};
    constexpr std::array<std::uint8_t, 3> overflow{0x32U, 0U, 0U};
    if (e.receive_flow_control(route11.request_id, false, reserved, 1U)
            != Result::invalid) return false;
    if (e.receive_flow_control(route11.request_id, false, wait, 2U)
            != Result::ok) return false;
    if (e.pump(3U) != Result::not_ready) return false;
    if (e.receive_flow_control(route11.request_id, false, overflow, 4U)
            != Result::aborted || e.pending()) return false;
    return e.receive_flow_control(route11.request_id, false, cts, 5U)
        == Result::no_pending;
}

bool group07_unrelated_frames_do_not_extend_fc_timeout()
{
    Engine e;
    if (!configured(e) ||
        e.enable_flow_control(route11.response_id, route11.request_id) != Result::ok)
        return false;
    auto p = payload(20);
    if (e.begin_readonly_reply(p, 100U) != Result::ok) return false;
    Frame ff{};
    if (!e.pop(ff)) return false;
    constexpr std::array<std::uint8_t, 1> irrelevant{0x7fU};
    if (e.receive_flow_control(0x7e1U, false, cts, 100010U)
            != Result::wrong_route) return false;
    if (e.ingest_synthetic(0x7e9U, false, irrelevant, 200000U)
            != Result::blocked) return false;
    if (e.pump(Engine::fc_deadline_us + 100U) != Result::not_ready)
        return false;
    if (e.pump(Engine::fc_deadline_us + 101U) != Result::timed_out)
        return false;
    if (e.pending() || e.queued() != 0) return false;
    return e.receive_flow_control(route11.request_id, false, cts,
                                   Engine::fc_deadline_us + 200U)
        == Result::no_pending;
}

bool group08_reset_wrap_and_lossless_backpressure()
{
    Engine e;
    if (!configured(e, route29) ||
        e.enable_flow_control(route29.response_id, route29.request_id)
            != Result::ok) return false;
    const auto p = payload(150); // more than 16 CF, sequence nibble wraps.
    if (e.begin_readonly_reply(p, 0U) != Result::ok) return false;
    Frame ff{};
    if (!e.pop(ff) || !ff.extended || ff.can_id != route29.response_id)
        return false;
    if (e.receive_flow_control(route29.request_id, true, cts, 1U)
            != Result::ok) return false;
    if (e.pump(1U) != Result::ok || e.pending()) return false;
    const std::size_t total = (p.size() - 6 + 6) / 7;
    if (e.queued() != total) return false;
    for (std::size_t i = 0; i < total; ++i) {
        Frame cf{};
        const std::uint8_t seq = static_cast<std::uint8_t>((i + 1U) & 0x0fU);
        if (!e.pop(cf) || cf.data[0] !=
            static_cast<std::uint8_t>(0x20U | seq)) return false;
    }

    // A saturated FIFO cannot consume pending CF or silently lose bytes.
    const auto huge = payload(4095);
    if (e.begin_readonly_reply(huge, 10U) != Result::ok) return false;
    if (e.receive_flow_control(route29.request_id, true, cts, 11U)
            != Result::ok) return false;
    if (e.pump(11U) != Result::queue_full ||
        e.queued() != Engine::fifo_capacity || !e.pending())
        return false;
    Frame stale{};
    // Consume FF + 63 CFs; pending transfer must resume at the NEXT
    // sequence number, without skipping any payload bytes.
    if (!e.pop(stale) || stale.data[0] != 0x1fU ||
        stale.data[1] != 0xffU) return false;
    for (std::size_t i = 0; i < 63; ++i) {
        Frame drained{};
        if (!e.pop(drained) ||
            drained.data[0] != static_cast<std::uint8_t>(0x20U | ((i + 1U) & 0x0fU)))
            return false;
    }
    if (e.queued() != 0 || !e.pending()) return false;
    if (e.pump(12U) != Result::queue_full || e.queued() != Engine::fifo_capacity ||
        !e.pending()) return false;
    if (!e.pop(stale) || stale.data[0] != 0x20U) return false; // CF#64 wraps
    const auto before = e.generation();
    e.reset();
    if (e.generation() == before || e.pending() || e.queued() ||
        e.filters() != 0 || e.pop(stale)) return false;
    if (e.begin_readonly_reply(p, 12U) != Result::blocked) return false;
    return e.add_filter(RuleKind::pass, 0x1fffffffU, route29.response_id)
        == Result::ok;
}
} // namespace

int main()
{
    using Gate = bool (*)();
    const std::array<std::pair<const char*, Gate>, 8> tests{{
        {"01 standard/extended route bounds", group01_routes},
        {"02 strict filters and ECU ownership", group02_filters_and_ownership},
        {"03 bounded 64-frame FIFO preserves order", group03_fifo_atomic_order_and_backpressure},
        {"04 ISO-TP FF/CTS/CF reassembly", group04_first_frame_cts_and_sequence},
        {"05 FC block credit and microsecond STmin", group05_blocksize_stmin_and_grant},
        {"06 WAIT/OVERFLOW/reserved STmin fail-closed", group06_wait_overflow_reserved_stmin},
        {"07 unrelated CAN traffic does not extend FC timeout", group07_unrelated_frames_do_not_extend_fc_timeout},
        {"08 29bit CF wrap, bounded queue, reset generation", group08_reset_wrap_and_lossless_backpressure}
    }};
    int passed = 0;
    for (const auto& [name, gate] : tests) {
        const bool ok = gate();
        std::printf("%s %s\n", ok ? "PASS" : "FAIL", name);
        if (ok) ++passed;
    }
    std::printf("M4A native transport gates: %d/8\n", passed);
    return passed == 8 ? 0 : 1;
}
