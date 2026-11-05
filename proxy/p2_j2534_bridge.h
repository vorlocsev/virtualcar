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

typedef struct {
    uint32_t id, protocol_id, baud, generation;
    bool active;
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
    p2_cem_decision decision;
    uint32_t baud;
    p2_bus bus;
    bool observed;
} p2_bridge_tx_result;

void p2_bridge_init(p2_j2534_bridge *bridge);
/* Opt-in MY selection for read-only classification. Does not change any J2534
   channel or DLL behavior and never emits an ECU response. Invalid MY leaves
   the destination unchanged. */
bool p2_bridge_init_xc90_model_year(p2_j2534_bridge *bridge,
                                     unsigned model_year, bool engine_b8444s);
void p2_bridge_connect(p2_j2534_bridge *bridge, uint32_t channel,
                       uint32_t protocol_id, uint32_t baud);
void p2_bridge_disconnect(p2_j2534_bridge *bridge, uint32_t channel);
bool p2_bridge_inspect_tx(p2_j2534_bridge *bridge, uint32_t channel,
                          uint32_t tx_flags, const uint8_t *data,
                          size_t data_size, p2_bridge_tx_result *out);
/* Returns static label for an opt-in, observed raw LS CAN frame or NULL.
 * Never extracts or logs key position / actual frame bytes. */
const char *p2_bridge_inspect_rx(p2_j2534_bridge *bridge, uint32_t channel,
                                  uint32_t rx_status, const uint8_t *data,
                                  size_t data_size, uint64_t time_ms);
#endif
