#include "p2_xc90_generation.h"
#include <assert.h>
#include <stdio.h>

static unsigned groups;
#define GROUP() (++groups)

int main(void) {
    p2_xc90_generation p;
    assert(!p2_xc90_generation_lookup(2009u, true, 0));
    assert(!p2_xc90_generation_lookup(2002u, false, &p));
    assert(p.kind == P2_XC90_UNKNOWN && p.hs_can_bps == 0u);
    assert(!p2_xc90_generation_lookup(2015u, false, &p)); GROUP();

    assert(p2_xc90_generation_lookup(2003u, false, &p));
    assert(p.kind == P2_XC90_EARLY_MY2003_2004);
    assert(p.hs_can_bps == 250000u && p.ls_can_bps == 125000u);
    assert(p.vida_cem_node_hint == 0x40u); GROUP();

    assert(p2_xc90_generation_lookup(2004u, true, &p));
    assert(p.kind == P2_XC90_EARLY_MY2003_2004);
    assert(!p.ggd_hs_v8_candidate); GROUP();

    assert(p2_xc90_generation_lookup(2005u, false, &p));
    assert(p.kind == P2_XC90_LATE_MY2005_2006);
    assert(p.hs_can_bps == 500000u && p.vida_cem_node_hint == 0x50u);
    assert(p2_xc90_generation_lookup(2006u, false, &p));
    assert(p.kind == P2_XC90_LATE_MY2005_2006); GROUP();

    assert(p2_xc90_generation_lookup(2007u, false, &p));
    assert(p.kind == P2_XC90_FACELIFT_MY2007_2014);
    assert(p2_xc90_generation_lookup(2009u, false, &p));
    assert(p.kind == P2_XC90_FACELIFT_MY2007_2014); GROUP();

    assert(p2_xc90_generation_lookup(2014u, false, &p));
    assert(p.hs_can_bps == 500000u && p.ls_can_bps == 125000u);
    assert(!p.ggd_hs_v8_candidate); GROUP();

    assert(p2_xc90_generation_lookup(2009u, true, &p));
    assert(p.ggd_hs_v8_candidate);
    assert(!p.ecu_fixture_verified && !p.auto_identification_response_allowed);
    assert(p2_xc90_generation_vida_cem_hint_matches(&p, 0x50u));
    assert(!p2_xc90_generation_vida_cem_hint_matches(&p, 0x40u)); GROUP();

    assert(p2_xc90_generation_bus_matches(&p, P2_XC90_HS_BUS, 500000u));
    assert(!p2_xc90_generation_bus_matches(&p, P2_XC90_HS_BUS, 250000u));
    assert(p2_xc90_generation_bus_matches(&p, P2_XC90_LS_BUS, 125000u));
    assert(!p2_xc90_generation_bus_matches(&p, P2_XC90_LS_BUS, 500000u));
    assert(!p2_xc90_generation_bus_matches(&p, (p2_xc90_bus_kind)3, 500000u));
    assert(!p2_xc90_generation_bus_matches(0, P2_XC90_HS_BUS, 500000u));
    assert(!p2_xc90_generation_vida_cem_hint_matches(0, 0x50u)); GROUP();

    printf("XC90 generations: %u/8 groups OK\n", groups);
    return groups == 8u ? 0 : 1;
}
