// M5D-1: eleven synthetic, deterministic, read-only VCRD envelope/ledger gates.
// No IPC/ECU/CAN/J2534 transport is touched or enabled by this executable.

#include "virtualcar/readonly_contract.hpp"

#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdio>
#include <limits>
#include <span>
#include <thread>

using virtualcar::readonly::Codec;
using virtualcar::readonly::Envelope;
using virtualcar::readonly::Identity;
using virtualcar::readonly::Kind;
using virtualcar::readonly::Ledger;
using virtualcar::readonly::Result;
using virtualcar::readonly::Route;

namespace {
constexpr Identity owner{11, 3, 4321, 100000};
constexpr Identity another_host{11, 3, 4321, 200000};
constexpr Route standard{0x7e0, 0x7e8, false};
constexpr Route extended{0x18daf110, 0x18da10f1, true};

Envelope request(std::uint64_t id, std::uint16_t did = 0xf190,
                 Route route = standard, Identity identity = owner) {
    Envelope out{};
    out.kind = Kind::read_request;
    out.operation_id = id;
    out.owner = identity;
    out.route = route;
    out.length = 3;
    out.payload[0] = 0x22;
    out.payload[1] = static_cast<std::uint8_t>(did >> 8);
    out.payload[2] = static_cast<std::uint8_t>(did);
    return out;
}
Envelope response(std::uint64_t id, std::uint16_t did = 0xf190,
                  Route route = standard, Identity identity = owner) {
    Envelope out = request(id, did, route, identity);
    out.kind = Kind::read_response;
    out.length = 5;
    out.payload[0] = 0x62;
    out.payload[3] = 0x41; // Completely invented synthetic ECU data.
    out.payload[4] = 0x42;
    return out;
}
bool same(const Envelope& a, const Envelope& b) {
    return a.kind == b.kind &&
        a.operation_id == b.operation_id &&
        a.owner.session_id == b.owner.session_id &&
        a.owner.generation == b.owner.generation &&
        a.owner.server_pid == b.owner.server_pid &&
        a.owner.server_created_100ns == b.owner.server_created_100ns &&
        a.route.request_can_id == b.route.request_can_id &&
        a.route.response_can_id == b.route.response_can_id &&
        a.route.extended == b.route.extended &&
        a.length == b.length &&
        std::equal(a.payload.begin(), a.payload.begin() + a.length,
                   b.payload.begin());
}
void put16(std::array<std::uint8_t, Codec::maximum_wire_size>& a,
           std::size_t offset, std::uint16_t v) {
    a[offset] = static_cast<std::uint8_t>(v);
    a[offset + 1] = static_cast<std::uint8_t>(v >> 8);
}
void put32(std::array<std::uint8_t, Codec::maximum_wire_size>& a,
           std::size_t offset, std::uint32_t v) {
    for (unsigned i = 0; i < 4; ++i)
        a[offset + i] = static_cast<std::uint8_t>(v >> (8U * i));
}

bool group01_wire_golden_vector_and_roundtrip() {
    const Envelope in = request(0x0102030405060708ULL);
    std::array<std::uint8_t, Codec::maximum_wire_size> bytes{};
    std::size_t used = 0;
    if (!Codec::encode(in, bytes, used) || used != 63 ||
        bytes[0] != 'V' || bytes[1] != 'C' ||
        bytes[2] != 'R' || bytes[3] != 'D' ||
        bytes[4] != 1 || bytes[5] != 0 ||
        bytes[6] != 1 || bytes[7] != 0 ||
        bytes[8] != 3 || bytes[9] != 0 ||
        bytes[10] != 0 || bytes[11] != 0 ||
        bytes[12] != 8 || bytes[13] != 7 ||
        bytes[59] != 0 ||
        bytes[60] != 0x22 || bytes[61] != 0xf1 || bytes[62] != 0x90)
        return false;

    Envelope out{};
    if (!Codec::decode(std::span<const std::uint8_t>(bytes.data(), used), out) ||
        !same(in, out))
        return false;
    const Envelope positive = response(0x11);
    if (!Codec::encode(positive, bytes, used) || used != 65 ||
        !Codec::decode(std::span<const std::uint8_t>(bytes.data(), used), out) ||
        !same(positive, out))
        return false;

    const Envelope long_reply = [] {
        Envelope e = response(12);
        e.length = 64;
        for (std::size_t i = 3; i < e.length; ++i)
            e.payload[i] = static_cast<std::uint8_t>(i);
        return e;
    }();
    return Codec::encode(long_reply, bytes, used) &&
        used == Codec::maximum_wire_size &&
        Codec::decode(std::span<const std::uint8_t>(bytes.data(), used), out) &&
        same(long_reply, out);
}

bool group02_framing_rejects_all_malformed_headers() {
    std::array<std::uint8_t, Codec::maximum_wire_size> bytes{};
    std::size_t used{};
    if (!Codec::encode(request(1), bytes, used)) return false;
    Envelope decoded{};
    const auto baseline = bytes;
    const auto invalid = [&decoded](const auto& raw, std::size_t length) {
        return !Codec::decode(
            std::span<const std::uint8_t>(raw.data(), length), decoded);
    };
    if (!invalid(bytes, 59) || !invalid(bytes, used - 1) ||
        !invalid(bytes, used + 1))
        return false;
    bytes = baseline; bytes[0] = 'X';
    if (!invalid(bytes, used)) return false;
    bytes = baseline; put16(bytes, 4, 2);
    if (!invalid(bytes, used)) return false;
    bytes = baseline; put16(bytes, 6, 3); // No writes, reset, security access.
    if (!invalid(bytes, used)) return false;
    bytes = baseline; put16(bytes, 8, 65);
    if (!invalid(bytes, used)) return false;
    bytes = baseline; put16(bytes, 10, 2); // Unknown flags.
    if (!invalid(bytes, used)) return false;
    bytes = baseline; put32(bytes, 56, 1); // Reserved word.
    if (!invalid(bytes, used)) return false;
    bytes = baseline; put16(bytes, 8, 2);
    return invalid(bytes, used);
}

bool group03_read_only_service_and_did_allowlist() {
    std::array<std::uint8_t, Codec::maximum_wire_size> bytes{};
    std::size_t used{};
    constexpr std::array<std::uint16_t, 3> allowed_dids{
        static_cast<std::uint16_t>(0xf187U),
        static_cast<std::uint16_t>(0xf189U),
        static_cast<std::uint16_t>(0xf190U)
    };
    for (const std::uint16_t did : allowed_dids) {
        if (!Codec::encode(request(did, did), bytes, used) ||
            !Codec::encode(response(did, did), bytes, used))
            return false;
    }
    constexpr std::array<std::uint8_t, 4> forbidden_services{
        static_cast<std::uint8_t>(0x27U),
        static_cast<std::uint8_t>(0x2eU),
        static_cast<std::uint8_t>(0x31U),
        static_cast<std::uint8_t>(0x34U)
    };
    for (const std::uint8_t command : forbidden_services) {
        Envelope denied = request(1);
        denied.payload[0] = command;
        if (Codec::encode(denied, bytes, used) || used != 0)
            return false;
    }
    if (Codec::encode(request(2, 0xf191), bytes, used)) return false;
    Envelope invalid_reply = response(3);
    invalid_reply.payload[0] = 0x7f;
    if (Codec::encode(invalid_reply, bytes, used)) return false;
    invalid_reply = response(4);
    invalid_reply.length = 3; // No zero-byte positive reply accepted.
    if (Codec::encode(invalid_reply, bytes, used)) return false;
    Envelope wrong = request(1);
    wrong.route.request_can_id = 0x800;
    if (Codec::encode(wrong, bytes, used)) return false;
    wrong = request(1);
    wrong.route.response_can_id = wrong.route.request_can_id;
    if (Codec::encode(wrong, bytes, used)) return false;
    wrong = request(1);
    wrong.kind = static_cast<Kind>(99);
    return !Codec::encode(wrong, bytes, used);
}

bool group04_default_deny_and_invalid_bind() {
    Ledger ledger;
    if (ledger.active() || ledger.pending() != 0 ||
        ledger.submit(request(1), 1) != Result::not_ready ||
        ledger.complete(response(1), 1) != Result::not_ready)
        return false;
    for (const auto bad : {Identity{}, Identity{0, 3, 1, 1},
                           Identity{11, 3, 0, 1}, Identity{11, 3, 1, 0}}) {
        if (ledger.bind(bad, standard, 10, 100) != Result::invalid)
            return false;
    }
    if (ledger.bind(owner, {0x800, 0x7e8, false}, 10, 100) != Result::invalid ||
        ledger.bind(owner, {0x7e0, 0x7e0, false}, 10, 100) != Result::invalid ||
        ledger.bind(owner, standard, 10, 99) != Result::invalid ||
        ledger.bind(owner, standard, 10, 5001) != Result::invalid ||
        ledger.bind(owner, standard,
            (std::numeric_limits<std::uint64_t>::max)() - 50, 100) != Result::invalid)
        return false;
    return !ledger.active() &&
        ledger.bind(owner, standard, 10, 100) == Result::ok &&
        ledger.active() && ledger.pending() == 0;
}

bool group05_correlate_positive_reply_by_owner_did_and_route() {
    Ledger ledger;
    if (ledger.bind(owner, standard, 100, 500) != Result::ok ||
        ledger.submit(request(1, 0xf190), 101) != Result::ok ||
        ledger.complete(response(1, 0xf190), 102) != Result::ok ||
        ledger.pending() != 0)
        return false;
    if (ledger.complete(response(1), 103) != Result::stale ||
        ledger.submit(request(2, 0xf187), 104) != Result::ok)
        return false;
    if (ledger.complete(response(2, 0xf189), 105) != Result::denied ||
        ledger.active() || ledger.pending() != 0)
        return false;
    if (ledger.bind(owner, extended, 200, 500) != Result::ok ||
        ledger.submit(request(3, 0xf189, extended), 201) != Result::ok ||
        ledger.complete(response(3, 0xf189, extended), 202) != Result::ok ||
        ledger.submit(request(4, 0xf190, extended), 203) != Result::ok)
        return false;
    // Reply on a different CAN route is never accepted as another ECU.
    return ledger.complete(response(4, 0xf190, standard), 204) == Result::denied &&
        !ledger.active() && ledger.pending() == 0;
}

bool group06_bounded_queue_and_no_replay_after_cancel() {
    Ledger ledger;
    if (ledger.bind(owner, standard, 100, 500) != Result::ok) return false;
    for (std::uint64_t id = 1; id <= Ledger::maximum_pending; ++id) {
        if (ledger.submit(request(id), 101) != Result::ok) return false;
    }
    if (ledger.pending() != Ledger::maximum_pending ||
        ledger.submit(request(9), 101) != Result::capacity ||
        ledger.cancel(owner, 3, 102) != Result::ok ||
        ledger.cancel(owner, 3, 102) != Result::stale ||
        ledger.submit(request(3), 103) != Result::duplicate ||
        ledger.submit(request(9), 104) != Result::ok ||
        ledger.pending() != Ledger::maximum_pending)
        return false;
    ledger.revoke();
    if (ledger.active() || ledger.pending() != 0 ||
        ledger.bind(owner, standard, 200, 500) != Result::ok ||
        ledger.submit(request(9), 201) != Result::duplicate ||
        ledger.submit(request(10), 201) != Result::ok)
        return false;
    return ledger.pending() == 1;
}

bool group07_deadline_exact_boundary_and_clock_rollback() {
    Ledger ledger;
    if (ledger.bind(owner, standard, 100, 100) != Result::ok ||
        ledger.submit(request(1), 100) != Result::ok)
        return false;
    std::size_t expired = 99;
    if (ledger.tick(199, expired) != Result::ok || expired != 0 ||
        ledger.complete(response(1), 200) != Result::expired ||
        ledger.pending() != 0)
        return false;
    if (ledger.submit(request(2), 201) != Result::ok ||
        ledger.tick(301, expired) != Result::ok || expired != 1 ||
        ledger.pending() != 0 ||
        ledger.tick(300, expired) != Result::clock_regressed ||
        ledger.active() || ledger.pending() != 0)
        return false;
    constexpr auto max = (std::numeric_limits<std::uint64_t>::max)();
    if (ledger.bind(owner, standard, max - 100, 100) != Result::ok ||
        ledger.submit(request(3), max) != Result::invalid)
        return false;
    return ledger.pending() == 0;
}

bool group08_wrong_host_rejected_and_concurrent_capacity() {
    Ledger ledger;
    if (ledger.bind(owner, standard, 100, 500) != Result::ok ||
        ledger.submit(request(1, 0xf190, standard, another_host), 101) != Result::denied ||
        ledger.active() || ledger.pending() != 0)
        return false;
    if (ledger.bind(owner, standard, 200, 500) != Result::ok)
        return false;
    constexpr std::size_t attempts = 24;
    std::array<Result, attempts> states{};
    std::array<std::thread, attempts> workers{};
    for (std::size_t i = 0; i < attempts; ++i) {
        workers[i] = std::thread([&states, &ledger, i] {
            states[i] = ledger.submit(request(static_cast<std::uint64_t>(i + 2)), 201);
        });
    }
    for (auto& worker : workers) worker.join();
    const auto admitted = std::count(states.begin(), states.end(), Result::ok);
    const auto denied = std::count(states.begin(), states.end(), Result::capacity);
    if (admitted > static_cast<std::ptrdiff_t>(Ledger::maximum_pending) ||
        ledger.pending() > Ledger::maximum_pending)
        return false;
    // Monotonic operation IDs are serialized, so older racing requests may
    // be rejected as duplicates rather than only as capacity failures.
    const auto duplicates = std::count(states.begin(), states.end(), Result::duplicate);
    if (admitted + denied + duplicates != static_cast<std::ptrdiff_t>(attempts) ||
        admitted == 0)
        return false;
    ledger.revoke();
    return !ledger.active() && ledger.pending() == 0;
}

bool group09_host_rebind_denies_stale_owner_and_old_operation() {
    Ledger ledger;
    const Identity new_host{owner.session_id, owner.generation,
        owner.server_pid, owner.server_created_100ns + 1U};
    if (ledger.bind(owner, standard, 100, 500) != Result::ok ||
        ledger.submit(request(1), 101) != Result::ok ||
        ledger.pending() != 1)
        return false;
    ledger.revoke();
    if (ledger.pending() != 0 ||
        ledger.bind(new_host, standard, 200, 500) != Result::ok)
        return false;
    // Even when numeric session and generation were reused, a
    // response from the prior Host's FILETIME must revoke binding.
    if (ledger.complete(response(1), 201) != Result::denied ||
        ledger.active() || ledger.pending() != 0)
        return false;
    if (ledger.bind(new_host, standard, 210, 500) != Result::ok ||
        ledger.submit(request(1, 0xf190, standard, new_host), 211)
            != Result::duplicate ||
        ledger.submit(request(2, 0xf190, standard, new_host), 212)
            != Result::ok ||
        ledger.complete(response(1, 0xf190, standard, new_host), 213)
            != Result::stale ||
        ledger.pending() != 1)
        return false;
    if (ledger.complete(response(2, 0xf190, standard, new_host), 214)
            != Result::ok ||
        ledger.pending() != 0)
        return false;
    ledger.revoke();
    return !ledger.active() && ledger.pending() == 0;
}

bool group10_long_serial_identification_and_rebind_stays_bounded() {
    Ledger ledger;
    constexpr std::array<std::uint16_t, 3> dids{0xf187U, 0xf189U, 0xf190U};
    std::uint64_t now = 100;
    std::uint64_t id = 1;
    // 8 synthetic lifetime epochs x 32 operations. No real ECU access.
    for (unsigned epoch = 0; epoch < 8; ++epoch) {
        const Identity epoch_host{owner.session_id, owner.generation,
            owner.server_pid, owner.server_created_100ns + epoch};
        if (ledger.bind(epoch_host, standard, now, 500) != Result::ok)
            return false;
        for (unsigned i = 0; i < 32; ++i) {
            const std::uint16_t did = dids[i % dids.size()];
            if (ledger.submit(request(id, did, standard, epoch_host), now + 1)
                    != Result::ok ||
                ledger.pending() != 1 ||
                ledger.complete(response(id, did, standard, epoch_host), now + 2)
                    != Result::ok ||
                ledger.pending() != 0)
                return false;
            ++id;
            now += 3;
        }
        ledger.revoke();
        if (ledger.active() || ledger.pending() != 0 ||
            ledger.bind(epoch_host, standard, now, 500) != Result::ok ||
            ledger.submit(request(id - 1, 0xf190, standard, epoch_host), now + 1)
                != Result::duplicate)
            return false;
        ledger.revoke();
        now += 10;
    }
    return !ledger.active() && ledger.pending() == 0 && id == 257;
}

bool group11_deadline_repeats_do_not_resurrect_old_replies() {
    Ledger ledger;
    std::uint64_t now = 100;
    for (std::uint64_t id = 1; id <= 40; ++id) {
        if (ledger.bind(owner, standard, now, 100) != Result::ok ||
            ledger.submit(request(id), now) != Result::ok)
            return false;
        std::size_t expired = 99;
        if (ledger.tick(now + 99, expired) != Result::ok || expired != 0 ||
            ledger.pending() != 1 ||
            ledger.complete(response(id), now + 100) != Result::expired ||
            ledger.complete(response(id), now + 101) != Result::stale ||
            ledger.pending() != 0)
            return false;
        ledger.revoke();
        now += 200;
    }
    return !ledger.active() && ledger.pending() == 0;
}

} // namespace

