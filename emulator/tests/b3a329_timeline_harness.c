#include <stdint.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>
typedef uint32_t U32;
typedef uint8_t U8;
#include "model.c"
#include "timeline.c"
int main(void){
    const U32 times[]={0,2000,4000,60000,180000};
    ECM_LAB_STATE s;
    U8 rpm[4],rpm16[2],voltage[2],maf[4];
    U32 i,t;
    for(i=0;i<5;i++){
        ecm_lab_sample(times[i],&s);
        assert(!memcmp(&s,&g_ecm_lab_scenarios[i],sizeof s));
    }
    ecm_lab_sample(3000,&s);assert(s.rpm==650 && s.battery_mv==12350 && s.maf_centi_gps==550);
    for(t=0;t<=180000;t++){
        ecm_lab_sample(t,&s);assert(ecm_lab_state_valid(&s));
        assert(s.speed_kph==0&&s.pedal_permille==0&&s.coolant_c>=20&&s.coolant_c<=90);
        assert(ecm_lab_encode(&s,0,0xda48,rpm)==4&&ecm_lab_encode(&s,0,0xf40c,rpm16)==2);
        assert(((U32)rpm16[0]*256u+rpm16[1])==s.rpm*4u);
        assert(ecm_lab_encode(&s,0,0x120d,voltage)==2&&ecm_lab_encode(&s,1,0xd994,maf)==4);
    }
    ecm_lab_select_scenario(1,"4");ecm_lab_dynamic_start(0,100);ecm_lab_dynamic_tick(5000);
    assert(g_ecm_lab_state.rpm==700 && ecm_lab_battery_mv(12345,1,1)==14000);
    ecm_lab_dynamic_start(1,0xffffff00u);assert(g_ecm_lab_state.rpm==0);
    ecm_lab_dynamic_tick(0xffffff00u+3000u);assert(g_ecm_lab_state.rpm==650 && ecm_lab_battery_mv(12345,1,1)==12350);
    ecm_lab_dynamic_tick(0xffffff00u+180000u);assert(g_ecm_lab_state.rpm==700 && g_ecm_lab_finished);
    ecm_lab_dynamic_tick(0xffffff00u+1u);assert(g_ecm_lab_state.rpm==700);
    ecm_lab_select_scenario(1,"2");ecm_lab_dynamic_start(0,0);assert(g_ecm_lab_state.rpm==1100);
    ecm_lab_dynamic_start(1,1000);assert(g_ecm_lab_state.rpm==0&&!g_ecm_lab_finished);
    puts("B3A329_TIMELINE_PASS");return 0;
}
