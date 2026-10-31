#include "p2_ls_observer.h"

bool p2_ls_decode(uint32_t bitrate_hz, bool extended_id, uint32_t can_id,
                  const uint8_t *data, size_t dlc, p2_ls_observation *out)
{
    if (!out || !data || !extended_id || bitrate_hz != 125000 || dlc != 8 || can_id > 0x1FFFFFFFu)
        return false;

    p2_ls_observation tmp = {0};
    tmp.can_id = can_id;
    switch (can_id) {
    case 0x00617FF8u: {
        uint8_t key_byte = data[6];
        tmp.kind = P2_LS_CEM_IGNITION;
        tmp.value.cem.key_present = (key_byte & 0x80u) != 0;
        tmp.value.cem.position = (key_byte >> 5) & 0x03u;
        break;
    }
    case 0x03003028u:
        tmp.kind = P2_LS_GEARBOX;
        tmp.value.gearbox.selected_gear = data[2] & 0x07u;
        /* Preserve raw bits 4-6: source README and C++ code disagree on shift. */
        tmp.value.gearbox.raw_actual_gear_bits = data[2] & 0x70u;
        break;
    case 0x00E00442u:
        tmp.kind = P2_LS_CCM;
        tmp.value.ccm.park_button_pressed = (data[2] & 0x40u) != 0;
        tmp.value.ccm.ambient_light_nibble = data[3] & 0x0Fu;
        break;
    case 0x01E0522Eu:
        tmp.kind = P2_LS_REM;
        tmp.value.rem.distance_code = 0x1Fu - (data[3] >> 3);
        break;
    case 0x00404066u:
        tmp.kind = P2_LS_SWM;
        tmp.value.swm.buttons = ((uint16_t)(data[6] & 0x3Fu) << 8) | ((uint16_t)(~data[7]) & 0x3Fu);
        break;
    default:
        return false;
    }
    *out = tmp;
    return true;
}
