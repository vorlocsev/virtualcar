// M4B-2: REAL black-box comparison of the independently built legacy
// 32-bit C J2534 DLL and the isolated C++20 ISO15765 RX engine.
// Input: identical independently specified read-only synthetic DID traces.
// Output: compare every J2534 field and payload byte, except dynamic
// microsecond Timestamp; never feed legacy output as new-engine input.
// No physical adapters, registry edits, OEM identities or public artifacts.
#include "virtualcar/isotp_rx.hpp"

#include <Windows.h>
#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <span>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace fs = std::filesystem;
namespace j = virtualcar::j2534;
namespace tr = virtualcar::transport;
using Msg = j::PASSTHRU_MSG;
using Dword = j::DWORD;

namespace {
constexpr tr::Route ecu_a{0x7e0U, 0x7e8U, 500000U, false};
constexpr tr::Route ecu_b{0x7e1U, 0x7e9U, 500000U, false};
constexpr std::array<std::uint8_t, 3> did_part{0x22, 0xf1, 0x87};
constexpr std::array<std::uint8_t, 3> did_sw{0x22, 0xf1, 0x89};
constexpr Dword ok = 0U;
constexpr Dword empty = 16U;

std::vector<std::uint8_t> expected(std::uint8_t did, std::string_view label)
{
    std::vector<std::uint8_t> data{0x62U, 0xf1U, did};
    for (const char c : label) data.push_back(static_cast<std::uint8_t>(c));
    return data;
}

Msg id_message(std::uint32_t id)
{
    Msg msg{};
    msg.ProtocolID = 6U;
    msg.DataSize = 4U;
    msg.Data[0] = static_cast<std::uint8_t>(id >> 24U);
    msg.Data[1] = static_cast<std::uint8_t>(id >> 16U);
    msg.Data[2] = static_cast<std::uint8_t>(id >> 8U);
    msg.Data[3] = static_cast<std::uint8_t>(id);
    return msg;
}

struct Legacy {
    HMODULE lib{};
    j::Open open{};
    j::Close close{};
    j::Connect connect{};
    j::Disconnect disconnect{};
    j::ReadMsgs read{};
    j::WriteMsgs write{};
    j::StartMsgFilter filter{};
    j::StopMsgFilter stop_filter{};
    Dword device{};
    bool opened{};
    std::vector<Dword> channels;

    ~Legacy()
    {
        if (disconnect)
            for (const Dword channel : channels) (void)disconnect(channel);
        if (opened && close) (void)close(device);
        if (lib) FreeLibrary(lib);
    }

    bool load(const fs::path& path)
    {
        lib = LoadLibraryExW(path.c_str(), nullptr, LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR);
        if (!lib) return false;
        const auto symbol = [this](const char* name) {
            return GetProcAddress(lib, name);
        };
        open = reinterpret_cast<j::Open>(symbol("PassThruOpen"));
        close = reinterpret_cast<j::Close>(symbol("PassThruClose"));
        connect = reinterpret_cast<j::Connect>(symbol("PassThruConnect"));
        disconnect = reinterpret_cast<j::Disconnect>(symbol("PassThruDisconnect"));
        read = reinterpret_cast<j::ReadMsgs>(symbol("PassThruReadMsgs"));
        write = reinterpret_cast<j::WriteMsgs>(symbol("PassThruWriteMsgs"));
        filter = reinterpret_cast<j::StartMsgFilter>(symbol("PassThruStartMsgFilter"));
        stop_filter = reinterpret_cast<j::StopMsgFilter>(symbol("PassThruStopMsgFilter"));
        if (!(open && close && connect && disconnect && read && write &&
              filter && stop_filter))
            return false;
        if (open(nullptr, &device) != ok || device == 0U) return false;
        opened = true;
        return true;
    }

    Dword channel()
    {
        Dword id = 0;
        if (!opened || connect(device, 6U, 0U, 500000U, &id) != ok)
            return 0;
        channels.push_back(id);
        return id;
    }

    bool close_channel(Dword channel_id)
    {
        if (disconnect(channel_id) != ok) return false;
        const auto it = std::find(channels.begin(), channels.end(), channel_id);
        if (it != channels.end()) channels.erase(it);
        return true;
    }

    // The synthetic fixture source is explicit and independent of old outputs.
    bool install(Dword channel_id, std::uint32_t rx, std::uint32_t tx,
                 std::uint32_t mask_id = 0xffffffffU,
                 std::uint32_t override_flow = 0xffffffffU)
    {
        Msg mask = id_message(mask_id);
        Msg pattern = id_message(rx & mask_id);
        Msg flow = id_message(override_flow == 0xffffffffU ? tx : override_flow);
        Dword filter_id = 0;
        return filter(channel_id, 3U, &mask, &pattern, &flow, &filter_id) == ok &&
            filter_id != 0U;
    }

