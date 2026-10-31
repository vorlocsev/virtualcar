#ifndef P2_LS_OBSERVER_H
#define P2_LS_OBSERVER_H
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>

/* Read-only Volvo P2 low-speed CAN observation; no TX or diag response generation. */
typedef enum {
    P2_LS_UNKNOWN = 0,
    P2_LS_CEM_IGNITION,
    P2_LS_GEARBOX,
    P2_LS_CCM,
    P2_LS_REM,
    P2_LS_SWM
} p2_ls_kind;

typedef struct {
    p2_ls_kind kind;
    uint32_t can_id;
    union {
        struct { bool key_present; uint8_t position; } cem;
        struct { uint8_t selected_gear; uint8_t raw_actual_gear_bits; } gearbox;
        struct { bool park_button_pressed; uint8_t ambient_light_nibble; } ccm;
        struct { uint8_t distance_code; } rem;
        struct { uint16_t buttons; } swm;
    } value;
} p2_ls_observation;

/* Returns false for insufficient DLC, non-extended frame, unknown ID, or null pointers.
   Extended and bus-speed verification is performed by the caller at channel level;
   bitrate_hz must be precisely 125000 here. */
bool p2_ls_decode(uint32_t bitrate_hz, bool extended_id, uint32_t can_id,
                  const uint8_t *data, size_t dlc, p2_ls_observation *out);
#endif
