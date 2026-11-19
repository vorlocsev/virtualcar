#include "p2_vehicle_core.h"

p2_vehicle_config p2_vehicle_xc90_v8_my2009_config(void) {
    p2_vehicle_config cfg;
    cfg.hs_bitrate = 500000u;
    cfg.ls_bitrate = 125000u;
    cfg.enable_community_ls_signals = false;
    cfg.observed_cem_ls_can_id = 0u;
    return cfg;
}

void p2_vehicle_init(p2_vehicle *v, const p2_vehicle_config *cfg) {
    if (!v) return;
    *v = (p2_vehicle){0};
    v->cfg = cfg ? *cfg : p2_vehicle_xc90_v8_my2009_config();
    v->diagnostic_ignition = P2_DIAG_IGNITION_UNKNOWN;
}

static bool bus_correct(const p2_vehicle *v, p2_bus bus, uint32_t bitrate) {
    return (bus == P2_BUS_HS && bitrate == v->cfg.hs_bitrate) ||
           (bus == P2_BUS_LS && bitrate == v->cfg.ls_bitrate);
}

p2_vehicle_tx_assessment p2_vehicle_observe_tx(p2_vehicle *v,
      p2_bus bus, uint32_t bitrate, uint32_t can_id,
      const uint8_t *data, size_t n) {
    p2_vehicle_tx_assessment out;
    out = (p2_vehicle_tx_assessment){0};
    out.must_forward_unchanged = true;
    out.classified.request = P2_CEM_NOT_D2;
    out.classified.decision = P2_CEM_KEEP_EXISTING;
    if (!v) return out;
    out.bus_matches_config = bus_correct(v, bus, bitrate);
    out.classified = p2_cem_classify(can_id, bitrate, data, n);
    (void)p2_hw_observe_tx(&v->hw_tx, can_id, bitrate, data, n);
    if (out.classified.request != P2_CEM_NOT_D2) {
        ++v->d2_tx_seen;
        if (!out.bus_matches_config || out.classified.decision == P2_CEM_ROUTE_MISMATCH) {
            ++v->diag_wrong_bus_annotations;
            out.classified.decision = P2_CEM_ROUTE_MISMATCH;
        }
        switch (out.classified.request) {
        case P2_CEM_A3_SHAPE: ++v->a3_shape_seen; break;
        case P2_CEM_B9F0: ++v->b9f0_seen; break;
        case P2_CEM_B9FB: ++v->b9fb_seen; break;
        case P2_CEM_A6_REF6660_CANDIDATE: ++v->possible_ref6660_seen; break;
        default: break;
        }
    }
    return out;
}

bool p2_vehicle_observe_rx(p2_vehicle *v,
      p2_bus bus, uint32_t bitrate, bool extended_id,
      uint32_t can_id, const uint8_t *data, size_t dlc, uint64_t at_ms,
      p2_ls_observation *observation) {
    p2_ls_observation decoded;
    uint32_t decode_id;
    if (!v) return false;
    if (!v->cfg.enable_community_ls_signals || bus != P2_BUS_LS ||
        bitrate != v->cfg.ls_bitrate || !extended_id ||
        dlc != 8u || !data || can_id > 0x1FFFFFFFu) {
        ++v->ls_frames_rejected;
        return false;
    }
    decode_id = can_id;
    /* Explicit remapping only for CEM signal confirmed by the caller.
       All other source-defined IDs remain untouched. */
    if (v->cfg.observed_cem_ls_can_id != 0u &&
        can_id == v->cfg.observed_cem_ls_can_id)
        decode_id = 0x00617FF8u;
    else if (can_id == 0x00617FF8u &&
             v->cfg.observed_cem_ls_can_id != can_id) {
        ++v->ls_frames_rejected;
        return false; /* never trust default source-car ID as target-car CEM */
    }
    if (!p2_ls_decode(bitrate, extended_id, decode_id, data, dlc, &decoded)) {
        ++v->ls_frames_rejected;
        return false;
    }
    decoded.can_id = can_id; /* retain real frame ID, not virtual lookup ID */
    if (decoded.kind == P2_LS_CEM_IGNITION) {
        if (v->passive_key.valid && at_ms < v->passive_key.observed_ms) {
            ++v->stale_ignition_frames;
            ++v->ls_frames_rejected;
            return false;
        }
        v->passive_key.valid = true;
        v->passive_key.key_present = decoded.value.cem.key_present;
        v->passive_key.key_position = decoded.value.cem.position;
        v->passive_key.source_can_id = can_id;
        v->passive_key.observed_ms = at_ms;
    }
    ++v->ls_frames_accepted;
    if (observation) *observation = decoded;
    return true;
}

void p2_vehicle_note_d2_candidate_rx(p2_vehicle *v,
      const uint8_t *body, size_t len) {
    if (v && p2_cem_e3_02_candidate(body, len)) ++v->diag_e3_02_candidates;
    /* Not a confirmation: missing session correlation, full decoded body, ECU ID. */
}

bool p2_vehicle_observe_passthru_tx(p2_vehicle *v,
      uint32_t protocol_id, uint32_t bitrate, bool extended_id,
      const uint8_t *data, size_t n, p2_vehicle_tx_assessment *out) {
    uint32_t id;
    p2_bus bus;
    if (!v || !out || !data || n < 4u || !extended_id ||
        (protocol_id != 5u && protocol_id != 6u)) return false;
    id = ((uint32_t)data[0] << 24) | ((uint32_t)data[1] << 16) |
         ((uint32_t)data[2] << 8) | data[3];
    if (id > 0x1FFFFFFFu) return false;
    /* Require known configured bitrate, rather than guessing bus ownership. */
    if (bitrate == v->cfg.hs_bitrate && bitrate != v->cfg.ls_bitrate) bus = P2_BUS_HS;
    else if (bitrate == v->cfg.ls_bitrate && bitrate != v->cfg.hs_bitrate) bus = P2_BUS_LS;
    else return false;
    *out = p2_vehicle_observe_tx(v, bus, bitrate, id, data + 4, n - 4);
    return true;
}
