#include "p2_j2534_rx_status.h"
#include <assert.h>
#include <stdio.h>

static unsigned groups;
#define GROUP() (++groups)
int main(void) {
    unsigned bit;
    assert(p2_j2534_rx_is_data(0u)); GROUP();
    /* CAN_29BIT_ID and ISO15765_ADDR_TYPE are metadata, not TX echoes. */
    assert(p2_j2534_rx_is_data(0x100u));
    assert(p2_j2534_rx_is_data(0x080u));
    assert(p2_j2534_rx_is_data(0x180u)); GROUP();
    /* TX_MSG_TYPE and its common transmit-done combination. */
    assert(!p2_j2534_rx_is_data(0x001u));
    assert(!p2_j2534_rx_is_data(0x009u)); GROUP();
    /* START_OF_MESSAGE is not a complete application-data RX frame. */
    assert(!p2_j2534_rx_is_data(0x002u)); GROUP();
    /* TX_SUCCESS (former TX_INDICATION) is not a reply. */
    assert(!p2_j2534_rx_is_data(0x008u)); GROUP();
    /* RX_BREAK, invalid padding, error and loss markers are not clean data. */
    for (bit = 2; bit <= 6; ++bit)
        assert(!p2_j2534_rx_is_data(1u << bit));
    GROUP();
    /* TX_FAILED in newer J2534 status layout is not an ECU message. */
    assert(!p2_j2534_rx_is_data(0x200u)); GROUP();
    /* Address flags cannot mask transmit/invalid-status indicators. */
    assert(!p2_j2534_rx_is_data(0x181u));
    assert(!p2_j2534_rx_is_data(0x189u));
    assert(!p2_j2534_rx_is_data(0x380u)); GROUP();
    /* A failed read may leave the buffer and message count untouched. */
    assert(p2_j2534_rx_read_is_data(0u, 0u));
    assert(p2_j2534_rx_read_is_data(0u, 0x180u));
    assert(!p2_j2534_rx_read_is_data(7u, 0u));
    assert(!p2_j2534_rx_read_is_data(16u, 0x180u));
    assert(!p2_j2534_rx_read_is_data(0u, 0x009u)); GROUP();
    printf("dev26: %u/9 native J2534 RxStatus groups OK\n", groups);
    return groups == 9u ? 0 : 1;
}
