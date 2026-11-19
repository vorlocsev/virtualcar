#ifndef P2_CEM_ROUTER_H
#define P2_CEM_ROUTER_H
#include <stdint.h>
#include <stddef.h>
#ifdef __cplusplus
extern "C" {
#endif

/* Read-only D2 request classifier for Virtual Car.
   No ECU response is emitted by this module. In particular A3, E0, F0 and
   ignition reference replies are NEVER synthesized. */
#define P2_CEM_D2_TX_CAN_ID 0x000FFFFEu
#define P2_CEM_D2_RX_CAN_ID 0x01200003u

typedef enum {
  P2_CEM_NOT_D2 = 0, P2_CEM_INVALID_REQUEST,
  P2_CEM_A3_SHAPE, P2_CEM_A3_OTHER,
  P2_CEM_B9E0, P2_CEM_B9F0, P2_CEM_B9FB, P2_CEM_B9FC,
  P2_CEM_A6_REF6660_CANDIDATE, P2_CEM_UNKNOWN
} p2_cem_request;

typedef enum {
  P2_CEM_KEEP_EXISTING = 0,  /* no side effect, existing J2534 path owns response */
  P2_CEM_ROUTE_MISMATCH = 1, /* diagnostic annotation only, never block TX */
  P2_CEM_NEED_EVIDENCE = 2   /* request recognized but no verified answer */
} p2_cem_decision;

typedef struct {
  p2_cem_request request;
  p2_cem_decision decision;
  uint8_t route;
  uint8_t is_valid_cem_route;
  uint8_t is_expected_bus;
  uint8_t matched_full_shape;
} p2_cem_result;

/* Input is D2 payload only, WITHOUT four J2534 CAN-ID bytes.
   This is metadata/classification ONLY. */
p2_cem_result p2_cem_classify(uint32_t tx_can_id, uint32_t bitrate,
                              const uint8_t *payload, size_t size);
const char *p2_cem_request_name(p2_cem_request r);

/* Hardware-phase TX evidence only. This never authorizes ECU access and
   never confirms a positive CEM reply. No received payload is used here. */
typedef enum {
  P2_HW_UNRELATED = 0,
  P2_HW_INVALID_SHAPE,
  P2_HW_WRONG_BUS,
  P2_HW_A3_TX,
  P2_HW_E0_TX_AFTER_A3_TX_UNVERIFIED,
  P2_HW_F0_TX_AFTER_E0_TX_UNVERIFIED,
  P2_HW_OUT_OF_ORDER
} p2_hw_tx_event;

typedef struct {
  uint32_t a3_tx, e0_tx, f0_tx, invalid_shapes, wrong_bus, out_of_order;
  uint8_t last_target;
  uint8_t last_request; /* 0=none, 1=A3 TX, 2=E0 TX, 3=F0 TX; NOT ECU-ACK */
} p2_hw_tx_trace;

/* Input is eight classic-CAN data bytes, without 4-byte J2534 CAN ID.
   Distinguishes observed TX chronology from accepted ECU/session state. */
p2_hw_tx_event p2_hw_observe_tx(p2_hw_tx_trace *trace, uint32_t can_id,
                                 uint32_t bitrate, const uint8_t *data,
                                 size_t data_size);

/* Static-safe event labels for native J2534 logs (no payload). */
const char *p2_hw_tx_event_name(p2_hw_tx_event event);

/* Candidate RX observer for a legacy D2 E3/02 header after an A3 TX.
   This does NOT authenticate a CEM, prove OEM provenance, or unlock a session.
   Legacy response IDs are observational assumptions, not MY2009 truth. */
typedef enum {
  P2_HW_RX_UNRELATED = 0,
  P2_HW_RX_ORPHAN_E3_CANDIDATE,
  P2_HW_RX_INVALID_FRAME_CANDIDATE,
  P2_HW_RX_ROUTE_MISMATCH_CANDIDATE,
  P2_HW_RX_SUBCOMMAND_MISMATCH_CANDIDATE,
  P2_HW_RX_WRONG_BUS_CANDIDATE,
  P2_HW_RX_OTHER_ID_CANDIDATE,
  P2_HW_RX_LEGACY_ID_CANDIDATE_UNVERIFIED
} p2_hw_rx_event;

p2_hw_rx_event p2_hw_inspect_e3_rx_candidate(const p2_hw_tx_trace *tx,
                                             uint32_t bitrate,
                                             uint32_t response_can_id,
                                             const uint8_t *payload, size_t len);
const char *p2_hw_rx_event_name(p2_hw_rx_event event);

/* Independent passive readers: do not convert the following into responses.
   Two-frame legacy F0 PN and SectorV's 15-byte F0 body are distinct formats. */
int p2_cem_decode_legacy_b9f0_pn(const uint8_t first[8],
                                  const uint8_t second[8], uint32_t *pn);
/* Client-side Hardware F0 body shape only (assembled 15-byte body).
   No part number, ECU provenance, accepted session or OEM identity. */
typedef enum {
  P2_CEM_F0_NO_BODY = 0,
  P2_CEM_F0_INVALID_LENGTH,
  P2_CEM_F0_INVALID_BCD,
  P2_CEM_F0_INVALID_REVISION,
  P2_CEM_F0_STRUCTURAL_CANDIDATE
} p2_cem_f0_shape;

p2_cem_f0_shape p2_cem_inspect_sectorv_f0_body(const uint8_t *body, size_t len);
const char *p2_cem_f0_shape_name(p2_cem_f0_shape status);
int p2_cem_validate_sectorv_f0_body(const uint8_t *body, size_t size);
int p2_cem_e3_02_candidate(const uint8_t *body, size_t size);
#ifdef __cplusplus
}
#endif
#endif
