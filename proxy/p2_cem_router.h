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

/* Independent passive readers: do not convert the following into responses.
   Two-frame legacy F0 PN and SectorV's 15-byte F0 body are distinct formats. */
int p2_cem_decode_legacy_b9f0_pn(const uint8_t first[8],
                                  const uint8_t second[8], uint32_t *pn);
int p2_cem_validate_sectorv_f0_body(const uint8_t *body, size_t size);
int p2_cem_e3_02_candidate(const uint8_t *body, size_t size);
#ifdef __cplusplus
}
#endif
#endif
