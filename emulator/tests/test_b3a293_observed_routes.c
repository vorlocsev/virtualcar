/* Standalone C99 regression for metadata-only route observer.
   Build: cc -std=c99 -Wall -Wextra -Werror -pedantic -I emulator/src \
     emulator/tests/test_b3a293_observed_routes.c -o b3a293_test */
#include <stdio.h>
#include <string.h>
#include "p2core/p2_observed_routes.h"

static unsigned passed, failed;
static void check(const char *case_name, const char *actual, const char *wanted) {
    int ok = (!wanted && !actual) ||
             (wanted && actual && strcmp(actual, wanted) == 0);
    if (ok) passed++;
    else { failed++; fprintf(stderr, "FAIL %s (unexpected label)\n", case_name); }
}
static const char *probe(uint32_t p, uint32_t b, uint32_t mp,
                         uint32_t flags, uint32_t can_id,
                         const uint8_t *data, size_t n) {
    return p2_observed_29bit_request_label(p,b,mp,flags,can_id,data,n);
}
int main(void) {
    static const struct { uint32_t id; const char *name; } routes[] = {
        {0x18DA10F1u, "P3_29_ECM_REQUEST_OBSERVED"},
        {0x18DA18F1u, "P3_29_TCM_REQUEST_OBSERVED"},
        {0x18DA1AF1u, "P3_29_DEM_REQUEST_OBSERVED"},
        {0x18DA01F1u, "P3_29_BCM_REQUEST_OBSERVED"},
        {0x18DA32F1u, "P3_29_SAS_REQUEST_OBSERVED"},
        {0x18DA76F1u, "P3_29_HCM_REQUEST_OBSERVED"}
    };
    static const uint8_t did[] = {0x22u,0xF1u,0x10u};
    static const uint8_t dtc[] = {0x19u,0x02u,0xFFu};
    static const uint8_t write[] = {0x2Eu,0xF1u,0x10u};
    static const uint8_t reset[] = {0x11u,0x01u};
    static const uint8_t malformed[] = {0x22u,0xF1u};
    static const uint8_t compound[] = {0x22u,0xF1u,0x10u,0xF1u,0x24u};
    static const uint8_t long_dtc[] = {0x19u,0x02u,0xFFu,0,0,0,0,0,0};
    size_t i;
    for (i=0; i<sizeof(routes)/sizeof(routes[0]); i++) {
        const char *n = routes[i].name;
        uint32_t id = routes[i].id;
        check("service_22_29bit",probe(6,500000,6,0x100,id,did,3),n);
        check("service_22_frame_pad",probe(6,500000,6,0x140,id,did,3),n);
        check("service_19_29bit",probe(6,500000,6,0x100,id,dtc,3),n);
        check("wrong_proto_CAN",probe(5,500000,5,0x100,id,did,3),0);
        check("wrong_message_protocol",probe(6,500000,5,0x100,id,did,3),0);
        check("wrong_baud",probe(6,125000,6,0x100,id,did,3),0);
        check("missing_29bit_flag",probe(6,500000,6,0,id,did,3),0);
        check("extra_extended_addressing_flag",probe(6,500000,6,0x180,id,did,3),0);
        check("write_is_not_observed_read",probe(6,500000,6,0x100,id,write,3),0);
        check("reset_is_not_observed_read",probe(6,500000,6,0x100,id,reset,2),0);
        check("malformed_did_read",probe(6,500000,6,0x100,id,malformed,2),0);
        check("compound_did_read",probe(6,500000,6,0x100,id,compound,5),0);
        check("oversize_dtc_request",probe(6,500000,6,0x100,id,long_dtc,9),0);
        check("null_payload",probe(6,500000,6,0x100,id,0,0),0);
    }
    check("CEM29_is_separate",probe(6,500000,6,0x140,0x18DA50F1u,did,3),0);
    check("CEM11_existing",probe(6,500000,6,0,0x726u,did,3),0);
    check("ECM11_existing",probe(6,500000,6,0,0x7E0u,did,3),0);
    check("unknown_29bit",probe(6,500000,6,0x100,0x18DA77F1u,did,3),0);
    printf("B3A293_OBSERVED_ROUTE_CLASSIFIER_TESTS=%s;PASSED=%u;FAILED=%u\n",
           failed ? "FAIL" : "PASS",passed,failed);
    return failed ? 1 : 0;
}