    bool send(Dword channel_id, std::uint32_t request_id,
              std::span<const std::uint8_t> uds)
    {
        if (uds.empty() || uds.size() > 32U) return false;
        Msg m = id_message(request_id);
        m.DataSize = static_cast<Dword>(uds.size() + 4U);
        std::copy(uds.begin(), uds.end(), m.Data + 4);
        Dword n = 1U;
        return write(channel_id, &m, &n, 10U) == ok && n == 1U;
    }

    bool drain(Dword channel_id, std::vector<Msg>& messages)
    {
        messages.clear();
        for (std::size_t attempt = 0; attempt < 130U; ++attempt) {
            Msg result{};
            Dword count = 1U;
            const Dword status = read(channel_id, &result, &count, 0U);
            if (status == empty && count == 0U) return true;
            if (status != ok || count != 1U || result.DataSize > 4128U)
                return false;
            messages.push_back(result);
        }
        return false; // Never accept a perpetually producing queue.
    }
};

bool configure(tr::Iso15765Rx& fresh, tr::Route route,
               std::uint32_t mask = 0xffffffffU)
{
    return fresh.add_route(route) == tr::Result::ok &&
        fresh.bind_flow_filter(fresh.route_count() - 1,
            mask, route.response_id & mask, route.request_id) == tr::Result::ok;
}

bool emit(tr::Iso15765Rx& fresh, std::size_t owner,
          std::span<const std::uint8_t> bytes)
{
    return fresh.emit_verified_readonly_reply(owner, bytes, true, 1234567U)
        == tr::Result::ok;
}

bool collect(tr::Iso15765Rx& fresh, std::vector<Msg>& output)
{
    output.clear();
    Msg m{};
    std::size_t owner{};
    while (fresh.pop(m, owner)) {
        if (output.size() >= 130U || owner >= fresh.route_count())
            return false;
        output.push_back(m);
    }
    return true;
}

bool equal_message(const Msg& actual, const Msg& expected)
{
    // Only volatile microsecond Timestamp is normalized. Dynamic device/
    // channel/filter handles never appear in these output structures.
    return actual.ProtocolID == expected.ProtocolID &&
        actual.RxStatus == expected.RxStatus &&
        actual.TxFlags == expected.TxFlags &&
        actual.DataSize == expected.DataSize &&
        actual.ExtraDataIndex == expected.ExtraDataIndex &&
        actual.DataSize <= 4128U &&
        std::equal(actual.Data, actual.Data + actual.DataSize, expected.Data);
}
bool equal_messages(const std::vector<Msg>& old_messages,
                    const std::vector<Msg>& new_messages)
{
    if (old_messages.size() != new_messages.size()) return false;
    for (std::size_t i = 0; i < old_messages.size(); ++i)
        if (!equal_message(old_messages[i], new_messages[i])) return false;
    return true;
}

bool group01_short_positive(Legacy& old)
{
    const Dword channel = old.channel();
    tr::Iso15765Rx fresh;
    if (!channel || !old.install(channel, ecu_a.response_id, ecu_a.request_id) ||
        !configure(fresh, ecu_a) || !old.send(channel, ecu_a.request_id, did_part) ||
        !emit(fresh, 0, expected(0x87U, "LAB-A"))) return false;
    std::vector<Msg> a, b;
    return old.drain(channel, a) && collect(fresh, b) &&
        a.size() == 1U && equal_messages(a, b);
}

bool group02_long_with_start(Legacy& old)
{
    const Dword channel = old.channel();
    tr::Iso15765Rx fresh;
    if (!channel || !old.install(channel, ecu_a.response_id, ecu_a.request_id) ||
        !configure(fresh, ecu_a) || !old.send(channel, ecu_a.request_id, did_sw) ||
        !emit(fresh, 0, expected(0x89U, "LAB-LONG-SYNTHETIC-ENGINE")))
        return false;
    std::vector<Msg> a, b;
    return old.drain(channel, a) && collect(fresh, b) &&
        a.size() == 2U && equal_messages(a, b) &&
        a[0].RxStatus == tr::Iso15765Rx::start_of_message &&
        a[0].DataSize == 4U && a[0].ExtraDataIndex == 0U &&
        a[1].ExtraDataIndex == a[1].DataSize;
}

bool group03_two_ecu(Legacy& old)
{
    const Dword channel = old.channel();
    tr::Iso15765Rx fresh;
    if (!channel || !old.install(channel, ecu_a.response_id, ecu_a.request_id) ||
        !old.install(channel, ecu_b.response_id, ecu_b.request_id) ||
        !configure(fresh, ecu_a) || !configure(fresh, ecu_b))
        return false;
    if (!old.send(channel, ecu_a.request_id, did_part) ||
        !old.send(channel, ecu_b.request_id, did_part) ||
        !emit(fresh, 0, expected(0x87U, "LAB-A")) ||
        !emit(fresh, 1, expected(0x87U, "LAB-B")))
        return false;
    std::vector<Msg> a, b;
    return old.drain(channel, a) && collect(fresh, b) &&
        a.size() == 2U && equal_messages(a, b);
}

bool group04_channel_isolation(Legacy& old)
{
    const Dword with_filter = old.channel();
    const Dword without_filter = old.channel();
    tr::Iso15765Rx fresh_allowed, fresh_blocked;
    if (!with_filter || !without_filter ||
        !old.install(with_filter, ecu_a.response_id, ecu_a.request_id) ||
        !configure(fresh_allowed, ecu_a) ||
        fresh_blocked.add_route(ecu_a) != tr::Result::ok)
        return false;
    if (!old.send(with_filter, ecu_a.request_id, did_part) ||
        !old.send(without_filter, ecu_a.request_id, did_part) ||
        !emit(fresh_allowed, 0, expected(0x87U, "LAB-A")) ||
        fresh_blocked.emit_verified_readonly_reply(0,
            expected(0x87U, "LAB-A"), false, 0U) != tr::Result::blocked)
        return false;
    std::vector<Msg> a, b, c, d;
    return old.drain(with_filter, a) && old.drain(without_filter, b) &&
        collect(fresh_allowed, c) && collect(fresh_blocked, d) &&
        a.size() == 1U && b.empty() && d.empty() && equal_messages(a, c);
}

bool group05_broad_filter(Legacy& old)
{
    const Dword channel = old.channel();
    tr::Iso15765Rx fresh;
    constexpr std::uint32_t broad = 0xfffffff0U;
    if (!channel || !old.install(channel, ecu_a.response_id, ecu_a.request_id, broad) ||
        !configure(fresh, ecu_a, broad) ||
        !old.send(channel, ecu_a.request_id, did_part) ||
        !old.send(channel, ecu_a.request_id, did_sw) ||
        !emit(fresh, 0, expected(0x87U, "LAB-A")) ||
        fresh.emit_verified_readonly_reply(
            0, expected(0x89U, "LAB-LONG-SYNTHETIC-ENGINE"), true, 1U)
            != tr::Result::blocked)
        return false;
    std::vector<Msg> a, b;
    return old.drain(channel, a) && collect(fresh, b) &&
        a.size() == 1U && equal_messages(a, b);
}

bool group06_wrong_flow(Legacy& old)
{
    const Dword channel = old.channel();
    tr::Iso15765Rx fresh;
    if (!channel ||
        !old.install(channel, ecu_a.response_id, ecu_a.request_id,
                     0xffffffffU, 0x7e2U) ||
        fresh.add_route(ecu_a) != tr::Result::ok ||
        fresh.bind_flow_filter(0, 0xffffffffU, ecu_a.response_id, 0x7e2U)
            != tr::Result::invalid ||
        !old.send(channel, ecu_a.request_id, did_sw))
        return false;
    std::vector<Msg> a, b;
    return old.drain(channel, a) && collect(fresh, b) &&
        a.empty() && b.empty();
}

bool group07_atomic_full_fifo(Legacy& old)
{
    const Dword channel = old.channel();
    tr::Iso15765Rx fresh;
    if (!channel || !old.install(channel, ecu_a.response_id, ecu_a.request_id) ||
        !configure(fresh, ecu_a)) return false;
    const auto short_reply = expected(0x87U, "LAB-A");
    for (std::size_t i = 0; i < 63U; ++i) {
        if (!old.send(channel, ecu_a.request_id, did_part) ||
            !emit(fresh, 0, short_reply)) return false;
    }
    if (!old.send(channel, ecu_a.request_id, did_sw) ||
        fresh.emit_verified_readonly_reply(0,
            expected(0x89U, "LAB-LONG-SYNTHETIC-ENGINE"),
            true, 2U) != tr::Result::queue_full ||
        fresh.queued() != 63U || fresh.dropped() != 1U)
        return false;

    std::vector<Msg> a, b;
    return old.drain(channel, a) && collect(fresh, b) &&
        a.size() == 63U && equal_messages(a, b);
}

bool group08_disconnect_reset(Legacy& old)
{
    const Dword channel = old.channel();
    tr::Iso15765Rx fresh;
    if (!channel || !old.install(channel, ecu_a.response_id, ecu_a.request_id) ||
        !configure(fresh, ecu_a) ||
        !old.send(channel, ecu_a.request_id, did_part) ||
        !emit(fresh, 0, expected(0x87U, "LAB-A")))
        return false;
    const auto generation = fresh.generation();
    if (!old.close_channel(channel)) return false;
    fresh.reset();
    if (fresh.generation() == generation || fresh.queued() != 0U)
        return false;
    const Dword next_channel = old.channel();
    if (!next_channel || !old.send(next_channel, ecu_a.request_id, did_part))
        return false;
    std::vector<Msg> a, b;
    return old.drain(next_channel, a) && collect(fresh, b) &&
        a.empty() && b.empty();
}

bool create_lab(const fs::path& old_path, const fs::path& lab_dir,
                fs::path& copied)
{
    if (fs::exists(lab_dir) || !fs::exists(old_path)) return false;
    if (!fs::create_directory(lab_dir)) return false;
    copied = lab_dir / L"VirtualCarJ2534.dll";
    fs::copy_file(old_path, copied, fs::copy_options::none);

    // Deliberately omit VIN and CEM identity. All test replies are
    // independently specified read-only synthetic ECM DID labels.
    std::ofstream config(lab_dir / L"virtualcar.ini",
                         std::ios::out | std::ios::binary | std::ios::trunc);
    config <<
        "; Synthetic executable parity only, never a genuine ECU profile.\r\n"
        "[Vehicle]\r\nECUCount=2\r\nBatteryMv=12500\r\nEmitIsoRxStart=1\r\n"
        "[ECU0]\r\nRequestId=7E0\r\nResponseId=7E8\r\n"
        "PartNumber=LAB-A\r\nSoftware=LAB-LONG-SYNTHETIC-ENGINE\r\n"
        "[ECU1]\r\nRequestId=7E1\r\nResponseId=7E9\r\n"
        "PartNumber=LAB-B\r\nSoftware=LAB-SW-B\r\n"
        "[Diagnostics]\r\nStrictJ2534Filters=1\r\nBackendTelemetryEnabled=0\r\n"
        "[PassiveCAN]\r\nEnabled=0\r\n"
        "[PassiveTrace]\r\nEnabled=0\r\n"
        "[P2]\r\nStrictRouting=1\r\n"
        "[D2_40]\r\nB9FBFrameCount=0\r\n"
        "[D2_50]\r\nB9FBFrameCount=0\r\n";
    config.close();
    if (!config) return false;
    // Child-process-only environment; never edit J2534 registry or user
    // profile, and never overwrite the original DLL or config.
    const std::string dir = lab_dir.string();
    return SetEnvironmentVariableA("LOCALAPPDATA", dir.c_str()) &&
        SetEnvironmentVariableA("TEMP", dir.c_str()) &&
        SetEnvironmentVariableA("TMP", dir.c_str());
}

} // namespace

