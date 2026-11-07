#include "virtualcar/readonly_contract.hpp"

#include <algorithm>
#include <limits>

namespace virtualcar::readonly {
namespace {
constexpr std::array<std::uint8_t, 4> magic{'V', 'C', 'R', 'D'};

void put16(std::uint8_t* p, std::uint16_t v) noexcept {
    p[0] = static_cast<std::uint8_t>(v);
    p[1] = static_cast<std::uint8_t>(v >> 8U);
}
void put32(std::uint8_t* p, std::uint32_t v) noexcept {
    for (unsigned i = 0; i < 4; ++i)
        p[i] = static_cast<std::uint8_t>(v >> (i * 8U));
}
void put64(std::uint8_t* p, std::uint64_t v) noexcept {
    for (unsigned i = 0; i < 8; ++i)
        p[i] = static_cast<std::uint8_t>(v >> (i * 8U));
}
[[nodiscard]] std::uint16_t get16(const std::uint8_t* p) noexcept {
    return static_cast<std::uint16_t>(
        static_cast<std::uint16_t>(p[0]) |
        (static_cast<std::uint16_t>(p[1]) << 8U));
}
[[nodiscard]] std::uint32_t get32(const std::uint8_t* p) noexcept {
    std::uint32_t v = 0;
    for (unsigned i = 0; i < 4; ++i)
        v |= static_cast<std::uint32_t>(p[i]) << (i * 8U);
    return v;
}
[[nodiscard]] std::uint64_t get64(const std::uint8_t* p) noexcept {
    std::uint64_t v = 0;
    for (unsigned i = 0; i < 8; ++i)
        v |= static_cast<std::uint64_t>(p[i]) << (i * 8U);
    return v;
}
[[nodiscard]] bool valid_owner(Identity owner) noexcept {
    return owner.session_id != 0 && owner.generation != 0 &&
        owner.server_pid != 0 && owner.server_created_100ns != 0;
}
[[nodiscard]] bool same_owner(Identity a, Identity b) noexcept {
    return a.session_id == b.session_id &&
        a.generation == b.generation &&
        a.server_pid == b.server_pid &&
        a.server_created_100ns == b.server_created_100ns;
}
[[nodiscard]] bool same_route(Route a, Route b) noexcept {
    return a.request_can_id == b.request_can_id &&
        a.response_can_id == b.response_can_id &&
        a.extended == b.extended;
}
[[nodiscard]] bool allowlisted_did(std::uint16_t did) noexcept {
    // Synthetic identification reads only: software number, ECU identity, VIN.
    return did == 0xf187U || did == 0xf189U || did == 0xf190U;
}
[[nodiscard]] std::uint16_t did_of(const Envelope& f) noexcept {
    return static_cast<std::uint16_t>(
        (static_cast<std::uint16_t>(f.payload[1]) << 8U) |
         static_cast<std::uint16_t>(f.payload[2]));
}
}

bool Codec::valid_route(Route route) noexcept {
    const std::uint32_t limit = route.extended ? 0x1fffffffU : 0x7ffU;
    return route.request_can_id <= limit && route.response_can_id <= limit &&
        route.request_can_id != route.response_can_id;
}

bool Codec::valid(const Envelope& f) noexcept {
    if (!valid_owner(f.owner) || f.operation_id == 0 ||
        !valid_route(f.route) || f.length > maximum_payload)
        return false;
    if (f.kind == Kind::read_request)
        return f.length == 3 && f.payload[0] == 0x22U &&
            allowlisted_did(did_of(f));
    if (f.kind == Kind::read_response)
        return f.length >= 4 && f.payload[0] == 0x62U &&
            allowlisted_did(did_of(f));
    return false;
}

bool Codec::encode(const Envelope& f,
                   std::array<std::uint8_t, maximum_wire_size>& output,
                   std::size_t& used) noexcept {
    used = 0;
    if (!valid(f)) return false;
    output.fill(0);
    std::copy(magic.begin(), magic.end(), output.begin());
    put16(output.data() + 4, version);
    put16(output.data() + 6, static_cast<std::uint16_t>(f.kind));
    put16(output.data() + 8, f.length);
    put16(output.data() + 10, f.route.extended ? 1U : 0U);
    put64(output.data() + 12, f.operation_id);
    put64(output.data() + 20, f.owner.session_id);
    put64(output.data() + 28, f.owner.generation);
    put32(output.data() + 36, f.owner.server_pid);
    put64(output.data() + 40, f.owner.server_created_100ns);
    put32(output.data() + 48, f.route.request_can_id);
    put32(output.data() + 52, f.route.response_can_id);
    // Reserved word at +56 remains zero.
    std::copy_n(f.payload.begin(), f.length, output.begin() + header_size);
    used = header_size + f.length;
    return true;
}

bool Codec::decode(std::span<const std::uint8_t> wire,
                   Envelope& output) noexcept {
    if (wire.size() < header_size || wire.size() > maximum_wire_size ||
        !std::equal(magic.begin(), magic.end(), wire.begin()) ||
        get16(wire.data() + 4) != version ||
        get32(wire.data() + 56) != 0)
        return false;
    const std::uint16_t flags = get16(wire.data() + 10);
    const std::uint16_t length = get16(wire.data() + 8);
    if (flags > 1U || length > maximum_payload ||
        wire.size() != header_size + static_cast<std::size_t>(length))
        return false;
    Envelope decoded{};
    decoded.kind = static_cast<Kind>(get16(wire.data() + 6));
    decoded.length = static_cast<std::uint8_t>(length);
    decoded.operation_id = get64(wire.data() + 12);
    decoded.owner.session_id = get64(wire.data() + 20);
    decoded.owner.generation = get64(wire.data() + 28);
    decoded.owner.server_pid = get32(wire.data() + 36);
    decoded.owner.server_created_100ns = get64(wire.data() + 40);
    decoded.route.request_can_id = get32(wire.data() + 48);
    decoded.route.response_can_id = get32(wire.data() + 52);
    decoded.route.extended = flags != 0;
    std::copy(wire.begin() + header_size, wire.end(), decoded.payload.begin());
    if (!valid(decoded)) return false;
    output = decoded;
    return true;
}

void Ledger::revoke_locked() noexcept {
    pending_.fill({});
    owner_ = {};
    route_ = {};
    timeout_ms_ = 0;
    last_now_ms_ = 0;
    active_ = false;
    // Do not roll back last_issued_operation_id_: no replay across sessions.
}
void Ledger::revoke() noexcept {
    const std::lock_guard<std::mutex> lock(mutex_);
    revoke_locked();
}
bool Ledger::active() const noexcept {
    const std::lock_guard<std::mutex> lock(mutex_);
    return active_;
}
std::size_t Ledger::pending() const noexcept {
    const std::lock_guard<std::mutex> lock(mutex_);
    return static_cast<std::size_t>(std::count_if(pending_.begin(),
        pending_.end(), [](const Slot& s) { return s.operation_id != 0; }));
}
bool Ledger::owner_matches_locked(Identity owner) const noexcept {
    return active_ && same_owner(owner, owner_);
}
bool Ledger::matches_locked(const Envelope& f) const noexcept {
    return owner_matches_locked(f.owner) && same_route(f.route, route_);
}
Result Ledger::bind(Identity owner, Route route,
                    std::uint64_t now_ms,
                    std::uint64_t timeout_ms) noexcept {
    const std::lock_guard<std::mutex> lock(mutex_);
    revoke_locked();
    if (!valid_owner(owner) || !Codec::valid_route(route) ||
        timeout_ms < minimum_timeout_ms || timeout_ms > maximum_timeout_ms ||
        now_ms > (std::numeric_limits<std::uint64_t>::max)() - timeout_ms)
        return Result::invalid;
    owner_ = owner;
    route_ = route;
    timeout_ms_ = timeout_ms;
    last_now_ms_ = now_ms;
    active_ = true;
    return Result::ok;
}
Result Ledger::touch_locked(std::uint64_t now_ms) noexcept {
    if (!active_) return Result::not_ready;
    if (now_ms < last_now_ms_) {
        revoke_locked();
        return Result::clock_regressed;
    }
    last_now_ms_ = now_ms;
    return Result::ok;
}
void Ledger::expire_locked(std::uint64_t now_ms,
                           std::size_t& count) noexcept {
    count = 0;
    for (Slot& s : pending_) {
        if (s.operation_id != 0 && now_ms >= s.expires_at_ms) {
            s = {};
            ++count;
        }
    }
}
Result Ledger::tick(std::uint64_t now_ms,
                    std::size_t& expired_count) noexcept {
    expired_count = 0;
    const std::lock_guard<std::mutex> lock(mutex_);
    const Result state = touch_locked(now_ms);
    if (state != Result::ok) return state;
    expire_locked(now_ms, expired_count);
    return Result::ok;
}
Result Ledger::submit(const Envelope& request, std::uint64_t now_ms) noexcept {
    const std::lock_guard<std::mutex> lock(mutex_);
    const Result state = touch_locked(now_ms);
    if (state != Result::ok) return state;
    if (!Codec::valid(request) || request.kind != Kind::read_request)
        return Result::invalid;
    if (!matches_locked(request)) {
        revoke_locked();
        return Result::denied;
    }
    std::size_t expired{};
    expire_locked(now_ms, expired);
    if (request.operation_id <= last_issued_operation_id_)
        return Result::duplicate;
    if (now_ms > (std::numeric_limits<std::uint64_t>::max)() - timeout_ms_)
        return Result::invalid;
    auto free = std::find_if(pending_.begin(), pending_.end(),
        [](const Slot& s) { return s.operation_id == 0; });
    if (free == pending_.end()) return Result::capacity;
    *free = Slot{request.operation_id, now_ms + timeout_ms_, did_of(request)};
    last_issued_operation_id_ = request.operation_id;
    return Result::ok;
}
Result Ledger::complete(const Envelope& response, std::uint64_t now_ms) noexcept {
    const std::lock_guard<std::mutex> lock(mutex_);
    const Result state = touch_locked(now_ms);
    if (state != Result::ok) return state;
    if (!Codec::valid(response) || response.kind != Kind::read_response) {
        revoke_locked();
        return Result::invalid;
    }
    if (!matches_locked(response)) {
        revoke_locked();
        return Result::denied;
    }
    auto pending = std::find_if(pending_.begin(), pending_.end(),
        [&response](const Slot& s) { return s.operation_id == response.operation_id; });
    if (pending == pending_.end()) return Result::stale;
    if (now_ms >= pending->expires_at_ms) {
        *pending = {};
        return Result::expired;
    }
    if (did_of(response) != pending->did) {
        revoke_locked();
        return Result::denied;
    }
    *pending = {};
    return Result::ok;
}
Result Ledger::cancel(Identity owner, std::uint64_t operation_id,
                      std::uint64_t now_ms) noexcept {
    const std::lock_guard<std::mutex> lock(mutex_);
    const Result state = touch_locked(now_ms);
    if (state != Result::ok) return state;
    if (!owner_matches_locked(owner)) {
        revoke_locked();
        return Result::denied;
    }
    if (operation_id == 0) return Result::invalid;
    auto pending = std::find_if(pending_.begin(), pending_.end(),
        [operation_id](const Slot& s) { return s.operation_id == operation_id; });
    if (pending == pending_.end()) return Result::stale;
    if (now_ms >= pending->expires_at_ms) {
        *pending = {};
        return Result::expired;
    }
    *pending = {};
    return Result::ok;
}

} // namespace virtualcar::readonly
