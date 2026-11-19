#ifndef P2_J2534_BRIDGE_H
#define P2_J2534_BRIDGE_H
#include "p2_vehicle_core.h"
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

/* Pure-C integration seam. The host MUST serialize access (proxy uses a Win32
 * critical section); the bridge neither invokes J2534 nor constructs replies. */
#define P2_BRIDGE_MAX_CHANNELS 64u
#define P2_BRIDGE_CAN_29BIT_FLAG 0x00000100u
#define P2_BRIDGE_RX_START_OF_MESSAGE_FLAG 0x00000002u
/* 5-second observation window from the currently observed client Hardware probe.
   An in-window candidate is still NOT an accepted ECU response. */
#define P2_BRIDGE_HW_E3_WINDOW_US 5000000ull

typedef struct {
    uint32_t id, protocol_id, baud, generation;
    bool active;
    p2_hw_tx_trace hw_tx; /* per-channel TX chronology, never an ECU ACK */
    uint64_t hw_a3_tx_us; /* local monotonic time, not in public logs */
    bool hw_a3_clock_valid; /* reset on retune/reconnect/another TX */
} p2_bridge_channel;

typedef struct {
    p2_vehicle vehicle;
    p2_bridge_channel channels[P2_BRIDGE_MAX_CHANNELS];
    uint32_t next_generation;
    uint32_t channels_overflow;
    uint32_t unknown_channel_events;
    uint32_t inspected_tx;
    uint32_t inspected_rx;
} p2_j2534_bridge;

typedef struct {
    const char *label;      /* static-safe name, never raw payload */
    p2_hw_tx_event hw_event; /* channel-scoped TX, never a positive RX */
    p2_cem_decision decision;
    uint32_t baud;
    p2_bus bus;
    bool observed;
} p2_bridge_tx_result;

void p2_bridge_init(p2_j2534_bridge *bridge);
void p2_bridge_connect(p2_j2534_bridge *bridge, uint32_t channel,
                       uint32_t protocol_id, uint32_t baud);
void p2_bridge_disconnect(p2_j2534_bridge *bridge, uint32_t channel);
bool p2_bridge_inspect_tx(p2_j2534_bridge *bridge, uint32_t channel,
                          uint32_t tx_flags, const uint8_t *data,
                          size_t data_size, p2_bridge_tx_result *out);
/* B3A317: add monotonic time to already-observed TX without altering
   the original passive observer. A new outgoing TX invalidates prior A3 clock. */
bool p2_bridge_inspect_tx_at(p2_j2534_bridge *bridge, uint32_t channel,
                             uint32_t flags, const uint8_t *data,
                             size_t data_size, uint64_t observed_us,
                             p2_bridge_tx_result *out);

/* Inspect J2534-delivered raw CAN RX only, as candidate header metadata.
   Does not mutate TX state, emit RX or assert successful CEM session. */
p2_hw_rx_event p2_bridge_inspect_hw_rx(p2_j2534_bridge *bridge,
                                        uint32_t channel,
                                        uint32_t rx_status,
                                        const uint8_t *data,
                                        size_t data_size);
/* B3A317: delivered RX must be within five seconds of a timestamped A3
   on the same channel. Matching is a candidate, NEVER authentication. */
p2_hw_rx_event p2_bridge_inspect_hw_rx_at(p2_j2534_bridge *bridge,
                                           uint32_t channel,
                                           uint32_t rx_status,
                                           const uint8_t *data,
                                           size_t data_size,
                                           uint64_t delivered_us);
/* Returns static label for an opt-in, observed raw LS CAN frame or NULL.
 * Never extracts or logs key position / actual frame bytes. */
const char *p2_bridge_inspect_rx(p2_j2534_bridge *bridge, uint32_t channel,
                                  uint32_t rx_status, const uint8_t *data,
                                  size_t data_size, uint64_t time_ms);
#endif
