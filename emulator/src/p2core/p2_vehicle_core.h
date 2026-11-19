#ifndef P2_VEHICLE_CORE_H
#define P2_VEHICLE_CORE_H
#include "p2_cem_router.h"
#include "p2_ls_observer.h"
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Diagnostic requests and passive LS data are distinct evidence streams.
   The core does NOT send CAN frames and never sets diagnostic ignition. */
typedef enum { P2_BUS_HS = 0, P2_BUS_LS = 1 } p2_bus;
typedef enum { P2_DIAG_IGNITION_UNKNOWN = 0 } p2_diag_ignition;

typedef struct {
    uint32_t hs_bitrate;                    /* 500000 for XC90 V8 MY2009 */
    uint32_t ls_bitrate;                    /* 125000 for XC90 V8 MY2009 */
    bool enable_community_ls_signals;      /* off until checked on the target car */
    uint32_t observed_cem_ls_can_id;       /* 0 means no validated CEM broadcast ID */
} p2_vehicle_config;

typedef struct {
    bool valid;
    bool key_present;
    uint8_t key_position;                  /* 0..3 observed from passive broadcast only */
    uint32_t source_can_id;
    uint64_t observed_ms;
} p2_passive_key;

typedef struct {
    p2_vehicle_config cfg;
    p2_passive_key passive_key;
    p2_diag_ignition diagnostic_ignition;
    uint32_t d2_tx_seen;
    uint32_t a3_shape_seen;
    uint32_t b9f0_seen;
    uint32_t b9fb_seen;
    uint32_t possible_ref6660_seen;
    uint32_t diag_wrong_bus_annotations;
    uint32_t diag_e3_02_candidates;       /* unverified header observations ONLY */
    uint32_t ls_frames_accepted;
    uint32_t ls_frames_rejected;
    uint32_t stale_ignition_frames;
} p2_vehicle;

typedef struct {
    p2_cem_result classified;
    bool bus_matches_config;
    bool must_forward_unchanged;          /* always true; no J2534 side effect */
    uint32_t generated_reply_count;       /* always zero */
} p2_vehicle_tx_assessment;

p2_vehicle_config p2_vehicle_xc90_v8_my2009_config(void);
void p2_vehicle_init(p2_vehicle *vehicle, const p2_vehicle_config *cfg);

/* `payload` begins with the D2 envelope marker (CF/CB/CA), NOT the 4-byte CAN ID.
   Caller still passes all messages to the existing J2534 implementation unchanged. */
p2_vehicle_tx_assessment p2_vehicle_observe_tx(p2_vehicle *vehicle,
      p2_bus bus, uint32_t bitrate, uint32_t can_id,
      const uint8_t *payload, size_t payload_len);

/* Caller supplies actual bus and 29-bit flag obtained from the adapter.
   Only authenticated by provenance as a CAN observation, NOT a validated CEM identity. */
bool p2_vehicle_observe_rx(p2_vehicle *vehicle,
      p2_bus bus, uint32_t bitrate, bool extended_id,
      uint32_t can_id, const uint8_t *payload, size_t dlc, uint64_t at_ms,
      p2_ls_observation *observation);

/* Diagnostic RX count is metadata only. No identity, auth or session is inferred. */
void p2_vehicle_note_d2_candidate_rx(p2_vehicle *vehicle,
      const uint8_t *diagnostic_body, size_t body_len);

/* Convenience adapter for J2534 Data = four big-endian CAN ID bytes + payload.
   Only recognizes CAN(5) and ISO15765(6); does not transform or transmit frames. */
bool p2_vehicle_observe_passthru_tx(p2_vehicle *vehicle,
      uint32_t protocol_id, uint32_t bitrate, bool extended_id,
      const uint8_t *data, size_t data_size, p2_vehicle_tx_assessment *out);
#ifdef __cplusplus
}
#endif
#endif
