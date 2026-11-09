#include "p2_xc90_generation.h"

bool p2_xc90_generation_lookup(unsigned model_year, bool engine_b8444s,
                               p2_xc90_generation *out) {
    p2_xc90_generation profile = {0};
    if (!out) return false;
    *out = profile;
    if (model_year < 2003u || model_year > 2014u) return false;
    profile.model_year = (uint16_t)model_year;
    profile.ls_can_bps = 125000u;
    if (model_year <= 2004u) {
        profile.kind = P2_XC90_EARLY_MY2003_2004;
        profile.hs_can_bps = 250000u;
        profile.vida_cem_node_hint = 0x40u;
    } else {
        profile.kind = model_year <= 2006u
            ? P2_XC90_LATE_MY2005_2006
            : P2_XC90_FACELIFT_MY2007_2014;
        profile.hs_can_bps = 500000u;
        profile.vida_cem_node_hint = 0x50u;
        /* Candidate family on the V8 branch, not an ECU-specific verdict. */
        profile.ggd_hs_v8_candidate = engine_b8444s;
    }
    /* Without vehicle-matched provenance, no ECU reply is authorized. */
    profile.ecu_fixture_verified = false;
    profile.auto_identification_response_allowed = false;
    *out = profile;
    return true;
}

bool p2_xc90_generation_bus_matches(const p2_xc90_generation *profile,
                                     p2_xc90_bus_kind bus, uint32_t bps) {
    if (!profile || profile->kind == P2_XC90_UNKNOWN) return false;
    if (bus == P2_XC90_HS_BUS) return bps == profile->hs_can_bps;
    if (bus == P2_XC90_LS_BUS) return bps == profile->ls_can_bps;
    return false;
}

bool p2_xc90_generation_vida_cem_hint_matches(
    const p2_xc90_generation *profile, uint8_t vida_node) {
    return profile && profile->kind != P2_XC90_UNKNOWN &&
           profile->vida_cem_node_hint == vida_node;
}
