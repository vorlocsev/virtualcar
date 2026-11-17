#ifndef P2_OBSERVED_ROUTES_H
#define P2_OBSERVED_ROUTES_H
#include <stddef.h>
#include <stdint.h>

/* B3A293: pure, metadata-only classification of VIDA request TARGETS.
   These names do NOT certify an ECU exists, that the ECU answered, or that
   an observed DID is supported. Never use them to decide RX or J2534 status.
   Source: owner B3A291 and B3A292 read-only observed TX route catalog. */
static const char *p2_observed_29bit_request_label(
    uint32_t protocol_id, uint32_t bitrate,
    uint32_t message_protocol_id, uint32_t tx_flags,
    uint32_t request_can_id, const uint8_t *uds, size_t uds_size)
{
    /* Standard J2534 ISO15765 / 500k; normal fixed 29-bit target. A padded
       J2534 TX is fine, but addressing / unrelated flag bits are not. */
    if (protocol_id != 6u || message_protocol_id != 6u ||
        bitrate != 500000u || (tx_flags & 0x100u) == 0u ||
        (tx_flags & ~(0x100u | 0x40u)) != 0u || !uds)
        return 0;
    /* Only bounded, complete single-DID reads and DTC read requests.
       Other service bytes (including write/reset/security) stay unlabelled. */
    if (!((uds_size == 3u && uds[0] == 0x22u) ||
          (uds_size >= 2u && uds_size <= 8u && uds[0] == 0x19u)))
        return 0;
    switch (request_can_id) {
    case 0x18DA10F1u: return "P3_29_ECM_REQUEST_OBSERVED";
    case 0x18DA18F1u: return "P3_29_TCM_REQUEST_OBSERVED";
    case 0x18DA1AF1u: return "P3_29_DEM_REQUEST_OBSERVED";
    case 0x18DA01F1u: return "P3_29_BCM_REQUEST_OBSERVED";
    case 0x18DA32F1u: return "P3_29_SAS_REQUEST_OBSERVED";
    case 0x18DA76F1u: return "P3_29_HCM_REQUEST_OBSERVED";
    default: return 0;
    }
}
#endif
