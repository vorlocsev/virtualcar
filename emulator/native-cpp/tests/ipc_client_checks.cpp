#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <Windows.h>

#include "virtualcar/ipc_client.hpp"
#include "virtualcar/authenticated_session.hpp"

#include <algorithm>
#include <array>
#include <charconv>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <string>
#include <thread>
#include <atomic>
#include <system_error>
#include <utility>
#include <vector>

using virtualcar::ipc::Client;
using virtualcar::ipc::Frame;
using virtualcar::ipc::FrameCodec;
using virtualcar::ipc::Kind;
using virtualcar::ipc::Result;
using virtualcar::session::AuthenticatedSession;
using SessionResult = virtualcar::session::Result;

namespace {

void put_u16(std::vector<std::uint8_t>& bytes, std::size_t offset,
             std::uint16_t value)
{
    bytes[offset] = static_cast<std::uint8_t>(value & 0xffU);
    bytes[offset + 1] = static_cast<std::uint8_t>((value >> 8U) & 0xffU);
}

void put_u32(std::vector<std::uint8_t>& bytes, std::size_t offset,
             std::uint32_t value)
{
    for (unsigned i = 0; i < 4; ++i)
        bytes[offset + i] = static_cast<std::uint8_t>((value >> (i * 8U)) & 0xffU);
}

std::array<std::uint8_t, 32> test_secret()
{
    std::array<std::uint8_t, 32> secret{};
    for (std::size_t i = 0; i < secret.size(); ++i)
        secret[i] = static_cast<std::uint8_t>(i * 7U + 3U);
    return secret;
}

bool group01_hello_golden_vector()
{
    Frame hello{};
    hello.kind = static_cast<std::uint16_t>(Kind::hello);
    const auto secret = test_secret();
    hello.payload.assign(secret.begin(), secret.end());

    std::vector<std::uint8_t> bytes;
    if (!FrameCodec::encode(hello, bytes) ||
        bytes.size() != FrameCodec::header_length + secret.size())
        return false;

    constexpr std::array<std::uint8_t, 12> header{
        'V', 'C', 'L', 'B', 1, 0, 1, 0, 32, 0, 0, 0
    };
    if (!std::equal(header.begin(), header.end(), bytes.begin()))
        return false;
    if (std::any_of(bytes.begin() + 12, bytes.begin() + 28,
            [](std::uint8_t value) { return value != 0; }))
        return false;
    return std::equal(secret.begin(), secret.end(), bytes.begin() + 28);
}

bool group02_ack_roundtrip_and_token()
{
    Frame expected{};
    expected.kind = static_cast<std::uint16_t>(Kind::ack);
    expected.session_id = 0x0102030405060708ULL;
    expected.generation = 0x1112131415161718ULL;

    std::vector<std::uint8_t> bytes;
    if (!FrameCodec::encode(expected, bytes)) return false;
    Frame actual{};
    if (!FrameCodec::decode(bytes, actual)) return false;
    return actual.kind == expected.kind &&
        actual.session_id == expected.session_id &&
        actual.generation == expected.generation &&
        actual.payload.empty();
}

bool group03_all_kinds_roundtrip()
{
    for (std::uint16_t kind = static_cast<std::uint16_t>(Kind::hello);
         kind <= static_cast<std::uint16_t>(Kind::ack); ++kind) {
        Frame expected{};
        expected.kind = kind;
        expected.session_id = 0x12345678U;
        expected.generation = 0x87654321U;
        expected.payload = {0x22U, 0xf1U, 0x87U};

        std::vector<std::uint8_t> bytes;
        if (!FrameCodec::encode(expected, bytes)) return false;
        Frame actual{};
        if (!FrameCodec::decode(bytes, actual) ||
            actual.kind != expected.kind ||
            actual.session_id != expected.session_id ||
            actual.generation != expected.generation ||
            actual.payload != expected.payload)
            return false;
    }
    return true;
}

bool group04_bad_magic_version_and_kind_rejected()
{
    Frame source{};
    source.kind = static_cast<std::uint16_t>(Kind::ack);
    std::vector<std::uint8_t> bytes;
    if (!FrameCodec::encode(source, bytes)) return false;
    Frame output{};

    auto invalid = bytes;
    invalid[0] = static_cast<std::uint8_t>('X');
    if (FrameCodec::decode(invalid, output)) return false;

    invalid = bytes;
    put_u16(invalid, 4, FrameCodec::version + 1);
    if (FrameCodec::decode(invalid, output)) return false;

    invalid = bytes;
    put_u16(invalid, 6, 99);
    return !FrameCodec::decode(invalid, output);
}

bool group05_truncated_oversized_and_trailing_data_rejected()
{
    Frame source{};
    source.kind = static_cast<std::uint16_t>(Kind::ack);
    std::vector<std::uint8_t> bytes;
    if (!FrameCodec::encode(source, bytes)) return false;
    Frame output{};

    auto invalid = bytes;
    invalid.resize(FrameCodec::header_length - 1);
    if (FrameCodec::decode(invalid, output)) return false;

    invalid = bytes;
    put_u32(invalid, 8,
        static_cast<std::uint32_t>(FrameCodec::maximum_payload + 1));
    if (FrameCodec::decode(invalid, output)) return false;

    invalid = bytes;
    put_u32(invalid, 8, 0xffffffffU);
    if (FrameCodec::decode(invalid, output)) return false;

    invalid = bytes;
    invalid.push_back(0xaaU);
    return !FrameCodec::decode(invalid, output);
}

bool group06_invalid_frames_cannot_be_encoded()
{
    Frame invalid{};
    invalid.kind = 99;
    std::vector<std::uint8_t> bytes;
    if (FrameCodec::encode(invalid, bytes)) return false;

    invalid.kind = static_cast<std::uint16_t>(Kind::hello);
    invalid.payload.resize(FrameCodec::maximum_payload + 1, 0x5aU);
    return !FrameCodec::encode(invalid, bytes);
}

bool group07_pipe_name_allowlist()
{
    if (!FrameCodec::valid_pipe_name(L"vcm5b-x86-test-01") ||
        !FrameCodec::valid_pipe_name(L"abc-123"))
        return false;
    if (FrameCodec::valid_pipe_name(L"") ||
        FrameCodec::valid_pipe_name(L"VCM5B") ||
        FrameCodec::valid_pipe_name(L"..") ||
        FrameCodec::valid_pipe_name(L"vcm5b\\\\evil") ||
        FrameCodec::valid_pipe_name(L"vcm5b name"))
        return false;
    return !FrameCodec::valid_pipe_name(std::wstring(81, L'a'));
}

bool group08_connect_and_absolute_read_deadlines_are_bounded()
{
    const auto secret = test_secret();

    Client missing;
    const std::wstring missing_name = L"vcm5b-no-listener-" +
        std::to_wstring(GetCurrentProcessId()) + L"-" +
        std::to_wstring(GetTickCount64());
    if (missing.connect(missing_name, secret, 0, 100) != Result::invalid)
        return false;
    const auto connect_start = std::chrono::steady_clock::now();
    const Result connect_result = missing.connect(missing_name, secret, 1, 100);
    const auto connect_elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::steady_clock::now() - connect_start).count();
    if (connect_result != Result::timed_out || missing.connected() ||
        connect_elapsed < 80 || connect_elapsed >= 2000)
        return false;

