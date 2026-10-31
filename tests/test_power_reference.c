#include "../proxy/p2_message_classify.h"
#include <assert.h>
#include <stdio.h>
static void check(const unsigned char *d,size_t n,int isrx,p2_kind expected){assert(p2_classify(d,n,isrx)==expected);}
int main(void){
  const unsigned char wrapped50[]={0,15,255,254,0xCB,0x50,0xA6,0x1A,0x04,0x01};
  const unsigned char wrapped40[]={0,15,255,254,0xCF,0x40,0xA6,0x1A,0x04,0x01};
  const unsigned char unwrapped[]={0,15,255,254,0xA6,0x1A,0x04,0x01};
  const unsigned char wrongid[]={0,15,255,254,0xCB,0x50,0xA6,0x1A,0x05,0x01};
  const unsigned char wrongmode[]={0,15,255,254,0xCB,0x50,0xA6,0x1A,0x04,0x02};
  const unsigned char shortreq[]={0,15,255,254,0xCB,0x50,0xA6,0x1A,0x04};
  const unsigned char e6wrapped[]={1,32,0,3,0xCB,0x50,0xE6,0x1A,0x04,0x06};
  const unsigned char e6raw[]={1,32,0,3,0xE6,0x1A,0x04,0x06};
  const unsigned char otherref[]={1,32,0,3,0xE6,0x1A,0x05,0x06};
  check(wrapped50,sizeof(wrapped50),0,P2_D2_POWER_REF_6660_TX);
  check(wrapped40,sizeof(wrapped40),0,P2_D2_POWER_REF_6660_TX);
  check(unwrapped,sizeof(unwrapped),0,P2_D2_POWER_REF_6660_TX);
  check(wrongid,sizeof(wrongid),0,P2_D2_A6_MARKER_TX);
  check(wrongmode,sizeof(wrongmode),0,P2_D2_A6_MARKER_TX);
  check(shortreq,sizeof(shortreq),0,P2_D2_A6_MARKER_TX);
  const unsigned char shifted_ref[]={0,15,255,254,0x19,0x18,0x14,0xA6,0x1A,0x04,0x01,0x55};
  const unsigned char unknown_d2[]={0,15,255,254,0xCB,0x50,0xB9,0xEA,0,0,0,0};
  const unsigned char unrelated[]={0x18,0xDA,0x50,0xF1,0x19,0x18,0x14,0xA6,0x1A,0x04,0x01,0x55};
  check(shifted_ref,sizeof(shifted_ref),0,P2_D2_POWER_REF_6660_POSSIBLE_TX);
  check(unknown_d2,sizeof(unknown_d2),0,P2_D2_UNRESOLVED_TX);
  check(unrelated,sizeof(unrelated),0,P2_OTHER);
  check(shifted_ref,sizeof(shifted_ref),1,P2_OTHER);
  check(e6wrapped,sizeof(e6wrapped),1,P2_RX_D2_POWER_6660_CANDIDATE);
  check(e6raw,sizeof(e6raw),1,P2_RX_D2_POWER_6660_CANDIDATE);
  check(otherref,sizeof(otherref),1,P2_OTHER);
  check(wrapped50,sizeof(wrapped50),1,P2_OTHER);
  const unsigned char normal50[]={0,15,255,254,0xCF,0x50,0xA3,0x02,0x03,0xA5,0xA5,0x00};
  const unsigned char normal40[]={0,15,255,254,0xCF,0x40,0xA3,0x02,0x03,0xA5,0xA5,0x00};
  const unsigned char hardwareA3[]={0,15,255,254,0xCF,0x50,0xA3,0x02,0x04,0xA5,0xA5,0x00};
  const unsigned char truncatedA3[]={0,15,255,254,0xCF,0x50,0xA3,0x02,0x03};
  const unsigned char rxE302[]={1,32,0,3,0xCF,0x50,0xE3,0x02,0x00};
  const unsigned char rxE303[]={1,32,0,3,0xCF,0x50,0xE3,0x03,0x00};
  const unsigned char rxE3WrongRoute[]={1,32,0,3,0xCF,0x60,0xE3,0x02,0x00};
  check(normal50,sizeof(normal50),0,P2_A3_0203_SHAPE);
  check(normal40,sizeof(normal40),0,P2_A3_0203_SHAPE);
  check(hardwareA3,sizeof(hardwareA3),0,P2_A3);
  check(truncatedA3,sizeof(truncatedA3),0,P2_A3);
  check(rxE302,sizeof(rxE302),1,P2_RX_E3_02_CANDIDATE);
  check(rxE303,sizeof(rxE303),1,P2_RX_E3_CANDIDATE);
  check(rxE3WrongRoute,sizeof(rxE3WrongRoute),1,P2_OTHER);
  check(normal50,sizeof(normal50),1,P2_OTHER);
  assert(p2_can_id(wrapped50,sizeof(wrapped50))==0x000FFFFE);
  assert(p2_kind_name(P2_D2_POWER_REF_6660_TX)[0]=='d');
  puts("24 dev22 read-only service-shape assertions OK");return 0;
}
