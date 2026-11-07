#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <Windows.h>

#include "virtualcar/authenticated_session.hpp"

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

    key_ = key;
    active_ = true;
    return Result::ok;
}

Result AuthenticatedSession::keep_alive()
{
    const std::lock_guard<std::mutex> lock(mutex_);
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
    if (!active_ || !client_.connected()) {
        revoke_locked();
        return Result::not_authenticated;
    }

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
    if (!active_ || !client_.connected()) {
        revoke_locked();
        return Result::not_authenticated;
    }

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

Result AuthenticatedSession::disconnect() noexcept
{
    const std::lock_guard<std::mutex> lock(mutex_);
    const ipc::Result remote = client_.disconnect();
    lifecycle_.reset();
    key_ = {};
    active_ = false;
    return map_ipc(remote);
}

void AuthenticatedSession::revoke_locked() noexcept
{
    if (client_.connected())
        (void)client_.disconnect();
    lifecycle_.reset();
    key_ = {};
    active_ = false;
}

bool AuthenticatedSession::connected() const noexcept
{
    const std::lock_guard<std::mutex> lock(mutex_);
    return active_ && client_.connected() && lifecycle_.snapshot().active;
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
