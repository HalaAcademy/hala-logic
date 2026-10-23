/* FR21A-TEACH static FRAME software TX: ID123 cycle7, 254 payload bytes.
 * Frame codec only; not a cluster scheduler. PB0 GPIO, TIM4 quarter-bit ISR.
 */
#include "sw_wave_tx.h"
int main(void)
{
    uint32_t id=0x123,words=127,cycle=7,header_crc=0x1a;
    uint32_t input=(id<<7)|words;
    for(int i=19;i>=0;--i)header_crc=crc_step(header_crc,(input>>i)&1u,11,0x385);
    uint8_t header[5]={(uint8_t)(0x20|(id>>8)),(uint8_t)id,
        (uint8_t)((words<<1)|(header_crc>>10)),(uint8_t)(header_crc>>2),
        (uint8_t)(((header_crc&3u)<<6)|cycle)};
    for(uint32_t i=0;i<12;++i)emit(1,4);
    for(uint32_t i=0;i<9;++i)emit(0,4);
    emit(1,4);
#ifdef CHANNEL_B
    uint32_t crc=0xabcdef;
#else
    uint32_t crc=0xfedcba;
#endif
    for(uint32_t n=0;n<259;++n) {
        uint32_t byte=n<5 ? header[n] : n-5;
        for(int bit=7;bit>=0;--bit)crc=crc_step(crc,(byte>>bit)&1u,24,0x5d6dcb);
        byte_out(byte);
    }
    byte_out(crc>>16);byte_out((crc>>8)&255);byte_out(crc&255);
    emit(0,4);emit(1,4);
    for(uint32_t i=0;i<12;++i)emit(1,4);
    start();for(;;)++student_loop_count;
}
