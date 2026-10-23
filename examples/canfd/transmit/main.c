/* ISO FD 11/29 software TX, 64 bytes, BRS 1k->2k; ACK observer, single-shot
 * cyclic teaching mode (no arbitration/retry/error-confinement claim).
 */
#define WAVE_CAPACITY 1024u
#include "sw_wave_tx.h"
#ifndef CANFD_EXTENDED
#define CANFD_EXTENDED 0
#endif
static uint8_t raw[553];
static uint32_t raw_length,c17=1u<<16,c21=1u<<20,last,run,stuff;
static void field(uint32_t value,uint32_t n)
{
    for(int i=(int)n-1;i>=0;--i)raw[raw_length++]=(uint8_t)((value>>i)&1u);
}
static void feed(uint32_t bit)
{
    c17=crc_step(c17,bit,17,0x1685b);c21=crc_step(c21,bit,21,0x102899);
}
int main(void)
{
    for(uint32_t i=0;i<12;++i)emit(1,4);
    field(0,1);
    if(CANFD_EXTENDED){field(0x12345678u>>18,11);field(1,1);field(1,1);field(0x12345678u&0x3ffff,18);field(0,1);field(1,1);field(0,1);}
    else {field(0x5aa,11);field(0,1);field(0,1);field(1,1);field(0,1);}
    field(1,1);field(0,1);field(15,4);
    uint32_t brs_index=raw_length-6;
    for(uint32_t i=0;i<64;++i)field(i,8);
    last=1;run=0;
    for(uint32_t i=0;i<raw_length;++i) {
        uint32_t b=raw[i];emit(b,i==brs_index ? 3 : i>brs_index ? 2 : 4);feed(b);
        run=b==last ? run+1 : 1;last=b;
        if(run==5 && i+1<raw_length) {
            last=1-b;emit(last,i>=brs_index ? 2 : 4);feed(last);run=1;++stuff;
        }
    }
    uint32_t gray=(stuff&7u)^((stuff&7u)>>1);
    uint32_t sc=(gray<<1)|((gray^(gray>>1)^(gray>>2))&1u);
    for(int i=3;i>=0;--i)feed((sc>>i)&1u);
    uint32_t crc=c21;
    for(uint32_t i=0;i<25;++i) {
        if(!(i&3u)){last=1-last;emit(last,2);}
        uint32_t b=i<4 ? (sc>>(3-i))&1u : (crc>>(24-i))&1u;
        emit(b,2);last=b;
    }
    emit(1,3); /* mixed CRC delimiter at 50% sample point */
    ack_entry=wave_length;emit(1,4);
    for(uint32_t i=0;i<23;++i)emit(1,4); /* ACK delim + EOF7 + IFS3 + idle12 */
    start();for(;;)++student_loop_count;
}
