// Virtual Car M3: native Windows C++20 J2534 v04.04 ABI boundary.
// This DLL deliberately DOES NOT open a vehicle, start a CAN channel,
// transmit bytes, simulate an ECU, contact IPC, or access hardware.
// It must not be registered as a functional PassThru adapter.
// M4/M5 will add bounded CAN/ISO-TP transport and authenticated host IPC
// only after separate regression evidence.

#include "virtualcar/j2534_abi.hpp"

#include <cstring>

namespace {
using DWORD32 = virtualcar::j2534::DWORD;
using MSG = virtualcar::j2534::PASSTHRU_MSG;

constexpr DWORD32 kOk = 0U;
constexpr DWORD32 kNotSupported = 1U;
constexpr DWORD32 kNullParameter = 4U;
constexpr DWORD32 kNotConnected = 8U;

// Error is per-thread so separate diagnostic clients don't contaminate
// one another's PassThruGetLastError summaries. No secrets are recorded.
thread_local DWORD32 t_error = kOk;

DWORD32 fail(DWORD32 code) noexcept
{
    t_error = code;
    return code;
}
const char* error_message(DWORD32 code) noexcept
{
    switch (code) {
        case kOk: return "No error";
        case kNullParameter: return "Null J2534 parameter";
        case kNotSupported: return "Virtual Car lab operation unavailable";
        case kNotConnected: return "Virtual Car lab service not connected";
        default: return "Virtual Car lab operation failed";
    }
}
} // namespace

extern "C" {

DWORD32 VC_J2534_CALL PassThruOpen(void* /*name*/, DWORD32* device_id) noexcept
{
    if (device_id == nullptr) return fail(kNullParameter);
    *device_id = 0U;
    return fail(kNotConnected);
}

DWORD32 VC_J2534_CALL PassThruClose(DWORD32 /*device_id*/) noexcept
{
    return fail(kNotConnected);
}

DWORD32 VC_J2534_CALL PassThruConnect(
    DWORD32 /*device_id*/, DWORD32 /*protocol_id*/, DWORD32 /*flags*/,
    DWORD32 /*baudrate*/, DWORD32* channel_id) noexcept
{
    if (channel_id == nullptr) return fail(kNullParameter);
    *channel_id = 0U;
    return fail(kNotConnected);
}

DWORD32 VC_J2534_CALL PassThruDisconnect(DWORD32 /*channel_id*/) noexcept
{
    return fail(kNotConnected);
}

DWORD32 VC_J2534_CALL PassThruReadMsgs(
    DWORD32 /*channel_id*/, MSG* messages, DWORD32* count, DWORD32 /*timeout*/) noexcept
{
    if (count == nullptr) return fail(kNullParameter);
    *count = 0U;
    if (messages == nullptr) return fail(kNullParameter);
    return fail(kNotConnected);
}

DWORD32 VC_J2534_CALL PassThruWriteMsgs(
    DWORD32 /*channel_id*/, MSG* messages, DWORD32* count, DWORD32 /*timeout*/) noexcept
{
    if (count == nullptr) return fail(kNullParameter);
    *count = 0U;
    if (messages == nullptr) return fail(kNullParameter);
    // Even if a caller sends unsafe or malformed bytes, never transmit.
    return fail(kNotSupported);
}

DWORD32 VC_J2534_CALL PassThruStartPeriodicMsg(
    DWORD32 /*channel_id*/, MSG* message, DWORD32 /*time_interval*/, DWORD32* message_id) noexcept
{
    if (message_id == nullptr) return fail(kNullParameter);
    *message_id = 0U;
    if (message == nullptr) return fail(kNullParameter);
    return fail(kNotSupported);
}

DWORD32 VC_J2534_CALL PassThruStopPeriodicMsg(
    DWORD32 /*channel_id*/, DWORD32 /*message_id*/) noexcept
{
    return fail(kNotConnected);
}

DWORD32 VC_J2534_CALL PassThruStartMsgFilter(
    DWORD32 /*channel_id*/, DWORD32 /*filter_type*/, MSG* mask,
    MSG* pattern, MSG* /*flow_control*/, DWORD32* filter_id) noexcept
{
    if (filter_id == nullptr) return fail(kNullParameter);
    *filter_id = 0U;
    if (mask == nullptr || pattern == nullptr) return fail(kNullParameter);
    return fail(kNotSupported);
}

DWORD32 VC_J2534_CALL PassThruStopMsgFilter(
    DWORD32 /*channel_id*/, DWORD32 /*filter_id*/) noexcept
{
    return fail(kNotConnected);
}

DWORD32 VC_J2534_CALL PassThruSetProgrammingVoltage(
    DWORD32 /*device_id*/, DWORD32 /*pin*/, DWORD32 /*voltage*/) noexcept
{
    // Never enable ECU flashing / programming through this test adapter.
    return fail(kNotSupported);
}

DWORD32 VC_J2534_CALL PassThruReadVersion(
    DWORD32 /*device_id*/, char* firmware, char* dll, char* api) noexcept
{
    if (firmware == nullptr || dll == nullptr || api == nullptr)
        return fail(kNullParameter);
    // Without an open device, do not imply a firmware/API capability.
    // Out buffers intentionally remain untouched on error.
    return fail(kNotConnected);
}

DWORD32 VC_J2534_CALL PassThruGetLastError(char* description) noexcept
{
    if (description == nullptr) return fail(kNullParameter);
    // J2534 PassThruGetLastError expects an 80-byte caller buffer.
    // Each message is constant, ASCII and <80 bytes including its NUL.
    const char* message = error_message(t_error);
    std::memcpy(description, message, std::strlen(message) + 1U);
    return kOk;
}

DWORD32 VC_J2534_CALL PassThruIoctl(
    DWORD32 /*channel_id*/, DWORD32 /*ioctl_id*/, void* /*input*/, void* /*output*/) noexcept
{
    // No hidden writes, voltage, reset, or physical I/O operations.
    return fail(kNotSupported);
}

} // extern "C"