    // A peer that trickles an incomplete ACK must not extend the absolute
    // whole-frame read deadline by delivering bytes just before each wait ends.
    const std::wstring stalled_name = L"vcm5b-stall-" +
        std::to_wstring(GetCurrentProcessId()) + L"-" +
        std::to_wstring(GetTickCount64());
    const std::wstring path = L"\\\\.\\pipe\\" + stalled_name;
    HANDLE server = CreateNamedPipeW(path.c_str(), PIPE_ACCESS_DUPLEX,
        PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT,
        1, 512, 512, 0, nullptr);
    if (server == INVALID_HANDLE_VALUE)
        return false;

    std::atomic<bool> hello_received{false};
    std::atomic<long long> first_fragment_ms{-1};
    std::atomic<long long> second_fragment_ms{-1};
    std::thread server_thread([server, &hello_received, &first_fragment_ms,
                               &second_fragment_ms] {
        const BOOL connected = ConnectNamedPipe(server, nullptr);
        if (connected == FALSE && GetLastError() != ERROR_PIPE_CONNECTED) {
            CloseHandle(server);
            return;
        }

        std::array<std::uint8_t, FrameCodec::header_length + 32> hello{};
        std::size_t offset = 0;
        while (offset < hello.size()) {
            DWORD received = 0;
            const DWORD request = static_cast<DWORD>(hello.size() - offset);
            if (ReadFile(server, hello.data() + offset, request, &received, nullptr) == FALSE ||
                received == 0) {
                CloseHandle(server);
                return;
            }
            offset += received;
        }
        hello_received.store(true);
        const auto peer_started = std::chrono::steady_clock::now();

        const std::uint8_t first = static_cast<std::uint8_t>('V');
        DWORD written = 0;
        if (WriteFile(server, &first, 1, &written, nullptr) == FALSE || written != 1) {
            CloseHandle(server);
            return;
        }
        first_fragment_ms.store(std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::steady_clock::now() - peer_started).count());

        // The second byte arrives well before the 500 ms absolute deadline.
        // The server closes at 600 ms: a client that incorrectly restarts a
        // 500 ms deadline after each byte will observe disconnect, not timeout.
        Sleep(300);
        const std::uint8_t second = static_cast<std::uint8_t>('C');
        if (WriteFile(server, &second, 1, &written, nullptr) == FALSE || written != 1) {
            CloseHandle(server);
            return;
        }
        second_fragment_ms.store(std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::steady_clock::now() - peer_started).count());
        Sleep(300);
        (void)DisconnectNamedPipe(server);
        CloseHandle(server);
    });

    Client stalled;
    const auto read_start = std::chrono::steady_clock::now();
    const Result read_result = stalled.connect(
        stalled_name, secret, static_cast<std::uint32_t>(GetCurrentProcessId()), 500);
    const auto read_elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::steady_clock::now() - read_start).count();
    server_thread.join();

    const long long first_ms = first_fragment_ms.load();
    const long long second_ms = second_fragment_ms.load();
    return read_result == Result::timed_out && !stalled.connected() &&
        hello_received.load() && first_ms >= 0 && first_ms < 200 &&
        second_ms >= 250 && second_ms < 450 &&
        read_elapsed >= 400 && read_elapsed < 2000;
}

