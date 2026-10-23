/* FR21A-TEACH static frame codec RX only, REAL PB8 IDR, 1kbit/s, 16kHz poll.
 * TSS/FSS/BSS/FES, header CRC11, channel-specific CRC24, payload 0..254 even.
 * No cluster startup/sync/scheduler claim. PB0 toggles on valid app delivery.
 * Standard C + TIM3/TIM4, no monitor API, no hardware FlexRay peripheral.
 */
#include <stdint.h>
#define R(a) (*(volatile uint32_t *)(a))
#ifdef CHANNEL_B
#define FRAME_SEED 0xabcdefu
#else
#define FRAME_SEED 0xfedcbau
#endif
volatile uint32_t rx_count,rx_errors,header_errors,frame_errors,format_errors;
volatile uint32_t rx_id,rx_length,rx_cycle,student_loop_count,student_irq_count;
volatile uint32_t student_max_lateness_ticks;
volatile uint8_t rx_data[254];
static uint8_t bytes[262];
static uint32_t phase,idle,low_at,deadline,byte_index,bit_index,byte_value,target,crc;
static volatile uint32_t frame_ready;
static uint32_t step(uint32_t c,uint32_t b,uint32_t width,uint32_t poly)
{
    uint32_t f=((c>>(width-1))&1u)^b;c=(c<<1)&((1u<<width)-1u);
    return f ? c^poly : c;
}
static void error(uint32_t kind)
{
    ++rx_errors;
    if(kind==1)++header_errors;else if(kind==2)++frame_errors;else ++format_errors;
    phase=idle=0;
}
static void sampled(uint32_t bit)
{
    if(phase==2) {
        if(bit){error(3);return;}
        phase=3;bit_index=byte_value=0;
    } else if(phase==3) {
        if(byte_index<target-3)crc=step(crc,bit,24,0x5d6dcb);
        byte_value=(byte_value<<1)|bit;
        if(++bit_index==8) {
            bytes[byte_index++]=(uint8_t)byte_value;
            if(byte_index==5) {
                uint32_t id=((bytes[0]&7u)<<8)|bytes[1];
                uint32_t words=bytes[2]>>1;
                uint32_t hc=((bytes[2]&1u)<<10)|(bytes[3]<<2)|(bytes[4]>>6);
                uint32_t input=(((bytes[0]>>3)&3u)<<18)|(id<<7)|words;
                uint32_t check=0x1a;
                for(int i=19;i>=0;--i)check=step(check,(input>>i)&1u,11,0x385);
                if(check!=hc){error(1);return;}
                if(!id){error(3);return;}
                target=8+words*2;
            }
            phase=byte_index==target ? 5 : 4;
        }
    } else if(phase==4) {
        if(!bit){error(3);return;}
        phase=2;
    } else if(phase==5) {
        if(bit){error(3);return;}phase=6;
    } else {
        if(!bit){error(3);return;}
        uint32_t received=(bytes[target-3]<<16)|(bytes[target-2]<<8)|bytes[target-1];
        if(crc!=received){error(2);return;}
        frame_ready=1;phase=idle=0;
    }
}
void TIM4_IRQHandler(void)
{
    R(0x40000810u)=0;
    uint32_t late=R(0x40000824u);
    if(late>student_max_lateness_ticks)student_max_lateness_ticks=late;
    ++student_irq_count;
    uint32_t now=R(0x40000424u)&65535u;
    uint32_t bit=(R(0x40010c08u)>>8)&1u;
    if(!phase) {
        if(bit){if(idle<1000)++idle;}
        else if(idle>=12*16){phase=1;low_at=now;idle=0;}
        else idle=0;
    } else if(phase==1) {
        if(bit) {
            if(((now-low_at)&65535u)<8800u){error(3);return;}
            phase=2;deadline=(now+2500)&65535u;
            byte_index=bit_index=byte_value=0;target=262;crc=FRAME_SEED;
        }
    } else if((int16_t)(now-deadline)>=0){sampled(bit);deadline=(deadline+1000)&65535u;}
}
int main(void)
{
    R(0x40021018u)|=1u<<3;R(0x40010c10u)=(1u<<8)|1;
    R(0x40010c04u)=(R(0x40010c04u)&~15u)|8;
    R(0x40010c00u)=(R(0x40010c00u)&~15u)|2;
    R(0x4002101cu)|=(1u<<1)|(1u<<2);
    R(0x40000428u)=71;R(0x4000042cu)=65535;R(0x40000414u)=1;R(0x40000400u)=1;
    R(0x40000828u)=0;R(0x4000082cu)=4499;
    R(0x40000814u)=1;R(0x40000810u)=0;R(0x4000080cu)=1;
    *(volatile uint8_t *)0xe000e41eu=0x10;R(0xe000e100u)=1u<<30;R(0x40000800u)=1;
    for(;;){
        ++student_loop_count;
        if(frame_ready) {
            uint32_t length=(bytes[2]>>1)*2u;
            for(uint32_t i=0;i<length;++i)rx_data[i]=bytes[5+i];
            rx_id=((bytes[0]&7u)<<8)|bytes[1];rx_length=length;rx_cycle=bytes[4]&63u;
            ++rx_count;R(0x40010c10u)=rx_count&1u ? 1 : 1u<<16;frame_ready=0;
        }
    }
}
