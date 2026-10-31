#include "p2_message_classify.h"
uint32_t p2_can_id(const uint8_t *d, size_t n) {
    if (!d || n < 4) return 0;
    return ((uint32_t)d[0]<<24)|((uint32_t)d[1]<<16)|((uint32_t)d[2]<<8)|d[3];
}
p2_kind p2_classify(const uint8_t *data, size_t size, int is_rx) {
    const uint8_t *p;
    size_t n;
    if (!data || size < 5) return P2_OTHER;
    p = data+4; n=size-4;
    if (!is_rx) {
        /* SectorV D2 ReadCemReference(6660=0x1A04), confirmed in managed IL:
           [0xA6, 0x1A, 0x04, 0x01]. The J2534 transport may add a
           CB/CF route header; match only the exact reference header.
           This is request recognition, NOT ignition state authentication. */
        if ((n>=6 && (p[0]==0xCB || p[0]==0xCF) &&
             (p[1]==0x40 || p[1]==0x50) &&
             p[2]==0xA6 && p[3]==0x1A && p[4]==0x04 && p[5]==0x01) ||
            (n>=4 && p[0]==0xA6 && p[1]==0x1A && p[2]==0x04 && p[3]==0x01))
            return P2_D2_POWER_REF_6660_TX;

        /* This exact A3 shape is SHARED by SectorV.Diagnostics normal-mode
           preparation (FieldRVA 406) and SectorV.dll hardware identification
           (FieldRVA 2843). Its bytes do NOT establish the calling scenario.
           Observe only. No ECU response is generated or authenticated. */
        if(n>=8 && p[0]==0xCF && (p[1]==0x40 || p[1]==0x50) &&
           p[2]==0xA3 && p[3]==0x02 && p[4]==0x03 &&
           p[5]==0xA5 && p[6]==0xA5 && p[7]==0x00)
            return P2_A3_0203_SHAPE;
        if(n>=3 && p[0]==0xCF && (p[1]==0x40 || p[1]==0x50) && p[2]==0xA3) return P2_A3;
        if(n>=4 && p[0]==0xCB && (p[1]==0x40 || p[1]==0x50) && p[2]==0xB9){
            if(p[3]==0xE0) return P2_B9E0;
            if(p[3]==0xF0) return P2_B9F0;
            if(p[3]==0xFB) return P2_B9FB;
            if(p[3]==0xFC) return P2_B9FC;
        }
        /* Privacy-preserving search for a reference request in an unknown
           transport envelope. A match at an unknown offset is ONLY a
           candidate, never a verified CEM request. No bytes are logged. */
        if (p2_can_id(data, size)==0x000FFFFEu) {
            size_t i;
            for (i=0; i+3<n; ++i) {
                if (p[i]==0xA6 && p[i+1]==0x1A && p[i+2]==0x04 && p[i+3]==0x01)
                    return P2_D2_POWER_REF_6660_POSSIBLE_TX;
            }
            for (i=0; i<n; ++i) {
                if (p[i]==0xA6) return P2_D2_A6_MARKER_TX;
            }
            return P2_D2_UNRESOLVED_TX;
        }
    } else {
        /* Candidate positive header only. Never claims CEM response validity. */
        if ((n>=5 && (p[0]==0xCB || p[0]==0xCF) &&
             (p[1]==0x40 || p[1]==0x50) &&
             p[2]==0xE6 && p[3]==0x1A && p[4]==0x04) ||
            (n>=3 && p[0]==0xE6 && p[1]==0x1A && p[2]==0x04))
            return P2_RX_D2_POWER_6660_CANDIDATE;
        /* Candidate only: a byte sequence alone cannot establish accepted ECU reply. */
        /* E3 02 is the SectorV client expectation. Only label a candidate,
           not a validated CEM acknowledgment. No request-response identity
           or transport-frame validation is implied by this byte match. */
        if(n>=4 && (p[0]==0xCB || p[0]==0xCF) &&
           (p[1]==0x40 || p[1]==0x50) && p[2]==0xE3 && p[3]==0x02)
            return P2_RX_E3_02_CANDIDATE;
        if(n>=3 && (p[1]==0x40 || p[1]==0x50) && p[2]==0xE3) return P2_RX_E3_CANDIDATE;
        if(n>=4 && (p[1]==0x40 || p[1]==0x50) && p[2]==0xF9){
            if(p[3]==0xE0) return P2_RX_F9E0_CANDIDATE;
            if(p[3]==0xF0) return P2_RX_F9F0_CANDIDATE;
        }
        /* Known observed B9FB response chunks may start with 8F,09..,4F. */
        if(n>=1 && ((p[0]>=0x08 && p[0]<=0x0F) || (p[0]>=0x40 && p[0]<=0x4F) || (p[0]>=0x80 && p[0]<=0x8F))) return P2_RX_D2_FRAGMENT;
    }
    return P2_OTHER;
}
const char *p2_kind_name(p2_kind k) {
    switch(k){
    case P2_D2_POWER_REF_6660_TX: return "d2_power_ref_6660_tx";
    case P2_RX_D2_POWER_6660_CANDIDATE: return "d2_power_6660_candidate";
    case P2_D2_POWER_REF_6660_POSSIBLE_TX: return "d2_power_ref_6660_possible_tx";
    case P2_D2_A6_MARKER_TX: return "d2_a6_marker_tx";
    case P2_D2_UNRESOLVED_TX: return "d2_unresolved_tx";
    case P2_A3_0203_SHAPE: return "a3_0203_shape_tx";
    case P2_RX_E3_02_CANDIDATE: return "e3_02_candidate";
    case P2_A3: return "a3_tx";
    case P2_B9E0: return "b9e0_tx";
    case P2_B9F0: return "b9f0_tx";
    case P2_B9FB: return "b9fb_tx";
    case P2_B9FC: return "b9fc_tx";
    case P2_RX_E3_CANDIDATE: return "e3_candidate";
    case P2_RX_F9E0_CANDIDATE: return "f9e0_candidate";
    case P2_RX_F9F0_CANDIDATE: return "f9f0_candidate";
    case P2_RX_D2_FRAGMENT: return "d2_rx_fragment";
    default: return "other";
    }
}