bool cross_language_reject_peer(const std::wstring& pipe_name,
                                std::uint32_t expected_server_pid)
{
    Client client;
    const auto secret = test_secret();
    const Result result = client.connect(pipe_name, secret, expected_server_pid, 5000);
    if (result != Result::peer_mismatch || client.connected()) {
        std::printf("FAIL same-user pipe endpoint was not rejected before HELLO\n");
        return false;
    }
    std::printf("PASS C++ client rejects a pipe hosted by the wrong process\n");
    return true;
}

bool cross_language_connect(const std::wstring& pipe_name,
                            std::uint32_t expected_server_pid)
{
    Client client;
    const auto secret = test_secret();
    const Result connected = client.connect(pipe_name, secret, expected_server_pid, 5000);
    if (connected != Result::ok || !client.connected()) {
        std::printf("FAIL C# host HELLO (status=%u, win32=%u)\n",
            static_cast<unsigned>(connected), client.last_error());
        return false;
    }
    const auto token = client.session();
    if (token.id == 0 || token.generation == 0) {
        std::printf("FAIL C# host session token\n");
        return false;
    }
    std::atomic<bool> first_keepalive{false};
    std::atomic<bool> second_keepalive{false};
    std::thread first([&] {
        first_keepalive.store(client.keep_alive() == Result::ok);
    });
    std::thread second([&] {
        second_keepalive.store(client.keep_alive() == Result::ok);
    });
    first.join();
    second.join();
    if (!first_keepalive.load() || !second_keepalive.load()) {
        std::printf("FAIL C# host concurrent session-bound KEEPALIVE\n");
        return false;
    }
    if (client.disconnect() != Result::ok || client.connected()) {
        std::printf("FAIL C# host GOODBYE\n");
        return false;
    }
    std::printf("PASS C++ native client <-> C# Host HELLO/KEEPALIVE/GOODBYE\n");
    return true;
}


