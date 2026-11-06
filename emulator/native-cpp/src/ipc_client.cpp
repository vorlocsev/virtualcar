#include "virtualcar/ipc_client.hpp"

#define WIN32_LEAN_AND_MEAN
#include <Windows.h>

#include <algorithm>
#include <array>
#include <cstring>
#include <limits>
#include <string>
#include <utility>

namespace virtualcar::ipc {
namespace {

constexpr std::array<std::uint8_t, 4> magic{'V', 'C', 'L', 'B'};
constexpr std::uint32_t minimum_timeout_ms = 100;
constexpr std::uint32_t maximum_timeout_ms = 60000;

void put_u16(std::uint8_t* out, std::uint16_t value) noexcept
{
    out[0] = static_cast<std::uint8_t>(value & 0xffU);
    out[1] = static_cast<std::uint8_t>((value >> 8U) & 0xffU);
}

void put_u32(std::uint8_t* out, std::uint32_t value) noexcept
{
    for (unsigned i = 0; i < 4; ++i)
        out[i] = static_cast<std::uint8_t>((value >> (i * 8U)) & 0xffU);
}

void put_u64(std::uint8_t* out, std::uint64_t value) noexcept
{
    for (unsigned i = 0; i < 8; ++i)
        out[i] = static_cast<std::uint8_t>((value >> (i * 8U)) & 0xffU);
}

std::uint16_t get_u16(const std::uint8_t* in) noexcept
{
    return static_cast<std::uint16_t>(
        static_cast<std::uint16_t>(in[0]) |
        (static_cast<std::uint16_t>(in[1]) << 8U));
}

std::uint32_t get_u32(const std::uint8_t* in) noexcept
{
    std::uint32_t value = 0;
    for (unsigned i = 0; i < 4; ++i)
        value |= static_cast<std::uint32_t>(in[i]) << (i * 8U);
    return value;
}

std::uint64_t get_u64(const std::uint8_t* in) noexcept
{
    std::uint64_t value = 0;
    for (unsigned i = 0; i < 8; ++i)
        value |= static_cast<std::uint64_t>(in[i]) << (i * 8U);
    return value;
}

bool is_invalid_handle(void* value) noexcept
{
    return value == nullptr || value == INVALID_HANDLE_VALUE;
}

Result map_error(std::uint32_t error) noexcept
{
    if (error == WAIT_TIMEOUT || error == ERROR_SEM_TIMEOUT)
        return Result::timed_out;
    if (error == ERROR_BROKEN_PIPE || error == ERROR_PIPE_NOT_CONNECTED ||
        error == ERROR_NO_DATA || error == ERROR_INVALID_HANDLE)
        return Result::disconnected;
    return Result::io_error;
}

class WipeBytes final {
public:
    explicit WipeBytes(std::vector<std::uint8_t>& bytes) noexcept : bytes_(bytes) {}
    ~WipeBytes()
    {
        if (!bytes_.empty())
            SecureZeroMemory(bytes_.data(), bytes_.size());
    }
    WipeBytes(const WipeBytes&) = delete;
    WipeBytes& operator=(const WipeBytes&) = delete;
private:
    std::vector<std::uint8_t>& bytes_;
};

Result transfer_exact(HANDLE pipe, std::span<std::uint8_t> bytes,
                      std::uint32_t timeout_ms, bool write,
                      std::uint32_t& last_error)
{
    // One absolute deadline covers all partial transfers; a peer cannot
    // extend a frame indefinitely by dribbling bytes before each timeout.
    const ULONGLONG started = GetTickCount64();
    std::size_t offset = 0;
    while (offset < bytes.size()) {
        const ULONGLONG elapsed = GetTickCount64() - started;
        if (elapsed >= timeout_ms) {
            last_error = WAIT_TIMEOUT;
            return Result::timed_out;
        }
        const DWORD remaining_timeout =
            static_cast<DWORD>(timeout_ms - elapsed);
        HANDLE event = CreateEventW(nullptr, TRUE, FALSE, nullptr);
        if (event == nullptr) {
            last_error = GetLastError();
            return Result::io_error;
        }

        OVERLAPPED overlapped{};
        overlapped.hEvent = event;
        const std::size_t remaining = bytes.size() - offset;
        const DWORD request = static_cast<DWORD>(
            (std::min)(remaining,
                static_cast<std::size_t>((std::numeric_limits<DWORD>::max)())));
        DWORD transferred = 0;
        const BOOL io_started = write
            ? WriteFile(pipe, bytes.data() + offset, request, &transferred, &overlapped)
            : ReadFile(pipe, bytes.data() + offset, request, &transferred, &overlapped);

        if (io_started == FALSE) {
            const DWORD start_error = GetLastError();
            if (start_error != ERROR_IO_PENDING) {
                last_error = start_error;
                CloseHandle(event);
                return map_error(start_error);
            }

            const DWORD wait = WaitForSingleObject(event, remaining_timeout);
            if (wait == WAIT_TIMEOUT) {
                (void)CancelIoEx(pipe, &overlapped);
                (void)WaitForSingleObject(event, INFINITE);
                DWORD ignored = 0;
                (void)GetOverlappedResult(pipe, &overlapped, &ignored, FALSE);
                last_error = WAIT_TIMEOUT;
                CloseHandle(event);
                return Result::timed_out;
            }
            if (wait != WAIT_OBJECT_0) {
                const DWORD wait_error = wait == WAIT_FAILED
                    ? GetLastError() : ERROR_GEN_FAILURE;
                (void)CancelIoEx(pipe, &overlapped);
                (void)WaitForSingleObject(event, INFINITE);
                DWORD ignored = 0;
                (void)GetOverlappedResult(pipe, &overlapped, &ignored, FALSE);
                last_error = wait_error;
                CloseHandle(event);
                return map_error(wait_error);
            }
            if (GetOverlappedResult(pipe, &overlapped, &transferred, FALSE) == FALSE) {
                const DWORD io_error = GetLastError();
                last_error = io_error;
                CloseHandle(event);
                return map_error(io_error);
            }
        }

        CloseHandle(event);
        if (transferred == 0) {
            last_error = ERROR_BROKEN_PIPE;
            return Result::disconnected;
        }
        offset += transferred;
    }
    return Result::ok;
}

} // namespace

bool FrameCodec::supported(std::uint16_t kind) noexcept
{
    return kind >= static_cast<std::uint16_t>(Kind::hello) &&
        kind <= static_cast<std::uint16_t>(Kind::ack);
}

bool FrameCodec::encode(const Frame& frame, std::vector<std::uint8_t>& output)
{
    if (!supported(frame.kind) || frame.payload.size() > maximum_payload)
        return false;

    output.assign(header_length + frame.payload.size(), 0);
    std::copy(magic.begin(), magic.end(), output.begin());
    put_u16(output.data() + 4, version);
    put_u16(output.data() + 6, frame.kind);
    put_u32(output.data() + 8,
        static_cast<std::uint32_t>(frame.payload.size()));
    put_u64(output.data() + 12, frame.session_id);
    put_u64(output.data() + 20, frame.generation);
    std::copy(frame.payload.begin(), frame.payload.end(),
        output.begin() + static_cast<std::ptrdiff_t>(header_length));
    return true;
}

bool FrameCodec::decode(std::span<const std::uint8_t> bytes, Frame& output)
{
    if (bytes.size() < header_length ||
        !std::equal(magic.begin(), magic.end(), bytes.begin()) ||
        get_u16(bytes.data() + 4) != version)
        return false;

    const std::uint16_t kind = get_u16(bytes.data() + 6);
    const std::uint32_t length = get_u32(bytes.data() + 8);
    if (!supported(kind) || length > maximum_payload ||
        bytes.size() != header_length + static_cast<std::size_t>(length))
        return false;

    Frame decoded{};
    decoded.kind = kind;
    decoded.session_id = get_u64(bytes.data() + 12);
    decoded.generation = get_u64(bytes.data() + 20);
    decoded.payload.assign(bytes.begin() + static_cast<std::ptrdiff_t>(header_length),
        bytes.end());
    output = std::move(decoded);
    return true;
}

bool FrameCodec::valid_pipe_name(std::wstring_view name) noexcept
{
    if (name.empty() || name.size() > 80) return false;
    for (const wchar_t ch : name) {
        if (!((ch >= L'a' && ch <= L'z') ||
              (ch >= L'0' && ch <= L'9') || ch == L'-'))
            return false;
    }
    return true;
}

Client::~Client()
{
    (void)disconnect();
}

Result Client::connect(std::wstring_view pipe_name,
                       std::span<const std::uint8_t> launch_secret,
                       std::uint32_t timeout_ms)
{
    std::lock_guard<std::mutex> guard(mutex_);
    if (!is_invalid_handle(pipe_)) return Result::busy;
    if (!FrameCodec::valid_pipe_name(pipe_name) ||
        launch_secret.size() != 32 ||
        timeout_ms < minimum_timeout_ms ||
        timeout_ms > maximum_timeout_ms)
        return Result::invalid;

    timeout_ms_ = timeout_ms;
    last_error_ = 0;
    const std::wstring path = L"\\\\.\\pipe\\" + std::wstring(pipe_name);
    const ULONGLONG started = GetTickCount64();
    HANDLE opened = INVALID_HANDLE_VALUE;

    for (;;) {
        opened = CreateFileW(path.c_str(), GENERIC_READ | GENERIC_WRITE, 0,
            nullptr, OPEN_EXISTING, FILE_FLAG_OVERLAPPED, nullptr);
        if (opened != INVALID_HANDLE_VALUE) break;

        const DWORD open_error = GetLastError();
        if (open_error != ERROR_PIPE_BUSY && open_error != ERROR_FILE_NOT_FOUND) {
            last_error_ = open_error;
            return map_win32_error(open_error);
        }

        const ULONGLONG elapsed = GetTickCount64() - started;
        if (elapsed >= timeout_ms_) {
            last_error_ = WAIT_TIMEOUT;
            return Result::timed_out;
        }
        const DWORD remaining = static_cast<DWORD>(timeout_ms_ - elapsed);
        if (open_error == ERROR_PIPE_BUSY) {
            if (WaitNamedPipeW(path.c_str(), remaining) == FALSE) {
                const DWORD wait_error = GetLastError();
                if (wait_error != ERROR_SEM_TIMEOUT &&
                    wait_error != ERROR_FILE_NOT_FOUND &&
                    wait_error != ERROR_PIPE_BUSY) {
                    last_error_ = wait_error;
                    return map_win32_error(wait_error);
                }
            }
        } else {
            Sleep((std::min)(remaining, static_cast<DWORD>(20)));
        }
    }

    pipe_ = opened;
    DWORD mode = PIPE_READMODE_BYTE;
    if (SetNamedPipeHandleState(static_cast<HANDLE>(pipe_), &mode,
            nullptr, nullptr) == FALSE) {
        const DWORD error = GetLastError();
        last_error_ = error;
        close_locked();
        return map_win32_error(error);
    }

    try {
        Frame hello{};
        hello.kind = static_cast<std::uint16_t>(Kind::hello);
        hello.payload.assign(launch_secret.begin(), launch_secret.end());
        [[maybe_unused]] WipeBytes wipe_hello(hello.payload);
        Result result = write_frame(hello);
        if (result != Result::ok) {
            close_locked();
            return result;
        }

        Frame response{};
        result = read_frame(response);
        if (result != Result::ok) {
            close_locked();
            return result;
        }
        if (response.kind != static_cast<std::uint16_t>(Kind::ack) ||
            response.session_id == 0 || response.generation == 0 ||
            !response.payload.empty()) {
            close_locked();
            return Result::protocol_error;
        }

        session_ = SessionToken{response.session_id, response.generation};
        return Result::ok;
    } catch (...) {
        close_locked();
        throw;
    }
}

Result Client::keep_alive()
{
    std::lock_guard<std::mutex> guard(mutex_);
    if (is_invalid_handle(pipe_) || session_.id == 0 ||
        session_.generation == 0)
        return Result::not_authenticated;

    try {
        Frame request{};
        request.kind = static_cast<std::uint16_t>(Kind::keep_alive);
        request.session_id = session_.id;
        request.generation = session_.generation;
        Result result = write_frame(request);
        if (result != Result::ok) {
            close_locked();
            return result;
        }

        Frame response{};
        result = read_frame(response);
        if (result != Result::ok) {
            close_locked();
            return result;
        }
        if (response.kind != static_cast<std::uint16_t>(Kind::ack) ||
            response.session_id != session_.id ||
            response.generation != session_.generation ||
            !response.payload.empty()) {
            close_locked();
            return Result::protocol_error;
        }
        return Result::ok;
    } catch (...) {
        close_locked();
        throw;
    }
}

Result Client::disconnect() noexcept
{
    std::lock_guard<std::mutex> guard(mutex_);
    if (is_invalid_handle(pipe_)) return Result::ok;

    Result result = Result::ok;
    try {
        if (session_.id != 0 && session_.generation != 0) {
            Frame goodbye{};
            goodbye.kind = static_cast<std::uint16_t>(Kind::goodbye);
            goodbye.session_id = session_.id;
            goodbye.generation = session_.generation;
            result = write_frame(goodbye);
        }
    } catch (...) {
        result = Result::io_error;
    }
    close_locked();
    return result;
}

bool Client::connected() const noexcept
{
    std::lock_guard<std::mutex> guard(mutex_);
    return !is_invalid_handle(pipe_) &&
        session_.id != 0 && session_.generation != 0;
}

SessionToken Client::session() const noexcept
{
    std::lock_guard<std::mutex> guard(mutex_);
    return session_;
}

std::uint32_t Client::last_error() const noexcept
{
    std::lock_guard<std::mutex> guard(mutex_);
    return last_error_;
}

Result Client::write_frame(const Frame& frame)
{
    std::vector<std::uint8_t> bytes;
    [[maybe_unused]] WipeBytes wipe(bytes);
    if (!FrameCodec::encode(frame, bytes)) return Result::protocol_error;
    return write_exact(bytes);
}

Result Client::read_frame(Frame& frame)
{
    std::array<std::uint8_t, FrameCodec::header_length> header{};
    Result result = read_exact(header);
    if (result != Result::ok) return result;
    if (!std::equal(magic.begin(), magic.end(), header.begin()) ||
        get_u16(header.data() + 4) != FrameCodec::version ||
        !FrameCodec::supported(get_u16(header.data() + 6)))
        return Result::protocol_error;

    const std::uint32_t length = get_u32(header.data() + 8);
    // This client consumes only server ACKs. ACKs must have no payload,
    // so reject unexpected data before allocating or reading a body.
    if (get_u16(header.data() + 6) != static_cast<std::uint16_t>(Kind::ack) ||
        length != 0)
        return Result::protocol_error;
    return FrameCodec::decode(header, frame)
        ? Result::ok : Result::protocol_error;
}

Result Client::write_exact(std::span<const std::uint8_t> bytes)
{
    std::span<std::uint8_t> writable(
        const_cast<std::uint8_t*>(bytes.data()), bytes.size());
    return transfer_exact(static_cast<HANDLE>(pipe_), writable,
        timeout_ms_, true, last_error_);
}

Result Client::read_exact(std::span<std::uint8_t> bytes)
{
    return transfer_exact(static_cast<HANDLE>(pipe_), bytes,
        timeout_ms_, false, last_error_);
}

void Client::close_locked() noexcept
{
    if (!is_invalid_handle(pipe_))
        CloseHandle(static_cast<HANDLE>(pipe_));
    pipe_ = nullptr;
    session_ = SessionToken{};
}

Result Client::map_win32_error(std::uint32_t error) noexcept
{
    return map_error(error);
}

} // namespace virtualcar::ipc
