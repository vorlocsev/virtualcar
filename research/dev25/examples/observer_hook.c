/* Platform-independent integration example, not a replacement PassThru DLL. */
#include "p2_vehicle_core.h"
#include <stdint.h>

/* One owner/dispatcher must serialize access to this object. */
static p2_vehicle vehicle;
void example_virtualcar_startup(void) {
    p2_vehicle_config cfg = p2_vehicle_xc90_v8_my2009_config();
    p2_vehicle_init(&vehicle, &cfg);
}

/* Call after validating J2534 DataSize and resolving the connected channel.
   Real PassThruWriteMsgs must ALWAYS process the original message afterward. */
void example_observe_j2534_tx(uint32_t protocol_id, uint32_t bitrate,
                              int extended_id, const uint8_t *j2534_data,
                              size_t valid_data_size) {
    p2_vehicle_tx_assessment result;
    (void)p2_vehicle_observe_passthru_tx(&vehicle, protocol_id, bitrate,
                                        extended_id != 0, j2534_data,
                                        valid_data_size, &result);
    /* No CAN TX, no J2534 error override, no fabricated reply. */
}

void example_observe_raw_ls_can_rx(uint32_t id, int extended,
                                   const uint8_t *data, size_t dlc,
                                   uint64_t tick_ms) {
    p2_ls_observation decoded;
    (void)p2_vehicle_observe_rx(&vehicle, P2_BUS_LS, 125000,
                                extended != 0, id, data, dlc,
                                tick_ms, &decoded);
}
