// M5D-2eB: Windows-only, authenticated synthetic Named Pipe Host epoch test.
// Tests two owned Host crashes + one cooperative read cancellation, followed
// by a clean fourth Host. Nothing links into the fail-closed J2534 DLL.
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <Windows.h>
#include "virtualcar/authenticated_session.hpp"

#include <algorithm>
#include <array>
#include <charconv>
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <string>
#include <thread>

using virtualcar::session::AuthenticatedSession;
using Result = virtualcar::session::Result;

namespace {
constexpr virtualcar::readonly::Route route{0x7e0U, 0x7e8U, false};

std::array<std::uint8_t, 32> test_secret() {
    std::array<std::uint8_t, 32> v{};
    for (std::size_t i = 0; i < v.size(); ++i)
        v[i] = static_cast<std::uint8_t>(i * 7U + 3U);
    return v; // Synthetic CI fixture, never a production credential.
}

bool wait_marker(const std::string& path, const std::string& expected) {
    for (unsigned retry = 0; retry < 300; ++retry) {
        std::ifstream in(path, std::ios::binary);
        if (in) {
            std::string value;
            in >> value;
            if (value == expected) return true;
        }
        Sleep(50);
    }
    return false;
}

bool read_pid(const std::string& path, std::uint32_t& pid) {
    pid = 0;
    for (unsigned retry = 0; retry < 300; ++retry) {
        std::ifstream in(path, std::ios::binary);
        if (in) {
            std::string value;
            in >> value;
            std::uint32_t parsed = 0;
            const auto r = std::from_chars(value.data(),
                value.data() + value.size(), parsed);
            if (r.ec == std::errc{} &&
                r.ptr == value.data() + value.size() && parsed != 0) {
                pid = parsed;
                return true;
            }
        }
        Sleep(50);
    }
    return false;
}

bool put_marker(const std::string& path, const char* value) {
    std::ofstream out(path, std::ios::binary | std::ios::trunc);
    if (!out) return false;
    out << value;
    out.close();
    return static_cast<bool>(out);
}

// Caller must only inspect session state after the pending read thread joins.
bool fully_revoked(AuthenticatedSession& session) {
    const auto snap = session.snapshot();
    return !session.connected() && !snap.active &&
        snap.channels == 0 && session.pending_read_count() == 0;
}

bool run(const std::wstring& pipe, std::uint32_t first_pid,
         const std::string& dir) {
    AuthenticatedSession session(5000);
    const auto secret = test_secret();
    const auto file = [&](unsigned round, const char* extension) {
        return dir + "\\round-" + std::to_string(round) + extension;
    };
    virtualcar::ipc::SessionToken previous{};
    std::uint32_t previous_channel = 0;
    for (unsigned round = 0; round < 4; ++round) {
        std::uint32_t pid = first_pid;
        if (round != 0 && !read_pid(file(round, ".pid"), pid)) {
            std::printf("FAIL M5D2eB epoch %u missing verified Host PID\n", round);
            return false;
        }
        if (session.connect(pipe, secret, pid, 5000) != Result::ok)
            return false;
        const auto current = session.session();
        if (current.id == 0 || current.generation == 0 ||
            current.server_pid != pid || current.server_creation_time_100ns == 0)
            return false;
        // Fresh C# Host sessions reuse 1/1 numeric tokens; process creation
        // FILETIME must still change even if Windows eventually reuses a PID.
        if (round != 0 &&
            (current.id != previous.id ||
             current.generation != previous.generation ||
             current.server_creation_time_100ns ==
                 previous.server_creation_time_100ns))
            return false;
        std::uint32_t channel = 0;
        if (session.reserve_channel(
                virtualcar::lifecycle::ChannelKind::can, channel) != Result::ok ||
            channel <= previous_channel ||
            (round != 0 &&
             session.close_channel(previous_channel) != Result::invalid))
            return false;
        previous_channel = channel;
        previous = current;

        std::array<std::uint8_t, 61> data{};
        data.fill(0xa5U);
        std::size_t length = 99;
        if (round == 3) {
            if (session.read_synthetic(route, 0xf187U, data, length) != Result::ok ||
                length != 2 || data[0] != 'A' || data[1] != 'B' ||
                session.pending_read_count() != 0 ||
                session.close_channel(channel) != Result::ok ||
                session.disconnect() != Result::ok ||
                !fully_revoked(session))
                return false;
            std::printf("PASS: M5D2eB three revoked Host epochs, clean F187 recovery\n");
            return true;
        }

        Result status = Result::invalid;
        std::thread pending([&] {
            status = session.read_synthetic(route, 0xf187U, data, length);
        });
        const bool accepted = wait_marker(file(round, ".ready"), "accepted");
        if (!accepted || round == 1)
            session.cancel_read(); // Round 1: controlled cancellation after acceptance.
        pending.join();

        const bool expected = round == 1
            ? status == Result::cancelled
            : (status == Result::disconnected ||
               status == Result::io_error ||
               status == Result::timed_out);
        if (!accepted || !expected || length != 0 ||
            !fully_revoked(session) ||
            !std::all_of(data.begin(), data.end(),
                [](std::uint8_t byte) { return byte == 0; })) {
            std::printf("FAIL M5D2eB round=%u accepted=%u status=%u\n",
                round, static_cast<unsigned>(accepted),
                static_cast<unsigned>(status));
            return false;
        }
        // This marker is the evidence boundary: only after the native client
        // observes rejection AND complete revocation may the runner re-host.
        if (!put_marker(file(round, ".revoked"), "revoked"))
            return false;
    }
    return false;
}
} // namespace

int main(int argc, char** argv) {
    if (argc != 5 || std::string(argv[1]) != "--three-epochs")
        return 2;
    std::wstring pipe;
    for (const char* p = argv[2]; *p != '\0'; ++p) {
        if (static_cast<unsigned char>(*p) > 0x7fU)
            return 2;
        pipe.push_back(static_cast<wchar_t>(*p));
    }
    std::uint32_t first_pid = 0;
    const std::string pid_arg(argv[3]);
    const auto p = std::from_chars(pid_arg.data(),
        pid_arg.data() + pid_arg.size(), first_pid);
    if (p.ec != std::errc{} ||
        p.ptr != pid_arg.data() + pid_arg.size() || first_pid == 0)
        return 2;
    const std::string dir(argv[4]);
    if (dir.empty() || dir.size() > 240 || dir.find('"') != std::string::npos)
        return 2;
    return run(pipe, first_pid, dir) ? 0 : 1;
}
