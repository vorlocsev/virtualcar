#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <Windows.h>

#include "virtualcar/ipc_client.hpp"

#include <algorithm>
#include <array>
#include <charconv>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstring>
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

} // namespace

int main(int argc, char** argv)
{
    if (argc == 4 &&
        (std::strcmp(argv[1], "--connect") == 0 ||
         std::strcmp(argv[1], "--reject-peer") == 0)) {
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
        return cross_language_connect(pipe_name, expected_server_pid) ? 0 : 1;
    }
    if (argc != 1) {
        std::printf("Usage: vc_ipc_client_checks [--connect|--reject-peer <pipe-name> <server-pid>]\n");
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
