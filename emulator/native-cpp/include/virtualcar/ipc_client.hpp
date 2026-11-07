#pragma once

// M5B: bounded native Windows client for the M5A local read-only pipe.
// The public API intentionally exposes only HELLO, KEEPALIVE and GOODBYE.
// It has no CAN, ECU, J2534 or arbitrary-command transport surface.

#include <cstddef>
#include <cstdint>
#include <mutex>
#include <span>
#include <string_view>
#include <vector>
#include "virtualcar/readonly_contract.hpp"

namespace virtualcar::ipc {

enum class Result : std::uint8_t {
    ok,
    invalid,
    busy,
    timed_out,
    disconnected,
    protocol_error,
    peer_mismatch,
    not_authenticated,
    io_error
};

enum class Kind : std::uint16_t {
    hello = 1,
    keep_alive = 2,
    goodbye = 3,
    ack = 4,
    read_request = 5,
    read_reply = 6
};

struct SessionToken final {
    std::uint64_t id{};
    std::uint64_t generation{};
    std::uint32_t server_pid{};
    // FILETIME process creation timestamp, in 100-nanosecond intervals.
    // Combined with PID it distinguishes a restarted host even if Windows
    // reuses the PID and the C# coordinator restarts its token counters.
    std::uint64_t server_creation_time_100ns{};
};

struct Frame final {
    std::uint16_t kind{};
    std::uint64_t session_id{};
    std::uint64_t generation{};
    std::vector<std::uint8_t> payload;
};

class FrameCodec final {
public:
    static constexpr std::uint16_t version = 1;
    static constexpr std::size_t header_length = 28;
    static constexpr std::size_t maximum_payload = 256;

    [[nodiscard]] static bool supported(std::uint16_t kind) noexcept;
    [[nodiscard]] static bool encode(const Frame& frame,
                                     std::vector<std::uint8_t>& output);
    [[nodiscard]] static bool decode(std::span<const std::uint8_t> bytes,
                                     Frame& output);
    [[nodiscard]] static bool valid_pipe_name(std::wstring_view name) noexcept;
};

// One owning thread at a time. Calls are serialized internally so concurrent
// J2534 entrypoints cannot interleave protocol frames on the same pipe.
class Client final {
public:
    Client() noexcept = default;
    ~Client();

    Client(const Client&) = delete;
    Client& operator=(const Client&) = delete;
    Client(Client&&) = delete;
    Client& operator=(Client&&) = delete;

    [[nodiscard]] Result connect(std::wstring_view pipe_name,
                                 std::span<const std::uint8_t> launch_secret,
                                 std::uint32_t expected_server_pid,
                                 std::uint32_t timeout_ms = 3000);
    [[nodiscard]] Result keep_alive();
    // M5D-2b: exactly one allowlisted synthetic 0x22 read over the already
    // authenticated current-user pipe. No generic CAN/J2534 transmit API.
    [[nodiscard]] Result read_synthetic(const readonly::Envelope& request,
                                        readonly::Envelope& response);
    [[nodiscard]] Result disconnect() noexcept;

    [[nodiscard]] bool connected() const noexcept;
    [[nodiscard]] SessionToken session() const noexcept;
    [[nodiscard]] std::uint32_t last_error() const noexcept;

private:
    [[nodiscard]] Result write_frame(const Frame& frame);
    [[nodiscard]] Result read_frame(Frame& frame);
    [[nodiscard]] Result write_exact(std::span<const std::uint8_t> bytes);
    [[nodiscard]] Result read_exact(std::span<std::uint8_t> bytes);
    void close_locked() noexcept;
    [[nodiscard]] static Result map_win32_error(std::uint32_t error) noexcept;

    mutable std::mutex mutex_;
    void* pipe_{};
    SessionToken session_{};
    std::uint32_t timeout_ms_{3000};
    std::uint32_t last_error_{};
};

} // namespace virtualcar::ipc
