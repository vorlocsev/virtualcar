// M3 Windows-only executable, built and run separately as x86 and x64.
// Eight independent J2534 ABI/loader/fail-closed checks. Never connect to a car.
#include "virtualcar/j2534_abi.hpp"

#include <Windows.h>
#include <array>
#include <atomic>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <thread>

namespace abi = virtualcar::j2534;

struct Api {
    abi::Open open{};
    abi::Close close{};
    abi::Connect connect{};
    abi::Disconnect disconnect{};
    abi::ReadMsgs read{};
    abi::WriteMsgs write{};
    abi::StartPeriodicMsg start_periodic{};
    abi::StopPeriodicMsg stop_periodic{};
    abi::StartMsgFilter start_filter{};
    abi::StopMsgFilter stop_filter{};
    abi::SetProgrammingVoltage voltage{};
    abi::ReadVersion version{};
    abi::GetLastError last_error{};
    abi::Ioctl ioctl{};
};

constexpr abi::DWORD kOk = 0U;
constexpr abi::DWORD kUnsupported = 1U;
constexpr abi::DWORD kNull = 4U;
constexpr abi::DWORD kNotConnected = 8U;

bool load_exports(HMODULE library, Api& api) {
    auto lookup = [library](const char* name) { return GetProcAddress(library, name); };
    api.open = reinterpret_cast<abi::Open>(lookup("PassThruOpen"));
    api.close = reinterpret_cast<abi::Close>(lookup("PassThruClose"));
    api.connect = reinterpret_cast<abi::Connect>(lookup("PassThruConnect"));
    api.disconnect = reinterpret_cast<abi::Disconnect>(lookup("PassThruDisconnect"));
    api.read = reinterpret_cast<abi::ReadMsgs>(lookup("PassThruReadMsgs"));
    api.write = reinterpret_cast<abi::WriteMsgs>(lookup("PassThruWriteMsgs"));
    api.start_periodic = reinterpret_cast<abi::StartPeriodicMsg>(lookup("PassThruStartPeriodicMsg"));
    api.stop_periodic = reinterpret_cast<abi::StopPeriodicMsg>(lookup("PassThruStopPeriodicMsg"));
    api.start_filter = reinterpret_cast<abi::StartMsgFilter>(lookup("PassThruStartMsgFilter"));
    api.stop_filter = reinterpret_cast<abi::StopMsgFilter>(lookup("PassThruStopMsgFilter"));
    api.voltage = reinterpret_cast<abi::SetProgrammingVoltage>(lookup("PassThruSetProgrammingVoltage"));
    api.version = reinterpret_cast<abi::ReadVersion>(lookup("PassThruReadVersion"));
    api.last_error = reinterpret_cast<abi::GetLastError>(lookup("PassThruGetLastError"));
    api.ioctl = reinterpret_cast<abi::Ioctl>(lookup("PassThruIoctl"));

    const bool all = api.open && api.close && api.connect && api.disconnect &&
        api.read && api.write && api.start_periodic && api.stop_periodic &&
        api.start_filter && api.stop_filter && api.voltage && api.version &&
        api.last_error && api.ioctl;
    if (!all) return false;

    // 32-bit clients must see undecorated J2534 names, not _Foo@N names.
    if constexpr (sizeof(void*) == 4) {
        if (lookup("_PassThruOpen@8") != nullptr) return false;
    }
    return true;
}

bool group02(const Api& a) {
    abi::DWORD device = 0xdeadbeefU;
    if (a.open(nullptr, nullptr) != kNull) return false;
    if (a.open(nullptr, &device) != kNotConnected || device != 0U) return false;
    device = 12345U;
    return a.open(nullptr, &device) == kNotConnected && device == 0U;
}

bool group03(const Api& a) {
    abi::DWORD channel = 0xffff'ffffU;
    if (a.connect(0, 5U, 0U, 500000U, nullptr) != kNull) return false;
    if (a.connect(0, 5U, 0U, 500000U, &channel) != kNotConnected || channel != 0U)
        return false;
    return a.close(111U) == kNotConnected &&
           a.disconnect(222U) == kNotConnected;
}

bool group04(const Api& a) {
    abi::PASSTHRU_MSG msg{};
    msg.ProtocolID = 5U;
    msg.DataSize = 4U;
    msg.Data[0] = 0x44U;
    abi::DWORD count = 17U;
    if (a.read(0, &msg, nullptr, 300U) != kNull) return false;
    if (a.read(0, nullptr, &count, 300U) != kNull || count != 0U) return false;
    count = 17U;
    return a.read(0, &msg, &count, 300U) == kNotConnected &&
        count == 0U && msg.Data[0] == 0x44U && msg.DataSize == 4U;
}

