#ifndef J2534_OBSERVER_H
#define J2534_OBSERVER_H
#include <stdint.h>
#include <stddef.h>

/* Passive, bounded metadata observer. Host serializes calls. No J2534 calls,
 * payload logging or replies. All times use the same wrapping host ms clock. */
#define VC_CHANNELS 64u
#define VC_FILTERS 128u
#define VC_PENDING 128u
#define VC_WINDOW_MS 5000u
typedef struct {
    uint32_t ProtocolID, RxStatus, TxFlags, Timestamp, DataSize, ExtraDataIndex;
    uint8_t Data[4128];
} vc_message;
typedef struct {
    const char *event, *classification, *relation;
    uint32_t ms, channel, generation, protocol, baud, status;
    uint32_t can_id, size, rx_status, tx_flags, device_timestamp;
    uint32_t filter_id, filter_type, active_filters, incomplete;
    uint32_t rx_pattern_id, rx_mask_id, flow_control_id, filter_usable;
    uint32_t sequence, candidates, elapsed_ms;
} vc_event;
typedef void (*vc_emit)(void *, const vc_event *);
typedef struct {
    uint32_t id, device, generation, protocol, baud;
    unsigned active, incomplete;
} vc_channel;
typedef struct {
    uint32_t channel, id, type, protocol, size, flags, flow_flags;
    uint8_t mask[5], pattern[5], flow[5];
    unsigned active, usable;
} vc_filter;
typedef struct {
    uint32_t channel, sequence, ms, filter_id;
    uint8_t sid, selector[2], selector_size;
    unsigned active;
} vc_pending;
typedef struct {
    vc_channel channels[VC_CHANNELS];
    vc_filter filters[VC_FILTERS];
    vc_pending pending[VC_PENDING];
    uint32_t generation, sequence;
    vc_emit emit;
    void *context;
} vc_observer;
void vc_init(vc_observer *, vc_emit, void *);
void vc_connect(vc_observer *, uint32_t device, uint32_t channel,
                uint32_t protocol, uint32_t baud, uint32_t now);
void vc_disconnect(vc_observer *, uint32_t channel, uint32_t now);
void vc_close(vc_observer *, uint32_t device, uint32_t now);
void vc_filter_start(vc_observer *, uint32_t channel, uint32_t type,
                     const vc_message *mask, const vc_message *pattern,
                     const vc_message *flow, uint32_t id, uint32_t status, uint32_t now);
void vc_filter_stop(vc_observer *, uint32_t channel, uint32_t id,
                    uint32_t status, uint32_t now);
void vc_ioctl(vc_observer *, uint32_t channel, uint32_t ioctl_id,
               uint32_t status, uint32_t now);
void vc_tx(vc_observer *, uint32_t channel, const vc_message *, uint32_t now);
void vc_rx(vc_observer *, uint32_t channel, const vc_message *, uint32_t now);
#endif
