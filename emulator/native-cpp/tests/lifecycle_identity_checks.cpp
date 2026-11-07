#include "virtualcar/lifecycle.hpp"

#include <array>
#include <cstdint>
#include <cstdio>

using virtualcar::lifecycle::BoundedSession;
using virtualcar::lifecycle::ChannelKind;
using virtualcar::lifecycle::Result;
using virtualcar::lifecycle::SessionKey;

namespace {
constexpr SessionKey original{1, 1, 4100, 100000};
constexpr SessionKey restarted_same_pid{1, 1, 4100, 200000};
constexpr SessionKey restarted_new_pid{1, 1, 5100, 300000};

bool group01_process_identity_is_mandatory()
{
    BoundedSession session(1000);
    return session.begin({1, 1, 0, 100000}, true, 100) == Result::invalid &&
           session.begin({1, 1, 4100, 0}, true, 100) == Result::invalid &&
           !session.snapshot().active;
}

bool group02_same_token_new_process_instance_is_fresh()
{
    BoundedSession session(1000);
    std::uint32_t old_channel{};
    if (session.begin(original, true, 100) != Result::ok ||
        session.reserve_channel(original, ChannelKind::can, 101, old_channel) != Result::ok)
        return false;

    // A restarted Core coordinator can legitimately issue the same 1/1 token.
    // The same PID may also be recycled, so creation time is part of identity.
    if (session.begin(restarted_same_pid, true, 102) != Result::ok)
        return false;
    const auto state = session.snapshot();
    if (!state.active || state.channels != 0)
        return false;

    std::uint32_t new_channel{};
    return session.reserve_channel(restarted_same_pid, ChannelKind::can, 103, new_channel) == Result::ok &&
           new_channel > old_channel &&
           session.close_channel(restarted_same_pid, old_channel, 104) == Result::invalid;
}

bool group03_duplicate_same_host_token_is_rejected()
{
    BoundedSession session(1000);
    if (session.begin(original, true, 100) != Result::ok)
        return false;
    if (session.begin(original, true, 101) != Result::invalid)
        return false;
    return !session.snapshot().active;
}

bool group04_validation_does_not_extend_and_stale_host_revokes()
{
    BoundedSession session(1000);
    if (session.begin(original, true, 100) != Result::ok ||
        session.validate(original, 500) != Result::ok ||
        session.snapshot().expires_at_ms != 1100)
        return false;

    BoundedSession after_restart(1000);
    if (after_restart.begin(restarted_new_pid, true, 100) != Result::ok)
        return false;
    if (after_restart.validate(original, 101) != Result::not_authenticated)
        return false;
    return !after_restart.snapshot().active &&
           after_restart.snapshot().channels == 0;
}
} // namespace

int main()
{
    struct Gate { const char* name; bool (*run)(); };
    constexpr std::array<Gate, 4> gates{{
        {"01 Host process identity is mandatory", group01_process_identity_is_mandatory},
        {"02 Same token after host restart is a fresh process instance", group02_same_token_new_process_instance_is_fresh},
        {"03 Duplicate token from same host is rejected", group03_duplicate_same_host_token_is_rejected},
        {"04 Read-only validation and stale-host revocation", group04_validation_does_not_extend_and_stale_host_revokes}
    }};
    unsigned passed = 0;
    for (const auto& gate : gates) {
        const bool ok = gate.run();
        std::printf("%s %s\n", ok ? "PASS" : "FAIL", gate.name);
        if (ok) ++passed;
    }
    std::printf("VirtualCar M5C-2 process identity gates: %u/4\n", passed);
    return passed == gates.size() ? 0 : 1;
}