bool group05(const Api& a) {
    abi::PASSTHRU_MSG msg{};
    msg.ProtocolID = 5U;
    // A write-like payload must never be forwarded or acknowledged.
    msg.DataSize = 3U;
    msg.Data[0] = 0x2eU;
    msg.Data[1] = 0xf1U;
    msg.Data[2] = 0x90U;
    abi::DWORD count = 9U;
    if (a.write(0, &msg, nullptr, 0U) != kNull) return false;
    if (a.write(0, nullptr, &count, 0U) != kNull || count != 0U) return false;
    count = 9U;
    return a.write(0, &msg, &count, 0U) == kUnsupported &&
        count == 0U && msg.Data[0] == 0x2eU;
}

bool group06(const Api& a) {
    abi::PASSTHRU_MSG mask{}, pattern{}, flow{};
    abi::DWORD periodic = 55U;
    abi::DWORD filter = 99U;
    if (a.start_periodic(0, &pattern, nullptr, 1000U) != kNull) return false;
    if (a.start_periodic(0, nullptr, &periodic, 1000U) != kNull || periodic != 0U)
        return false;
    periodic = 55U;
    if (a.start_periodic(0, &pattern, &periodic, 1000U) != kUnsupported || periodic != 0U)
        return false;
    if (a.stop_periodic(0, 1U) != kNotConnected) return false;
    if (a.start_filter(0, 1U, &mask, &pattern, &flow, nullptr) != kNull) return false;
    if (a.start_filter(0, 1U, &mask, &pattern, &flow, &filter) != kUnsupported ||
        filter != 0U) return false;
    return a.stop_filter(0, 1U) == kNotConnected;
}

bool group07(const Api& a) {
    char fw[4] = "A";
    char dll[4] = "B";
    char ver[4] = "C";
    if (a.version(0, nullptr, dll, ver) != kNull) return false;
    if (a.version(0, fw, dll, ver) != kNotConnected) return false;
    if (std::strcmp(fw, "A") || std::strcmp(dll, "B") || std::strcmp(ver, "C"))
        return false;
    return a.voltage(0, 6U, 12000U) == kUnsupported &&
        a.ioctl(0, 2U, nullptr, nullptr) == kUnsupported;
}

bool group08(const Api& a) {
    if (a.ioctl(0, 1U, nullptr, nullptr) != kUnsupported) return false;
    char main_buffer[80]{};
    if (a.last_error(main_buffer) != kOk ||
        std::strstr(main_buffer, "unavailable") == nullptr ||
        std::strlen(main_buffer) >= 80U) return false;
    std::atomic<bool> other_ok{false};
    std::thread worker([&]() {
        abi::DWORD device = 7U;
        char other_error[80]{};
        other_ok.store(
            a.open(nullptr, &device) == kNotConnected && device == 0U &&
            a.last_error(other_error) == kOk &&
            std::strstr(other_error, "not connected") != nullptr);
    });
    worker.join();
    char still_main[80]{};
    if (a.last_error(still_main) != kOk ||
        std::strcmp(main_buffer, still_main) != 0 ||
        !other_ok.load()) return false;
    return a.last_error(nullptr) == kNull;
}

int main(int argc, char** argv) {
    if (argc != 2) {
        std::fputs("Expected absolute path to private M3 native DLL\n", stderr);
        return 2;
    }

    const auto path = std::filesystem::absolute(argv[1]).wstring();
    HMODULE dll = LoadLibraryExW(path.c_str(), nullptr, LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR);
    if (!dll) {
        std::fputs("FAIL: M3 DLL not loadable in matching-bitness process\n", stderr);
        return 1;
    }
    Api api{};
    int passed = 0;

    auto report = [&](const char* title, bool ok) {
        std::printf("%s %s\n", ok ? "PASS" : "FAIL", title);
        if (ok) ++passed;
    };
    const bool exports_ok = load_exports(dll, api);
    report("01 exact 14 undecorated J2534 exports", exports_ok);
    if (exports_ok) {
        report("02 fail-closed open and zero device ID", group02(api));
        report("03 fail-closed channel lifecycle", group03(api));
        report("04 RX queue is disconnected and count zero", group04(api));
        report("05 write requests are refused with no TX", group05(api));
        report("06 filters and periodic TX are unavailable", group06(api));
        report("07 voltage, ioctl and version cannot claim capabilities", group07(api));
        report("08 bounded, thread-local J2534 error messages", group08(api));
    }

    FreeLibrary(dll);
    std::printf("VirtualCar M3 native %zu-bit checks: %d/8\n", sizeof(void*) * 8U, passed);
    return passed == 8 ? 0 : 1;
}
