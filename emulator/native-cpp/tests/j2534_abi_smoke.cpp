// Pure compile-time and host-side J2534 layout smoke check. This is NOT a DLL
// loading test, not native x86/x64 Windows API acceptance, and not a car test.
#include "virtualcar/j2534_abi.hpp"
#include <cstdio>
#include <type_traits>

using namespace virtualcar::j2534;
static_assert(sizeof(PASSTHRU_MSG) == PassThruMsgBytes);
static_assert(sizeof(PASSTHRU_MSG::Data) == PassThruDataCapacity);
static_assert(std::is_same_v<DWORD, std::uint32_t>);
static_assert(std::is_pointer_v<Open>);
static_assert(std::is_pointer_v<Connect>);
static_assert(std::is_pointer_v<ReadMsgs>);
static_assert(std::is_pointer_v<StartMsgFilter>);

int main()
{
    PASSTHRU_MSG msg{};
    msg.ProtocolID = 5u; // J2534 CAN, structure test only.
    msg.DataSize = 4u;
    msg.Data[0] = 0x11u;
    if (msg.ProtocolID != 5u || msg.DataSize != 4u ||
        msg.Data[0] != 0x11u || sizeof(msg) != 4152u) {
        return 1;
    }
    std::puts("PASS: C++20 J2534 ABI structure contract (host only)");
    return 0;
}