bool cross_language_authenticated_lifecycle(const std::wstring& pipe_name,
                                             std::uint32_t expected_server_pid,
                                             std::uint64_t lease_ms = 5000)
{
    AuthenticatedSession session(lease_ms);
    const auto secret = test_secret();
    const SessionResult connected = session.connect(
        pipe_name, secret, expected_server_pid, 5000);
    if (connected != SessionResult::ok || !session.connected()) {
        std::printf("FAIL authenticated lifecycle HELLO (status=%u, win32=%u)\\n",
            static_cast<unsigned>(connected), session.last_error());
        return false;
    }

    const auto token = session.session();
    if (token.id == 0 || token.generation == 0 ||
        token.server_pid != expected_server_pid ||
        token.server_creation_time_100ns == 0) {
        std::printf("FAIL authenticated host process identity\\n");
        return false;
    }

    std::uint32_t can_channel{};
    std::uint32_t iso_channel{};
    if (session.reserve_channel(virtualcar::lifecycle::ChannelKind::can,
            can_channel) != SessionResult::ok ||
        session.reserve_channel(virtualcar::lifecycle::ChannelKind::iso15765,
            iso_channel) != SessionResult::ok ||
        can_channel == 0 || iso_channel == 0 || can_channel == iso_channel) {
        std::printf("FAIL authenticated bounded channel reservation\\n");
        return false;
    }
    if (session.keep_alive() != SessionResult::ok ||
        session.close_channel(can_channel) != SessionResult::ok ||
        session.close_channel(iso_channel) != SessionResult::ok) {
        std::printf("FAIL authenticated lifecycle heartbeat/channel close\\n");
        return false;
    }
    if (session.disconnect() != SessionResult::ok || session.connected() ||
        session.snapshot().active || session.snapshot().channels != 0) {
        std::printf("FAIL authenticated lifecycle GOODBYE/cleanup\\n");
        return false;
    }
    std::printf("PASS authenticated C++ lifecycle <-> C# Host PID/creation/lease/channels\\n");
    return true;
}

bool cross_language_lifecycle_expiry(const std::wstring& pipe_name,
                                     std::uint32_t expected_server_pid)
{
    AuthenticatedSession session(250);
    const auto secret = test_secret();
    if (session.connect(pipe_name, secret, expected_server_pid, 5000) != SessionResult::ok)
        return false;
    std::uint32_t channel{};
    if (session.reserve_channel(virtualcar::lifecycle::ChannelKind::can,
            channel) != SessionResult::ok || channel == 0)
        return false;
    Sleep(350);
    std::uint32_t rejected{};
    const SessionResult expired = session.reserve_channel(
        virtualcar::lifecycle::ChannelKind::iso15765, rejected);
    if (expired != SessionResult::expired || rejected != 0 ||
        session.connected() || session.snapshot().active ||
        session.snapshot().channels != 0) {
        std::printf("FAIL local lease expiry did not revoke session and channels\\n");
        return false;
    }
    std::printf("PASS authenticated lifecycle lease expiry sends GOODBYE and clears channels\\n");
    return true;
}

