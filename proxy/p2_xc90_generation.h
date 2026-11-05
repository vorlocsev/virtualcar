#ifndef P2_XC90_GENERATION_H
#define P2_XC90_GENERATION_H

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Read-only vehicle metadata, not a CAN arbitration mapping or ECU fixture. */
typedef enum {
    P2_XC90_UNKNOWN = 0,
    P2_XC90_EARLY_MY2003_2004,
    P2_XC90_LATE_MY2005_2006,
    P2_XC90_FACELIFT_MY2007_2014
} p2_xc90_generation_kind;

typedef enum {
    P2_XC90_HS_BUS = 1,
    P2_XC90_LS_BUS = 2
} p2_xc90_bus_kind;

typedef struct {
    uint16_t model_year;
    p2_xc90_generation_kind kind;
    uint32_t hs_can_bps;
    uint32_t ls_can_bps;
    uint8_t vida_cem_node_hint;
    bool ggd_hs_v8_candidate;
    bool ecu_fixture_verified;
    bool auto_identification_response_allowed;
} p2_xc90_generation;

/* Engine selector is a caller claim, not an independently verified VIN/ECU.
   FALSE on unsupported MY, and clears 'out' on all failed lookups. */
bool p2_xc90_generation_lookup(unsigned model_year, bool engine_b8444s,
                               p2_xc90_generation *out);

/* Strict bus bitrate check; NOT a proof of physical J1962 pin routing. */
bool p2_xc90_generation_bus_matches(const p2_xc90_generation *profile,
                                     p2_xc90_bus_kind bus, uint32_t bps);

/* VIDA logical node hint, NOT a raw 11-/29-bit CAN ID. */
bool p2_xc90_generation_vida_cem_hint_matches(
    const p2_xc90_generation *profile, uint8_t vida_node);

#ifdef __cplusplus
}
#endif
#endif
