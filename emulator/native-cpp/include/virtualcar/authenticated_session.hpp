#pragma once

// M5C-2: binds the M5B authenticated pipe to the M5C bounded lifecycle.
// This is a local control/session wrapper only. It exposes no frame, ECU,
// CAN or J2534 data-plane operation.

#include "virtualcar/ipc_client.hpp"
#include "virtualcar/lifecycle.hpp"
#include "virtualcar/readonly_contract.hpp"

#include <array>
#include <cstddef>
#include <cstdint>
#include <mutex>
#include <span>
#include <string_view>

namespace virtualcar::session {

enum class Result : std::uint8_t {
    ok,
    invalid,
    busy,
    timed_out,
    disconnected,
    protocol_error,
    peer_mismatch,
    not_authenticated,
    expired,
    clock_regressed,
    capacity,
    exhausted,
    io_error
};

class AuthenticatedSession final {
public:
    explicit AuthenticatedSession(std::uint64_t lease_ms = 5000) noexcept;
    ~AuthenticatedSession();

    AuthenticatedSession(const AuthenticatedSession&) = delete;
    AuthenticatedSession& operator=(const AuthenticatedSession&) = delete;
    AuthenticatedSession(AuthenticatedSession&&) = delete;
    AuthenticatedSession& operator=(AuthenticatedSession&&) = delete;

    [[nodiscard]] Result connect(std::wstring_view pipe_name,
                                 std::span<const std::uint8_t> launch_secret,
                                 std::uint32_t expected_server_pid,
                                 std::uint32_t timeout_ms = 3000);
    [[nodiscard]] Result keep_alive();
    [[nodiscard]] Result reserve_channel(lifecycle::ChannelKind kind,
                                         std::uint32_t& channel_id);
    [[nodiscard]] Result close_channel(std::uint32_t channel_id);
    // M5D-2b: a serial, authenticated synthetic 0x22 DID request. The
    // returned buffer is an offline VCRF fixture, never physical CAN data.
    [[nodiscard]] Result read_synthetic(readonly::Route route, std::uint16_t did,
                                        std::array<std::uint8_t, 61>& bytes,
                                        std::size_t& length);
    [[nodiscard]] Result disconnect() noexcept;

    // Local state/lease check only; it is not a remote health probe.
    [[nodiscard]] bool connected() noexcept;
    [[nodiscard]] ipc::SessionToken session() const noexcept;
    [[nodiscard]] lifecycle::Snapshot snapshot() const noexcept;
    [[nodiscard]] std::uint32_t last_error() const noexcept;

private:
    void revoke_locked() noexcept;
    [[nodiscard]] Result keep_alive_locked();
    [[nodiscard]] static Result map_ipc(ipc::Result value) noexcept;
    [[nodiscard]] static Result map_lifecycle(lifecycle::Result value) noexcept;
    [[nodiscard]] static Result map_readonly(readonly::Result value) noexcept;

    mutable std::mutex mutex_;
    ipc::Client client_;
    lifecycle::BoundedSession lifecycle_;
    lifecycle::SessionKey key_{};
    readonly::Ledger ledger_;
    readonly::Route read_route_{};
    // Last issued ID survives disconnect/rebind/restart in this object.
    std::uint64_t next_read_operation_id_{1};
    bool read_route_bound_{};
    bool active_{};
};

} // namespace virtualcar::session