int main(int argc, char** argv)
{
    if (sizeof(void*) != 4U || argc != 3) {
        std::fputs("FAIL: require x86 host, old DLL path, NEW lab directory\n", stderr);
        return 2;
    }
    try {
        const fs::path source = fs::absolute(fs::path(argv[1]));
        const fs::path lab = fs::absolute(fs::path(argv[2]));
        fs::path copied;
        if (!create_lab(source, lab, copied)) {
            std::fputs("FAIL: isolated synthetic lab creation\n", stderr);
            return 2;
        }
        Legacy old;
        if (!old.load(copied)) {
            std::fputs("FAIL: actual old C x86 DLL not loaded/opened\n", stderr);
            return 1;
        }
        using Gate = bool (*)(Legacy&);
        const std::array<std::pair<const char*, Gate>, 8> checks{{
            {"01 old C DLL vs C++ exact short DID F187", group01_short_positive},
            {"02 old C DLL vs C++ long DID F189 START pair", group02_long_with_start},
            {"03 two independent ECU routes in same channel", group03_two_ecu},
            {"04 two channels, filtered vs unfiltered isolation", group04_channel_isolation},
            {"05 broad FC mask short allowed, long refused", group05_broad_filter},
            {"06 mismatched flow destination suppresses reply", group06_wrong_flow},
            {"07 63-message FIFO atomic START drop, byte parity", group07_atomic_full_fifo},
            {"08 disconnect invalidates queue and filter", group08_disconnect_reset}
        }};
        int passed = 0;
        for (const auto& [name, gate] : checks) {
            bool success = gate(old);
            // The reference C DLL has eight channel slots. Release each
            // gate's channels before the next independent trace begins.
            while (!old.channels.empty()) {
                const Dword channel = old.channels.back();
                if (!old.close_channel(channel)) {
                    success = false;
                    break;
                }
            }
            std::printf("%s %s\n", success ? "PASS" : "FAIL", name);
            if (success) ++passed;
        }
        std::printf("M4B-2 independently built C DLL vs C++ RX: %d/8\n", passed);
        return passed == 8 ? 0 : 1;
    } catch (...) {
        std::fputs("FAIL: isolated native parity test exception\n", stderr);
        return 1;
    }
}
