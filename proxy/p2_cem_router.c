#include "p2_cem_router.h"

static int bytes_equal(const uint8_t *a, const uint8_t *b, size_t n) {
  size_t i; for(i=0;i<n;i++) if(a[i]!=b[i])return 0; return 1;
}
static int bcd_ok(uint8_t x) { return ((x >> 4) <= 9u) && ((x & 15u) <= 9u); }
static uint32_t bcd_value(uint8_t x){ return 10u*(x>>4)+(x&15u); }
static int ascii_printable(uint8_t x) {return x >= 0x20u && x <= 0x7Eu;}

p2_cem_result p2_cem_classify(uint32_t tx_can_id,uint32_t bitrate,
                              const uint8_t *p,size_t n) {
  p2_cem_result r = { P2_CEM_NOT_D2, P2_CEM_KEEP_EXISTING, 0,0,0,0 };
  uint8_t service;
  if(tx_can_id != P2_CEM_D2_TX_CAN_ID) return r;
  if(!p || n < 3u){r.request=P2_CEM_INVALID_REQUEST;return r;}
  if(p[0] != 0xCFu && p[0] != 0xCBu && p[0] != 0xCAu) {
    r.request=P2_CEM_UNKNOWN; return r;
  }
  r.route = p[1];
  r.is_valid_cem_route = (uint8_t)(r.route==0x50u||r.route==0x40u);
  if(!r.is_valid_cem_route){r.request=P2_CEM_UNKNOWN;return r;}
  r.is_expected_bus=(uint8_t)((r.route==0x50u && bitrate==500000u) ||
                              (r.route==0x40u && bitrate==125000u));
  service=p[2];
  if(service==0xA3u){
     static const uint8_t shape[6]={0xA3u,0x02u,0x03u,0xA5u,0xA5u,0x00u};
     r.matched_full_shape=(uint8_t)(n>=8u && bytes_equal(p+2,shape,6u));
     r.request=r.matched_full_shape?P2_CEM_A3_SHAPE:P2_CEM_A3_OTHER;
  } else if(service==0xB9u && n>=4u) {
     switch(p[3]) {
       case 0xE0u:r.request=P2_CEM_B9E0;break;
       case 0xF0u:r.request=P2_CEM_B9F0;break;
       case 0xFBu:r.request=P2_CEM_B9FB;break;
       case 0xFCu:r.request=P2_CEM_B9FC;break;
       default:r.request=P2_CEM_UNKNOWN;break;
     }
  } else if(service==0xA6u && n>=6u &&
             p[3]==0x1Au && p[4]==0x04u && p[5]==0x01u) {
     /* Candidate only: protocol framing is not yet independently validated. */
     r.request=P2_CEM_A6_REF6660_CANDIDATE;
  } else r.request=P2_CEM_UNKNOWN;

  if(!r.is_expected_bus)r.decision=P2_CEM_ROUTE_MISMATCH;
  else if(r.request==P2_CEM_A3_SHAPE || r.request==P2_CEM_A3_OTHER ||
          r.request==P2_CEM_B9E0 || r.request==P2_CEM_B9F0 ||
          r.request==P2_CEM_A6_REF6660_CANDIDATE)
    r.decision=P2_CEM_NEED_EVIDENCE;
  /* Crucial: B9FB (which works) and all other existing handlers are untouched. */
  return r;
}

const char *p2_cem_request_name(p2_cem_request r) {
  switch(r) {
   case P2_CEM_NOT_D2:return "not_d2";
   case P2_CEM_INVALID_REQUEST:return "invalid_request";
   case P2_CEM_A3_SHAPE:return "a3_0203_shape";
   case P2_CEM_A3_OTHER:return "a3_other";
   case P2_CEM_B9E0:return "b9e0";
   case P2_CEM_B9F0:return "b9f0";
   case P2_CEM_B9FB:return "b9fb_existing";
   case P2_CEM_B9FC:return "b9fc";
   case P2_CEM_A6_REF6660_CANDIDATE:return "a6_ref6660_candidate";
   default:return "unknown";
  }
}

int p2_cem_decode_legacy_b9f0_pn(const uint8_t first[8],
                                 const uint8_t second[8],uint32_t *pn) {
  const uint8_t b[4] = {first?first[5]:0,first?first[6]:0,
                         first?first[7]:0,second?second[1]:0};
  size_t i;uint32_t number=0;
  if(!first||!second||!pn)return 0;
  /* Legacy decoder observed in Volvo P2 open-source project:
     first response frame bit 7 set; follow-up frame bit 6 clear.
     This is NOT a complete proof of D2 frame authenticity. */
  if(!(first[0]&0x80u) || (second[0]&0x40u))return 0;
  for(i=0;i<4;i++){
    if(!bcd_ok(b[i]))return 0;
    number=number*100u+bcd_value(b[i]);
  }
  *pn=number;return 1;
}

int p2_cem_validate_sectorv_f0_body(const uint8_t *body,size_t n){
  size_t i;
  if(!body||n!=15u)return 0;
  for(i=0;i<5;i++)if(!bcd_ok(body[i]))return 0;
  if(body[5]==0x20u && (!ascii_printable(body[6])||!ascii_printable(body[7])))return 0;
  return 1;
}

int p2_cem_e3_02_candidate(const uint8_t *body,size_t n){
  return (body && n>=2u && body[0]==0xE3u && body[1]==0x02u)?1:0;
}