bool cross_language_lifecycle_host_restart(const std::wstring& pipe_name,
                                           std::uint32_t first_server_pid,
                                           const char* ready_path,
                                           const char* host_lost_path,
                                           const char* next_pid_path)
{
    AuthenticatedSession session(5000);
    const auto secret = test_secret();
    if (session.connect(pipe_name, secret, first_server_pid, 5000) != SessionResult::ok)
        return false;
    const auto first_token = session.session();
    std::uint32_t old_channel{};
    if (session.reserve_channel(virtualcar::lifecycle::ChannelKind::can,
            old_channel) != SessionResult::ok || old_channel == 0)
        return false;

    // Signal the PowerShell orchestrator that the authenticated client
    // is connected and has an active synthetic channel. The orchestrator
    // terminates its own retained Process handle, never a PID reopened here.
    {
        std::ofstream ready(ready_path, std::ios::binary | std::ios::trunc);
        if (!ready) return false;
        ready << "ready";
        ready.close();
        if (!ready) return false;
    }

    SessionResult lost = SessionResult::ok;
    bool host_loss_detected = false;
    for (unsigned attempt = 0; attempt < 300; ++attempt) {
        lost = session.keep_alive();
        if (lost != SessionResult::ok) {
            host_loss_detected = true;
            break;
        }
        Sleep(50);
    }
    if (!host_loss_detected ||
        (lost != SessionResult::disconnected &&
         lost != SessionResult::io_error &&
         lost != SessionResult::timed_out)) {
        std::printf("FAIL host process loss was not detected (status=%u)\\n",
            static_cast<unsigned>(lost));
        return false;
    }
    if (session.connected() || session.snapshot().active ||
        session.snapshot().channels != 0) {
        std::printf("FAIL host loss left local session/channel state active\\n");
        return false;
    }

    // This marker is written only after the client has observed the broken
    // pipe and revoked its session. The orchestrator may now start Host #2.
    {
        std::ofstream host_lost(host_lost_path, std::ios::binary | std::ios::trunc);
        if (!host_lost) return false;
        host_lost << "revoked";
        host_lost.close();
        if (!host_lost) return false;
    }

    std::uint32_t second_server_pid = 0;
    for (unsigned attempt = 0; attempt < 300 && second_server_pid == 0; ++attempt) {
        std::ifstream input(next_pid_path);
        if (input.good()) {
            std::uint32_t parsed = 0;
            if (input >> parsed && parsed != 0)
                second_server_pid = parsed;
        }
        if (second_server_pid == 0) Sleep(50);
    }
    if (second_server_pid == 0) {
        std::printf("FAIL restarted C# Host PID was not provided\\n");
        return false;
    }

    if (session.connect(pipe_name, secret, second_server_pid, 5000) != SessionResult::ok) {
        std::printf("FAIL reconnect to restarted C# Host (win32=%u)\\n",
            session.last_error());
        return false;
    }
    const auto second_token = session.session();
    if (second_token.id != first_token.id ||
        second_token.generation != first_token.generation ||
        second_token.server_creation_time_100ns == first_token.server_creation_time_100ns ||
        second_token.server_pid != second_server_pid) {
        std::printf("FAIL restarted host did not produce a distinct process-bound session\\n");
        return false;
    }

    std::uint32_t new_channel{};
    if (session.reserve_channel(virtualcar::lifecycle::ChannelKind::can,
            new_channel) != SessionResult::ok ||
        new_channel <= old_channel ||
        session.close_channel(old_channel) != SessionResult::invalid ||
        session.keep_alive() != SessionResult::ok ||
        session.disconnect() != SessionResult::ok ||
        session.snapshot().active || session.snapshot().channels != 0) {
        std::printf("FAIL stale channel survived host restart or recovery failed\\n");
        return false;
    }
    std::printf("PASS host loss revokes state; restarted Host with replayed 1/1 token recovers under new process identity\\n");
    return true;
}

