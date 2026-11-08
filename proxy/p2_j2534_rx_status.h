#ifndef P2_J2534_RX_STATUS_H
#define P2_J2534_RX_STATUS_H

#include <stdint.h>

/* J2534 RxStatus, not TxFlags. Bits 7 and 8 describe addressing and
   CAN_29BIT_ID, and must NOT disqualify an otherwise real RX frame.
   Reject indications, failed TX, break, padding/error, and lost-data flags.
   This guards observers only: original PassThruReadMsgs output is untouched. */
#define P2_RX_STATUS_NON_DATA_MASK 0x0000027Fu

static inline int p2_j2534_rx_is_data(uint32_t rx_status) {
    return (rx_status & P2_RX_STATUS_NON_DATA_MASK) == 0u;
}

#endif
