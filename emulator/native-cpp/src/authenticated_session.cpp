#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <Windows.h>

#include "virtualcar/authenticated_session.hpp"

#include <algorithm>
#include <limits>

namespace virtualcar::session {

AuthenticatedSession::AuthenticatedSession(std::uint64_t lease_ms) noexcept
    : lifecycle_(lease_ms)
{
}

AuthenticatedSession::~AuthenticatedSession()
{
    (void)disconnect();
}

Result AuthenticatedSession::connect(std::wstring_view pipe_name,
                                     std::span<const std::uint8_t> launch_secret,
                                     std::uint32_t expected_server_pid,
                                     std::uint32_t timeout_ms)
{
    const std::lock_guard<std::mutex> lock(mutex_);
    if (active_ || client_.connected())
        return Result::busy;

    const ipc::Result connected = client_.connect(
        pipe_name, launch_secret, expected_server_pid, timeout_ms);
    if (connected != ipc::Result::ok)
        return map_ipc(connected);

    const ipc::SessionToken token = client_.session();
    if (token.id == 0 || token.generation == 0 ||
        token.server_pid != expected_server_pid ||
        token.server_creation_time_100ns == 0) {
        (void)client_.disconnect();
        lifecycle_.reset();
        key_ = {};
        active_ = false;
        return Result::peer_mismatch;
    }

    // The C# Host returns ACK only after ScenarioCoordinator has opened a
    // verified synthetic scenario session. There is deliberately no public
    // caller-controlled "approved" flag in this wrapper.
    const lifecycle::SessionKey key{
        token.id, token.generation, token.server_pid,
        token.server_creation_time_100ns};
    const auto started = lifecycle_.begin(
        key, true, static_cast<std::uint64_t>(GetTickCount64()));
    if (started != lifecycle::Result::ok) {
        (void)client_.disconnect();
        lifecycle_.reset();
        key_ = {};
        active_ = false;
        return map_lifecycle(started);
    }

    ledger_.revoke();
    read_route_ = {};
    read_route_bound_ = false;
    key_ = key;
    active_ = true;
    return Result::ok;
}

Result AuthenticatedSession::keep_alive()
{
    const std::lock_guard<std::mutex> lock(mutex_);
    return keep_alive_locked();
}

Result AuthenticatedSession::keep_alive_locked()
{
    if (!active_ || !client_.connected()) {
        revoke_locked();
        return Result::not_authenticated;
    }

    // Check the local lease before remote I/O. A remote ACK must never revive
    // an already-expired local session or its stale channel reservations.
    auto state = lifecycle_.validate(
        key_, static_cast<std::uint64_t>(GetTickCount64()));
    if (state != lifecycle::Result::ok) {
        (void)client_.disconnect();
        revoke_locked();
        return map_lifecycle(state);
    }

    const ipc::Result remote = client_.keep_alive();
    if (remote != ipc::Result::ok) {
        revoke_locked();
        return map_ipc(remote);
    }

    state = lifecycle_.heartbeat(
        key_, static_cast<std::uint64_t>(GetTickCount64()));
    if (state != lifecycle::Result::ok) {
        (void)client_.disconnect();
        revoke_locked();
        return map_lifecycle(state);
    }
    return Result::ok;
}

Result AuthenticatedSession::reserve_channel(lifecycle::ChannelKind kind,
                                              std::uint32_t& channel_id)
{
    const std::lock_guard<std::mutex> lock(mutex_);
    channel_id = 0;
    const Result health = keep_alive_locked();
    if (health != Result::ok)
        return health;

    const auto status = lifecycle_.reserve_channel(
        key_, kind, static_cast<std::uint64_t>(GetTickCount64()), channel_id);
    if (status == lifecycle::Result::expired ||
        status == lifecycle::Result::clock_regressed ||
        status == lifecycle::Result::not_authenticated) {
        (void)client_.disconnect();
        revoke_locked();
    }
    return map_lifecycle(status);
}

Result AuthenticatedSession::close_channel(std::uint32_t channel_id)
{
    const std::lock_guard<std::mutex> lock(mutex_);
    const Result health = keep_alive_locked();
    if (health != Result::ok)
        return health;

    const auto status = lifecycle_.close_channel(
        key_, channel_id, static_cast<std::uint64_t>(GetTickCount64()));
    if (status == lifecycle::Result::expired ||
        status == lifecycle::Result::clock_regressed ||
        status == lifecycle::Result::not_authenticated) {
        (void)client_.disconnect();
        revoke_locked();
    }
    return map_lifecycle(status);
}

Result AuthenticatedSession::read_synthetic(
    readonly::Route route, std::uint16_t did,
    std::array<std::uint8_t, 61>& bytes, std::size_t& length)
{
    const std::lock_guard<std::mutex> lock(mutex_);
    bytes.fill(0);
    length = 0;
    if ((did != 0xf187U && did != 0xf189U && did != 0xf190U) ||
        !readonly::Codec::valid_route(route))
        return Result::invalid;
    if (next_read_operation_id_ == (std::numeric_limits<std::uint64_t>::max)())
        return Result::exhausted;

    const Result health = keep_alive_locked();
    if (health != Result::ok)
        return health;

    const std::uint64_t now = static_cast<std::uint64_t>(GetTickCount64());
    const readonly::Identity owner{key_.id, key_.generation,
        key_.server_pid, key_.server_creation_time_100ns};
    if (!read_route_bound_) {
        const readonly::Result b = ledger_.bind(owner, route, now, 3000);
        if (b != readonly::Result::ok) {
            revoke_locked();
            return map_readonly(b);
        }
        read_route_ = route;
        read_route_bound_ = true;
    } else if (read_route_.request_can_id != route.request_can_id ||
               read_route_.response_can_id != route.response_can_id ||
               read_route_.extended != route.extended) {
        // Never switch synthetic CAN routes within one authenticated pipe.
        return Result::invalid;
    }

    readonly::Envelope request{};
    request.kind = readonly::Kind::read_request;
    request.owner = owner;
    request.operation_id = next_read_operation_id_;
    request.route = route;
    request.length = 3;
    request.payload[0] = 0x22U;
    request.payload[1] = static_cast<std::uint8_t>(did >> 8U);
    request.payload[2] = static_cast<std::uint8_t>(did);

    const readonly::Result queued = ledger_.submit(request, now);
    if (queued != readonly::Result::ok) {
        if (!ledger_.active())
            revoke_locked();
        return map_readonly(queued);
    }
    ++next_read_operation_id_;

    readonly::Envelope response{};
    const ipc::Result wire = client_.read_synthetic(request, response);
    if (wire != ipc::Result::ok || client_.read_cancel_requested()) {
        const Result denied = client_.read_cancel_requested()
            ? Result::cancelled : map_ipc(wire);
        revoke_locked();
        return denied;
    }

    const std::uint64_t received = static_cast<std::uint64_t>(GetTickCount64());
    const readonly::Result done = ledger_.complete(response, received);
    if (done != readonly::Result::ok) {
        revoke_locked();
        return map_readonly(done);
    }
    // A valid VCRD response does not itself grant permission to extend
    // or resurrect an expired M5C-2 authenticated lifecycle.
    const lifecycle::Result lease = lifecycle_.validate(key_, received);
    if (lease != lifecycle::Result::ok) {
        revoke_locked();
        return map_lifecycle(lease);
    }

    length = static_cast<std::size_t>(response.length - 3);
    std::copy_n(response.payload.begin() + 3,
        static_cast<std::ptrdiff_t>(length), bytes.begin());
    return Result::ok;
}

void AuthenticatedSession::cancel_read() noexcept
{
    // The read thread holds mutex_. Cancellation is a sticky atomic
    // signal consumed by the active overlapped read in ipc::Client.
    // The caller must keep this session object alive until it joins.
    client_.request_cancel_read();
}

Result AuthenticatedSession::disconnect() noexcept
{
    const std::lock_guard<std::mutex> lock(mutex_);
    const ipc::Result remote = client_.disconnect();
    lifecycle_.reset();
    ledger_.revoke();
    read_route_ = {};
    read_route_bound_ = false;
    key_ = {};
    active_ = false;
    return map_ipc(remote);
}

void AuthenticatedSession::revoke_locked() noexcept
{
    if (client_.connected())
        (void)client_.disconnect();
    lifecycle_.reset();
    ledger_.revoke();
    read_route_ = {};
    read_route_bound_ = false;
    key_ = {};
    active_ = false;
}

bool AuthenticatedSession::connected() noexcept
{
    const std::lock_guard<std::mutex> lock(mutex_);
    if (!active_ || !client_.connected()) {
        revoke_locked();
        return false;
    }
    const auto state = lifecycle_.validate(
        key_, static_cast<std::uint64_t>(GetTickCount64()));
    if (state != lifecycle::Result::ok) {
        (void)client_.disconnect();
        revoke_locked();
        return false;
    }
    return true;
}

ipc::SessionToken AuthenticatedSession::session() const noexcept
{
    const std::lock_guard<std::mutex> lock(mutex_);
    return client_.session();
}

lifecycle::Snapshot AuthenticatedSession::snapshot() const noexcept
{
    const std::lock_guard<std::mutex> lock(mutex_);
    return lifecycle_.snapshot();
}

std::size_t AuthenticatedSession::pending_read_count() const noexcept
{
    const std::lock_guard<std::mutex> lock(mutex_);
    return ledger_.pending();
}

std::uint32_t AuthenticatedSession::last_error() const noexcept
{
    const std::lock_guard<std::mutex> lock(mutex_);
    return client_.last_error();
}

Result AuthenticatedSession::map_ipc(ipc::Result value) noexcept
{
    switch (value) {
    case ipc::Result::ok: return Result::ok;
    case ipc::Result::invalid: return Result::invalid;
    case ipc::Result::busy: return Result::busy;
    case ipc::Result::timed_out: return Result::timed_out;
    case ipc::Result::disconnected: return Result::disconnected;
    case ipc::Result::protocol_error: return Result::protocol_error;
    case ipc::Result::peer_mismatch: return Result::peer_mismatch;
    case ipc::Result::not_authenticated: return Result::not_authenticated;
    case ipc::Result::io_error: return Result::io_error;
    case ipc::Result::cancelled: return Result::cancelled;
    }
    return Result::io_error;
}

Result AuthenticatedSession::map_readonly(readonly::Result value) noexcept
{
    switch (value) {
    case readonly::Result::ok: return Result::ok;
    case readonly::Result::invalid: return Result::invalid;
    case readonly::Result::denied: return Result::protocol_error;
    case readonly::Result::not_ready: return Result::not_authenticated;
    case readonly::Result::capacity: return Result::capacity;
    case readonly::Result::duplicate: return Result::invalid;
    case readonly::Result::stale: return Result::protocol_error;
    case readonly::Result::expired: return Result::expired;
    case readonly::Result::clock_regressed: return Result::clock_regressed;
    case readonly::Result::exhausted: return Result::exhausted;
    }
    return Result::io_error;
}

Result AuthenticatedSession::map_lifecycle(lifecycle::Result value) noexcept
{
    switch (value) {
    case lifecycle::Result::ok: return Result::ok;
    case lifecycle::Result::invalid: return Result::invalid;
    case lifecycle::Result::not_authenticated: return Result::not_authenticated;
    case lifecycle::Result::expired: return Result::expired;
    case lifecycle::Result::clock_regressed: return Result::clock_regressed;
    case lifecycle::Result::capacity: return Result::capacity;
    case lifecycle::Result::exhausted: return Result::exhausted;
    }
    return Result::invalid;
}

} // namespace virtualcar::session