bool cross_language_readonly_positive(const std::wstring& pipe_name,
                                      std::uint32_t expected_server_pid)
{
    AuthenticatedSession session;
    const auto secret = test_secret();
    if (session.connect(pipe_name, secret, expected_server_pid, 5000) != SessionResult::ok)
        return false;

    constexpr virtualcar::readonly::Route route{0x7e0U, 0x7e8U, false};
    constexpr std::array<std::uint16_t, 3> dids{0xf187U, 0xf189U, 0xf190U};
    constexpr std::array<std::array<std::uint8_t, 3>, 3> expected{{
        {{'A', 'B', 0}},
        {{'C', 0, 0}},
        {{'L', 'A', 'B'}}
    }};
    constexpr std::array<std::size_t, 3> sizes{2U, 1U, 3U};
    for (std::size_t i = 0; i < dids.size(); ++i) {
        std::array<std::uint8_t, 61> body{};
        std::size_t size = 0;
        const SessionResult result = session.read_synthetic(route, dids[i], body, size);
        if (result != SessionResult::ok || size != sizes[i] ||
            !std::equal(body.begin(), body.begin() +
                static_cast<std::ptrdiff_t>(size), expected[i].begin())) {
            std::printf("FAIL native synthetic read DID %04x (status=%u, count=%zu)\\n",
                static_cast<unsigned>(dids[i]),
                static_cast<unsigned>(result), size);
            return false;
        }
    }

    std::array<std::uint8_t, 61> blocked{};
    std::size_t blocked_size{};
    if (session.read_synthetic(route, 0xf191U, blocked, blocked_size) !=
            SessionResult::invalid ||
        blocked_size != 0 || !session.connected()) {
        std::printf("FAIL unauthorized DID was not rejected locally\\n");
        return false;
    }
    const virtualcar::readonly::Route wrong_route{0x7e1U, 0x7e8U, false};
    if (session.read_synthetic(wrong_route, 0xf187U,
            blocked, blocked_size) != SessionResult::invalid ||
        blocked_size != 0 || !session.connected()) {
        std::printf("FAIL route switching was not blocked locally\\n");
        return false;
    }
    if (session.keep_alive() != SessionResult::ok ||
        session.disconnect() != SessionResult::ok ||
        session.snapshot().active || session.snapshot().channels != 0) {
        std::printf("FAIL native read did not close authenticated lifecycle\\n");
        return false;
    }
    std::printf("PASS native C++ x86/x64 synthetic F187/F189/F190 read contract\\n");
    return true;
}

bool cross_language_readonly_deny(const std::wstring& pipe_name,
                                  std::uint32_t expected_server_pid,
                                  bool missing_fixture)
{
    AuthenticatedSession session;
    const auto secret = test_secret();
    if (session.connect(pipe_name, secret, expected_server_pid, 5000) != SessionResult::ok)
        return false;

    const virtualcar::readonly::Route route{
        missing_fixture ? 0x7e0U : 0x7e1U, 0x7e8U, false};
    std::array<std::uint8_t, 61> data{};
    std::size_t count{};
    const SessionResult result = session.read_synthetic(
        route, 0xf187U, data, count);
    if (result == SessionResult::ok || result == SessionResult::invalid ||
        count != 0 || session.connected() ||
        session.snapshot().active || session.snapshot().channels != 0) {
        std::printf("FAIL native read did not revoke on denied Host fixture/route\\n");
        return false;
    }
    std::printf("PASS native read fails closed when Host denies route/fixture\\n");
    return true;
}

bool cross_language_readonly_expiry(const std::wstring& pipe_name,
                                    std::uint32_t expected_server_pid)
{
    AuthenticatedSession session(250);
    const auto secret = test_secret();
    if (session.connect(pipe_name, secret, expected_server_pid, 5000) != SessionResult::ok)
        return false;

    Sleep(350);
    constexpr virtualcar::readonly::Route route{0x7e0U, 0x7e8U, false};
    std::array<std::uint8_t, 61> data{};
    std::size_t count{};
    return session.read_synthetic(route, 0xf187U, data, count) ==
               SessionResult::expired &&
           count == 0 && !session.connected() &&
           !session.snapshot().active && session.snapshot().channels == 0;
}

} // namespace

