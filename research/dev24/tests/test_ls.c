#include "../src/p2_ls_observer.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static int test_count = 0;
#define TEST(expr) do { assert(expr); ++test_count; } while (0)

int main(void) {
    uint8_t data[8] = {0};
    p2_ls_observation v = {0};
    data[6] = 0xC0; /* key present + position II */
    TEST(p2_ls_decode(125000, true, 0x00617FF8, data, 8, &v));
    TEST(v.kind == P2_LS_CEM_IGNITION && v.value.cem.key_present && v.value.cem.position == 2);
    data[6] = 0x20; /* key not present + position I, intentionally contradictory */
    TEST(p2_ls_decode(125000, true, 0x00617FF8, data, 8, &v));
    TEST(!v.value.cem.key_present && v.value.cem.position == 1);
    TEST(!p2_ls_decode(500000, true, 0x00617FF8, data, 8, &v));
    TEST(!p2_ls_decode(125000, false, 0x00617FF8, data, 8, &v));
    TEST(!p2_ls_decode(125000, true, 0x00617FF8, data, 7, &v));
    TEST(!p2_ls_decode(125000, true, 0x0, data, 8, &v));
    TEST(!p2_ls_decode(125000, true, 0x00617FF8, NULL, 8, &v));
    TEST(!p2_ls_decode(125000, true, 0x00617FF8, data, 8, NULL));
    memset(data, 0, sizeof data); data[2] = 0x24;
    TEST(p2_ls_decode(125000, true, 0x03003028, data, 8, &v));
    TEST(v.value.gearbox.selected_gear == 4 && v.value.gearbox.raw_actual_gear_bits == 0x20);
    data[2] = 0x40; data[3] = 0x0F;
    TEST(p2_ls_decode(125000, true, 0x00E00442, data, 8, &v));
    TEST(v.value.ccm.park_button_pressed && v.value.ccm.ambient_light_nibble == 15);
    data[3] = 0xF8;
    TEST(p2_ls_decode(125000, true, 0x01E0522E, data, 8, &v));
    TEST(v.value.rem.distance_code == 0);
    data[6] = 0x03; data[7] = 0x3E;
    TEST(p2_ls_decode(125000, true, 0x00404066, data, 8, &v));
    TEST(v.value.swm.buttons == 0x0301);
    printf("Passed %d checks (passive, synthetic inputs).\n", test_count);
    return 0;
}