int main() {
    struct Gate { const char* name; bool (*run)(); };
    const std::array<Gate, 11> gates{{
        {"01 LE bounded golden vectors", group01_wire_golden_vector_and_roundtrip},
        {"02 Reject malformed envelope headers", group02_framing_rejects_all_malformed_headers},
        {"03 Reject nonread/unauthorized DID", group03_read_only_service_and_did_allowlist},
        {"04 Deny unbound/invalid scenario context", group04_default_deny_and_invalid_bind},
        {"05 Correlate response owner/route/DID", group05_correlate_positive_reply_by_owner_did_and_route},
        {"06 Eight queue slots and replay denial", group06_bounded_queue_and_no_replay_after_cancel},
        {"07 Exact timeout and clock rollback", group07_deadline_exact_boundary_and_clock_rollback},
        {"08 Wrong Host + concurrent requests", group08_wrong_host_rejected_and_concurrent_capacity},
        {"09 Host rebind denies stale owner and replay", group09_host_rebind_denies_stale_owner_and_old_operation},
        {"10 Serial 256-reads with epoch rotation", group10_long_serial_identification_and_rebind_stays_bounded},
        {"11 Repeated deadline boundary rejects replies", group11_deadline_repeats_do_not_resurrect_old_replies}
    }};
    unsigned passed = 0;
    for (const auto& gate : gates) {
        const bool ok = gate.run();
        std::printf("%s %s\n", ok ? "PASS" : "FAIL", gate.name);
        if (ok) ++passed;
    }
    std::printf("VirtualCar M5D-1 read-only envelope/ledger: %u/11\n", passed);
    return passed == gates.size() ? 0 : 1;
}