int main(int argc, char** argv)
{
    if ((argc == 4 &&
         (std::strcmp(argv[1], "--connect") == 0 ||
          std::strcmp(argv[1], "--reject-peer") == 0 ||
          std::strcmp(argv[1], "--lifecycle") == 0 ||
          std::strcmp(argv[1], "--lifecycle-expire") == 0 ||
          std::strcmp(argv[1], "--readonly") == 0 ||
          std::strcmp(argv[1], "--readonly-deny") == 0 ||
          std::strcmp(argv[1], "--readonly-no-fixture") == 0 ||
          std::strcmp(argv[1], "--readonly-expire") == 0)) ||
        (argc == 7 && std::strcmp(argv[1], "--lifecycle-restart") == 0)) {
        std::wstring pipe_name;
        for (const char* p = argv[2]; *p != '\0'; ++p) {
            if (static_cast<unsigned char>(*p) > 0x7fU) return 2;
            pipe_name.push_back(static_cast<wchar_t>(*p));
        }
        std::uint32_t expected_server_pid = 0;
        const char* pid_end = argv[3] + std::strlen(argv[3]);
        const auto parsed = std::from_chars(argv[3], pid_end, expected_server_pid);
        if (parsed.ec != std::errc{} || parsed.ptr != pid_end ||
            expected_server_pid == 0)
            return 2;
        if (std::strcmp(argv[1], "--reject-peer") == 0)
            return cross_language_reject_peer(pipe_name, expected_server_pid) ? 0 : 1;
        if (std::strcmp(argv[1], "--lifecycle") == 0)
            return cross_language_authenticated_lifecycle(pipe_name, expected_server_pid) ? 0 : 1;
        if (std::strcmp(argv[1], "--lifecycle-expire") == 0)
            return cross_language_lifecycle_expiry(pipe_name, expected_server_pid) ? 0 : 1;
        if (std::strcmp(argv[1], "--readonly") == 0)
            return cross_language_readonly_positive(pipe_name, expected_server_pid) ? 0 : 1;
        if (std::strcmp(argv[1], "--readonly-deny") == 0)
            return cross_language_readonly_deny(pipe_name, expected_server_pid, false) ? 0 : 1;
        if (std::strcmp(argv[1], "--readonly-no-fixture") == 0)
            return cross_language_readonly_deny(pipe_name, expected_server_pid, true) ? 0 : 1;
        if (std::strcmp(argv[1], "--readonly-expire") == 0)
            return cross_language_readonly_expiry(pipe_name, expected_server_pid) ? 0 : 1;
        if (std::strcmp(argv[1], "--lifecycle-restart") == 0)
            return cross_language_lifecycle_host_restart(
                pipe_name, expected_server_pid, argv[4], argv[5], argv[6]) ? 0 : 1;
        return cross_language_connect(pipe_name, expected_server_pid) ? 0 : 1;
    }
    if (argc != 1) {
        std::printf("Usage: vc_ipc_client_checks [--connect|--reject-peer|--lifecycle|--lifecycle-expire <pipe-name> <server-pid>] | --lifecycle-restart <pipe-name> <server-pid> <ready-file> <host-lost-file> <next-pid-file>\n");
        return 2;
    }

    using Gate = bool (*)();
    const std::array<std::pair<const char*, Gate>, 8> tests{{
        {"01 C#-compatible HELLO golden vector", group01_hello_golden_vector},
        {"02 ACK roundtrip preserves session token", group02_ack_roundtrip_and_token},
        {"03 all four protocol kinds roundtrip", group03_all_kinds_roundtrip},
        {"04 bad magic/version/kind rejected", group04_bad_magic_version_and_kind_rejected},
        {"05 truncated/oversized/trailing frames rejected", group05_truncated_oversized_and_trailing_data_rejected},
        {"06 invalid frames cannot be encoded", group06_invalid_frames_cannot_be_encoded},
        {"07 pipe name allowlist rejects path injection", group07_pipe_name_allowlist},
        {"08 connect and trickle-read deadlines are bounded", group08_connect_and_absolute_read_deadlines_are_bounded}
    }};

    int passed = 0;
    for (const auto& [name, gate] : tests) {
        const bool ok = gate();
        std::printf("%s %s\n", ok ? "PASS" : "FAIL", name);
        if (ok) ++passed;
    }
    std::printf("M5B native IPC client gates: %d/8\n", passed);
    return passed == 8 ? 0 : 1;
}
