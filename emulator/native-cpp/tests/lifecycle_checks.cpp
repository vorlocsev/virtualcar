#include "virtualcar/lifecycle.hpp"

#include <algorithm>
#include <array>
#include <atomic>
#include <cstdint>
#include <cstdio>
#include <limits>
#include <thread>

using virtualcar::lifecycle::BoundedSession;
using virtualcar::lifecycle::ChannelKind;
using virtualcar::lifecycle::Result;
using virtualcar::lifecycle::SessionKey;

namespace {
constexpr SessionKey good{11, 9, 100, 1000};
constexpr SessionKey next{12, 10, 101, 2000};

bool group01_default_fail_closed()
{
    BoundedSession session(500);
    std::uint32_t id = 123;
    const bool blocked = session.heartbeat(good, 1) == Result::not_authenticated &&
        session.reserve_channel(good, ChannelKind::can, 1, id) == Result::not_authenticated &&
        session.close_channel(good, 1, 1) == Result::not_authenticated;
    const auto state = session.snapshot();
    return blocked && id == 0 && !state.active && state.channels == 0 &&
           state.expires_at_ms == 0;
}

bool group02_require_verified_unique_session()
{
    BoundedSession session(500);
    if (session.begin(good, false, 100) != Result::invalid ||
        session.begin({0, 9}, true, 100) != Result::invalid ||
        session.begin({11, 0}, true, 100) != Result::invalid ||
        session.begin(good, true, 100) != Result::ok)
        return false;
    const auto current = session.snapshot();
    if (!current.active || current.expires_at_ms != 600 ||
        session.begin(good, true, 101) != Result::invalid)
        return false;
    return !session.snapshot().active;
}

bool group03_heartbeat_deadline_exact_boundary()
{
    BoundedSession session(500);
    if (session.begin(good, true, 100) != Result::ok ||
        session.heartbeat(good, 599) != Result::ok ||
        session.snapshot().expires_at_ms != 1099 ||
        session.heartbeat(good, 1099) != Result::expired)
        return false;
    return !session.snapshot().active && session.snapshot().channels == 0;
}

bool group04_clock_regression_and_overflow()
{
    BoundedSession session(500);
    if (session.begin(good, true, 600) != Result::ok ||
        session.heartbeat(good, 599) != Result::clock_regressed ||
        session.snapshot().active)
        return false;
    constexpr auto max = std::numeric_limits<std::uint64_t>::max();
    if (session.begin(next, true, max - 400) != Result::invalid ||
        session.snapshot().active)
        return false;
    return session.begin(next, true, 1000) == Result::ok &&
        session.begin(good, true, 999) == Result::clock_regressed &&
        !session.snapshot().active;
}

bool group05_wrong_session_generation_invalidates()
{
    BoundedSession session(500);
    std::uint32_t id{};
    if (session.begin(good, true, 50) != Result::ok ||
        session.reserve_channel(good, ChannelKind::can, 51, id) != Result::ok)
        return false;
    if (session.heartbeat({11, 8, 100, 1000}, 52) != Result::not_authenticated)
        return false;
    return !session.snapshot().active && session.snapshot().channels == 0 &&
        session.close_channel(good, id, 53) == Result::not_authenticated;
}

bool group06_bounded_channel_slots_no_id_reuse()
{
    BoundedSession session(500);
    if (session.begin(good, true, 1) != Result::ok)
        return false;
    std::array<std::uint32_t, BoundedSession::maximum_channels> ids{};
    for (auto& id : ids)
        if (session.reserve_channel(good, ChannelKind::iso15765, 2, id) != Result::ok || id == 0)
            return false;
    std::uint32_t overflow = 7;
    if (session.reserve_channel(good, ChannelKind::can, 3, overflow) != Result::capacity ||
        overflow != 0 || session.snapshot().channels != ids.size() ||
        session.close_channel(good, ids[2], 4) != Result::ok ||
        session.close_channel(good, ids[2], 4) != Result::invalid)
        return false;
    std::uint32_t replacement{};
    return session.reserve_channel(good, ChannelKind::can, 5, replacement) == Result::ok &&
           replacement > ids.back() &&
           session.snapshot().channels == ids.size() &&
           session.reserve_channel(good, static_cast<ChannelKind>(42), 6, overflow) == Result::invalid;
}

bool group07_reauth_drops_old_slots_and_reset()
{
    BoundedSession session(500);
    std::uint32_t old_id{};
    if (session.begin(good, true, 20) != Result::ok ||
        session.reserve_channel(good, ChannelKind::can, 21, old_id) != Result::ok ||
        session.begin(next, true, 22) != Result::ok)
        return false;
    const auto s = session.snapshot();
    if (!s.active || s.channels != 0 || s.expires_at_ms != 522 ||
        session.close_channel(next, old_id, 23) != Result::invalid)
        return false;
    std::uint32_t fresh{};
    if (session.reserve_channel(next, ChannelKind::can, 24, fresh) != Result::ok ||
        fresh <= old_id)
        return false;
    session.reset();
    return !session.snapshot().active && session.snapshot().channels == 0 &&
        session.close_channel(next, fresh, 25) == Result::not_authenticated;
}

bool group08_parallel_reservations_are_bounded()
{
    BoundedSession session(500);
    if (session.begin(good, true, 100) != Result::ok)
        return false;
    constexpr std::size_t calls = 24;
    std::array<std::uint32_t, calls> ids{};
    std::array<Result, calls> results{};
    std::array<std::thread, calls> threads{};
    for (std::size_t i = 0; i < calls; ++i)
        threads[i] = std::thread([&session, &ids, &results, i] {
            results[i] = session.reserve_channel(good, ChannelKind::can, 101, ids[i]);
        });
    for (auto& thread : threads)
        thread.join();
    const std::size_t success = static_cast<std::size_t>(std::count(
        results.begin(), results.end(), Result::ok));
    const std::size_t rejected = static_cast<std::size_t>(std::count(
        results.begin(), results.end(), Result::capacity));
    if (success != BoundedSession::maximum_channels || success + rejected != calls ||
        session.snapshot().channels != BoundedSession::maximum_channels)
        return false;
    for (std::size_t i = 0; i < calls; ++i)
        for (std::size_t j = i + 1; j < calls; ++j)
            if (ids[i] != 0 && ids[i] == ids[j]) return false;
    session.reset();
    return !session.snapshot().active && session.snapshot().channels == 0;
}
} // namespace

int main()
{
    struct Gate { const char* name; bool (*run)(); };
    constexpr std::array<Gate, 8> gates{{
        {"01 Default deny", group01_default_fail_closed},
        {"02 Verified unique session", group02_require_verified_unique_session},
        {"03 Heartbeat deadline", group03_heartbeat_deadline_exact_boundary},
        {"04 Clock regression and overflow", group04_clock_regression_and_overflow},
        {"05 Wrong generation revocation", group05_wrong_session_generation_invalidates},
        {"06 Bounded channels", group06_bounded_channel_slots_no_id_reuse},
        {"07 Reauth and reset", group07_reauth_drops_old_slots_and_reset},
        {"08 Concurrent capacity", group08_parallel_reservations_are_bounded}
    }};
    unsigned passed = 0;
    for (const auto& gate : gates) {
        const bool ok = gate.run();
        std::printf("%s %s\n", ok ? "PASS" : "FAIL", gate.name);
        if (ok) ++passed;
    }
    std::printf("VirtualCar M5C-1 lifecycle gates: %u/8\n", passed);
    return passed == gates.size() ? 0 : 1;
}
