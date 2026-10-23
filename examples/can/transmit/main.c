/* Classical CAN software frame TX, nominal 1000 bit/s.
 * Compile-time 11/29-bit and DATA/RTR variants. Real PB0 BSRR and PB8 IDR.
 * ACK observation only: no automatic retry/arbitration/error-state machine.
 */
#define WAVE_CAPACITY 256u
#include "sw_wave_tx.h"
#ifndef CAN_EXTENDED
#define CAN_EXTENDED 0
#endif
#ifndef CAN_REMOTE
#define CAN_REMOTE 0
#endif
static uint8_t raw[118];
static uint32_t raw_length;
static void field(uint32_t value,uint32_t n)
{
    for(int i=(int)n-1;i>=0;--i)raw[raw_length++]=(uint8_t)((value>>i)&1u);
}
int main(void)
{
    static const uint8_t payload[8]={0,255,85,170,0,255,0,255};
    uint32_t id=CAN_EXTENDED ? 0x12345678u : 0x123u;
    for(uint32_t i=0;i<12;++i)emit(1,4);
    field(0,1);
    if(CAN_EXTENDED){field(id>>18,11);field(1,1);field(1,1);field(id&0x3ffff,18);}
    else field(id,11);
    field(CAN_REMOTE,1);
    field(0,1);field(0,1);field(8,4);
    if(!CAN_REMOTE)for(uint32_t i=0;i<8;++i)field(payload[i],8);
    uint32_t crc=0;
    for(uint32_t i=0;i<raw_length;++i)crc=crc_step(crc,raw[i],15,0x4599);
    field(crc,15);
    uint32_t last=1,run=0;
    for(uint32_t i=0;i<raw_length;++i){
        uint32_t b=raw[i];emit(b,4);
        run=b==last ? run+1 : 1;last=b;
        if(run==5){last=1-b;emit(last,4);run=1;}
    }
    emit(1,4); /* CRC delimiter */
    ack_entry=wave_length;emit(1,4);
    for(uint32_t i=0;i<23;++i)emit(1,4); /* ACK delimiter/EOF/IFS/idle */
    start();for(;;)++student_loop_count;
}
