/* B3A19 VIDA 29-bit physical UDS request classifier, READ-ONLY.
 * Must be included after U32/U8 and PROTO_ISO15765 are defined.
 * Classifies the exact 18 DA <target> F1 J2534 ISO15765 request shape.
 * A classifier hit is not an ECU, reply, VIN, or route implementation.
 * No CAN response ID is derived or fabricated here.
 */
#ifndef VIRTUALCAR_VIDA_UDS29_ROUTE_H
#define VIRTUALCAR_VIDA_UDS29_ROUTE_H

typedef struct {
    U32 request_id;
    U32 target;
    U32 sid;
    U32 operand; /* for SID 22: DID; for SID 19: subfunction + request byte */
} VIDA_UDS29_REQUEST;

static int vida_uds29_request_probe(U32 request_id, U32 protocol,
                                    const U8 *payload, U32 payload_len,
                                    VIDA_UDS29_REQUEST *out) {
    if(!payload || !out || protocol != PROTO_ISO15765 ||
       (request_id & 0xFFFF00FFu) != 0x18DA00F1u ||
       payload_len != 3u ||
       (payload[0] != 0x22u && payload[0] != 0x19u))
        return 0;
    out->request_id = request_id;
    out->target = (request_id >> 8) & 0xFFu;
    out->sid = payload[0];
    out->operand = ((U32)payload[1] << 8) | (U32)payload[2];
    return 1;
}

#endif
