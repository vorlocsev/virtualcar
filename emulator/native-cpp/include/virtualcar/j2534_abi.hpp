#pragma once
// Windows J2534 PassThru v04.04 ABI declarations for the NEW C++20 adapter.
// This header defines layout and signatures ONLY. No exports, synthetic ECU
// replies, or working client DLL are implemented at migration stage M0.

#include <cstddef>
#include <cstdint>
#include <type_traits>

#if defined(_WIN32) && (defined(_M_IX86) || defined(__i386__))
#  if defined(_MSC_VER)
#    define VC_J2534_CALL __stdcall
#  else
#    define VC_J2534_CALL __attribute__((stdcall))
#  endif
#else
#  define VC_J2534_CALL
#endif

namespace virtualcar::j2534 {

using DWORD = std::uint32_t;

#pragma pack(push, 1)
struct PASSTHRU_MSG {
    DWORD ProtocolID;
    DWORD RxStatus;
    DWORD TxFlags;
    DWORD Timestamp;
    DWORD DataSize;
    DWORD ExtraDataIndex;
    std::uint8_t Data[4128];
};
#pragma pack(pop)

// All clients and native shims use these signatures. The eventual
// x86/x64 DLLs must export *undecorated* PassThru names, verified separately.
using Open = DWORD (VC_J2534_CALL *)(void*, DWORD*);
using Close = DWORD (VC_J2534_CALL *)(DWORD);
using Connect = DWORD (VC_J2534_CALL *)(DWORD, DWORD, DWORD, DWORD, DWORD*);
using Disconnect = DWORD (VC_J2534_CALL *)(DWORD);
using ReadMsgs = DWORD (VC_J2534_CALL *)(DWORD, PASSTHRU_MSG*, DWORD*, DWORD);
using WriteMsgs = DWORD (VC_J2534_CALL *)(DWORD, PASSTHRU_MSG*, DWORD*, DWORD);
using StartPeriodicMsg = DWORD (VC_J2534_CALL *)(DWORD, PASSTHRU_MSG*, DWORD*, DWORD*);
using StopPeriodicMsg = DWORD (VC_J2534_CALL *)(DWORD, DWORD);
using StartMsgFilter = DWORD (VC_J2534_CALL *)(DWORD, DWORD, PASSTHRU_MSG*,
                                              PASSTHRU_MSG*, PASSTHRU_MSG*, DWORD*);
using StopMsgFilter = DWORD (VC_J2534_CALL *)(DWORD, DWORD);
using SetProgrammingVoltage = DWORD (VC_J2534_CALL *)(DWORD, DWORD, DWORD);
using ReadVersion = DWORD (VC_J2534_CALL *)(DWORD, char*, char*, char*);
using GetLastError = DWORD (VC_J2534_CALL *)(char*);
using Ioctl = DWORD (VC_J2534_CALL *)(DWORD, DWORD, void*, void*);

constexpr std::size_t PassThruDataCapacity = 4128;
constexpr std::size_t PassThruMsgBytes = 6 * sizeof(DWORD) + PassThruDataCapacity;

static_assert(sizeof(DWORD) == 4);
static_assert(sizeof(PASSTHRU_MSG) == 4152);
static_assert(offsetof(PASSTHRU_MSG, Data) == 24);
static_assert(offsetof(PASSTHRU_MSG, DataSize) == 16);
static_assert(alignof(PASSTHRU_MSG) == 1);
static_assert(std::is_standard_layout_v<PASSTHRU_MSG>);
static_assert(std::is_trivially_copyable_v<PASSTHRU_MSG>);

} // namespace virtualcar::j2534
