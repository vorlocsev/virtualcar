#ifndef P2_MESSAGE_CLASSIFY_H
#define P2_MESSAGE_CLASSIFY_H
#include <stdint.h>
#include <stddef.h>
/* Data begins with a 4-byte big-endian CAN ID in J2534 raw CAN/ISO15765 messages.
   This classifier intentionally inspects only protocol headers, never payloads. */
typedef enum {
    P2_OTHER=0, P2_A3, P2_B9E0, P2_B9F0, P2_B9FB, P2_B9FC,
    P2_RX_E3_CANDIDATE, P2_RX_F9E0_CANDIDATE, P2_RX_F9F0_CANDIDATE,
    P2_RX_D2_FRAGMENT, P2_D2_POWER_REF_6660_TX, P2_RX_D2_POWER_6660_CANDIDATE,
    P2_D2_POWER_REF_6660_POSSIBLE_TX, P2_D2_A6_MARKER_TX, P2_D2_UNRESOLVED_TX,
    P2_A3_0203_SHAPE, P2_RX_E3_02_CANDIDATE
} p2_kind;
p2_kind p2_classify(const uint8_t *data, size_t size, int is_rx);
const char *p2_kind_name(p2_kind k);
uint32_t p2_can_id(const uint8_t *data, size_t size);
#endif
