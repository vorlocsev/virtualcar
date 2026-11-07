// M5D-2eB (part 1): seven isolated synthetic Ledger cancellation/restart gates.
// No Named Pipe, Host process, physical adapter, J2534 or ECU is used.
#include "virtualcar/readonly_contract.hpp"

#include <array>
#include <atomic>
#include <cstdint>
#include <cstdio>
#include <thread>

using virtualcar::readonly::Envelope;
using virtualcar::readonly::Identity;
using virtualcar::readonly::Kind;
using virtualcar::readonly::Ledger;
using virtualcar::readonly::Result;
using virtualcar::readonly::Route;

namespace {
constexpr Identity owner{11, 3, 4321, 100000};
constexpr Identity other{11, 3, 4321, 200000};
constexpr Route route{0x7e0, 0x7e8, false};

Envelope request(std::uint64_t id, Identity who = owner) {
    Envelope v{};
    v.kind = Kind::read_request;
    v.owner = who;
    v.route = route;
    v.operation_id = id;
    v.length = 3;
    v.payload[0] = 0x22;
    v.payload[1] = 0xf1;
    v.payload[2] = 0x87;
    return v;
}
Envelope response(std::uint64_t id, Identity who = owner) {
    Envelope v = request(id, who);
    v.kind = Kind::read_response;
    v.length = 5;
    v.payload[0] = 0x62;
    v.payload[3] = 0x41;
    v.payload[4] = 0x42;
    return v;
}

bool cancel_before_reply() {
    Ledger ledger;
    if (ledger.bind(owner, route, 100, 500) != Result::ok) return false;
    for (std::uint64_t id = 1; id <= 48; ++id) {
        const auto now = 100U + id * 4U;
        if (ledger.submit(request(id), now) != Result::ok ||
            ledger.cancel(owner, id, now + 1) != Result::ok ||
            ledger.complete(response(id), now + 2) != Result::stale ||
            ledger.submit(request(id), now + 3) != Result::duplicate ||
            ledger.pending() != 0) return false;
    }
    ledger.revoke();
    return !ledger.active() && ledger.pending() == 0;
}

bool reply_before_cancel() {
    Ledger ledger;
    if (ledger.bind(owner, route, 100, 500) != Result::ok) return false;
    for (std::uint64_t id = 1; id <= 48; ++id) {
        const auto now = 100U + id * 4U;
        if (ledger.submit(request(id), now) != Result::ok ||
            ledger.complete(response(id), now + 1) != Result::ok ||
            ledger.cancel(owner, id, now + 2) != Result::stale ||
            ledger.complete(response(id), now + 3) != Result::stale ||
            ledger.pending() != 0) return false;
    }
    ledger.revoke();
    return !ledger.active() && ledger.pending() == 0;
}

bool simultaneous_cancel_and_complete() {
    Ledger ledger;
    if (ledger.bind(owner, route, 100, 500) != Result::ok) return false;
    for (std::uint64_t id = 1; id <= 64; ++id) {
        const auto now = 100U + id * 4U;
        if (ledger.submit(request(id), now) != Result::ok) return false;
        std::atomic<unsigned> ready{0};
        std::atomic<bool> begin{false};
        Result cancelled = Result::invalid;
        Result completed = Result::invalid;
        std::thread a([&] {
            ready.fetch_add(1, std::memory_order_release);
            while (!begin.load(std::memory_order_acquire)) std::this_thread::yield();
            cancelled = ledger.cancel(owner, id, now + 1);
        });
        std::thread b([&] {
            ready.fetch_add(1, std::memory_order_release);
            while (!begin.load(std::memory_order_acquire)) std::this_thread::yield();
            completed = ledger.complete(response(id), now + 1);
        });
        while (ready.load(std::memory_order_acquire) != 2) std::this_thread::yield();
        begin.store(true, std::memory_order_release);
        a.join();
        b.join();
        const bool one_winner =
            (cancelled == Result::ok && completed == Result::stale) ||
            (cancelled == Result::stale && completed == Result::ok);
        if (!one_winner || ledger.pending() != 0 ||
            ledger.complete(response(id), now + 2) != Result::stale) return false;
    }
    ledger.revoke();
    return !ledger.active() && ledger.pending() == 0;
}

bool simultaneous_revoke_and_complete() {
    Ledger ledger;
    for (std::uint64_t id = 1; id <= 32; ++id) {
        const auto now = 100U + id * 4U;
        if (ledger.bind(owner, route, now, 500) != Result::ok ||
            ledger.submit(request(id), now) != Result::ok) return false;
        std::atomic<unsigned> ready{0};
        std::atomic<bool> begin{false};
        Result completed = Result::invalid;
        std::thread a([&] {
            ready.fetch_add(1, std::memory_order_release);
            while (!begin.load(std::memory_order_acquire)) std::this_thread::yield();
            completed = ledger.complete(response(id), now + 1);
        });
        std::thread b([&] {
            ready.fetch_add(1, std::memory_order_release);
            while (!begin.load(std::memory_order_acquire)) std::this_thread::yield();
            ledger.revoke();
        });
        while (ready.load(std::memory_order_acquire) != 2) std::this_thread::yield();
        begin.store(true, std::memory_order_release);
        a.join();
        b.join();
        if ((completed != Result::ok && completed != Result::not_ready) ||
            ledger.active() || ledger.pending() != 0 ||
            ledger.complete(response(id), now + 2) != Result::not_ready) return false;
    }
    return !ledger.active() && ledger.pending() == 0;
}

bool stale_owner_across_24_restarts() {
    Ledger ledger;
    for (std::uint64_t epoch = 0; epoch < 24; ++epoch) {
        const auto now = 100U + epoch * 10U;
        const Identity previous{11, 3, 4321, 100000U + epoch * 2U};
        const Identity next{11, 3, 4321, 100001U + epoch * 2U};
        const auto old_id = epoch * 2U + 1U;
        const auto new_id = old_id + 1U;
        if (ledger.bind(previous, route, now, 500) != Result::ok ||
            ledger.submit(request(old_id, previous), now) != Result::ok) return false;
        ledger.revoke();
        if (ledger.bind(next, route, now + 1, 500) != Result::ok ||
            ledger.complete(response(old_id, previous), now + 2) != Result::denied ||
            ledger.active() || ledger.pending() != 0 ||
            ledger.bind(next, route, now + 3, 500) != Result::ok ||
            ledger.submit(request(old_id, next), now + 4) != Result::duplicate ||
            ledger.submit(request(new_id, next), now + 5) != Result::ok ||
            ledger.complete(response(new_id, next), now + 6) != Result::ok ||
            ledger.pending() != 0) return false;
        ledger.revoke();
    }
    return !ledger.active() && ledger.pending() == 0;
}

bool exact_expiry_both_orders() {
    Ledger ledger;
    for (std::uint64_t id = 1; id <= 64; ++id) {
        const auto now = 100U + id * 200U;
        if (ledger.bind(owner, route, now, 100) != Result::ok ||
            ledger.submit(request(id), now) != Result::ok) return false;
        if (id % 2 == 0) {
            if (ledger.cancel(owner, id, now + 100) != Result::expired ||
                ledger.complete(response(id), now + 101) != Result::stale)
                return false;
        } else {
            if (ledger.complete(response(id), now + 100) != Result::expired ||
                ledger.cancel(owner, id, now + 101) != Result::stale)
                return false;
        }
        if (ledger.pending() != 0) return false;
        ledger.revoke();
    }
    return !ledger.active() && ledger.pending() == 0;
}

bool wrong_host_cancel_revokes_epoch() {
    Ledger ledger;
    for (std::uint64_t epoch = 0; epoch < 32; ++epoch) {
        const auto now = 100U + epoch * 10U;
        const auto denied_id = epoch * 2U + 1U;
        const auto valid_id = denied_id + 1U;
        if (ledger.bind(owner, route, now, 500) != Result::ok ||
            ledger.submit(request(denied_id), now) != Result::ok ||
            ledger.cancel(other, denied_id, now + 1) != Result::denied ||
            ledger.active() || ledger.pending() != 0 ||
            ledger.bind(owner, route, now + 2, 500) != Result::ok ||
            ledger.complete(response(denied_id), now + 3) != Result::stale ||
            ledger.submit(request(valid_id), now + 4) != Result::ok ||
            ledger.complete(response(valid_id), now + 5) != Result::ok ||
            ledger.pending() != 0) return false;
        ledger.revoke();
    }
    return !ledger.active() && ledger.pending() == 0;
}
} // namespace

int main() {
    struct Gate { const char* name; bool (*check)(); };
    const std::array<Gate, 7> gates{{
        {"cancel before response denies stale", cancel_before_reply},
        {"response before cancel is terminal", reply_before_cancel},
        {"simultaneous cancel/complete single winner", simultaneous_cancel_and_complete},
        {"concurrent revoke/complete drops epoch", simultaneous_revoke_and_complete},
        {"24 synthetic Host FILETIME rotations", stale_owner_across_24_restarts},
        {"exact deadline both orders", exact_expiry_both_orders},
        {"wrong Host cancel revokes pending", wrong_host_cancel_revokes_epoch}
    }};
    unsigned passed = 0;
    for (const auto& gate : gates) {
        const bool ok = gate.check();
        std::printf("%s %s\n", ok ? "PASS" : "FAIL", gate.name);
        if (ok) ++passed;
    }
    std::printf("M5D-2eB offline Ledger preflight: %u/7\n", passed);
    return passed == gates.size() ? 0 : 1;
}
