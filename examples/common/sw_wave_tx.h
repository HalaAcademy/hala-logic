/* Student-local GPIO timing/CRC helpers, no resident monitor API. */
#include <stdint.h>
#define R(a) (*(volatile uint32_t *)(a))
#ifndef WAVE_CAPACITY
#define WAVE_CAPACITY 4096u
#endif
static uint8_t wave[WAVE_CAPACITY];
static uint32_t wave_length,tx_index,tx_wait,current_entry;
static uint32_t ack_entry=0xffffffffu;
volatile uint32_t student_frames,student_loop_count,student_irq_count;
volatile uint32_t tx_ack_count,tx_no_ack_count,student_max_lateness_ticks;
static void emit(uint32_t level,uint32_t quarters)
{
    if(wave_length>=WAVE_CAPACITY)__asm volatile("udf #0");
    wave[wave_length++]=(uint8_t)((quarters<<1)|!!level);
}
static uint32_t crc_step(uint32_t c,uint32_t b,uint32_t width,uint32_t poly)
{
    uint32_t f=((c>>(width-1))&1u)^b;c=(c<<1)&((1u<<width)-1u);
    return f ? c^poly : c;
}
static inline void byte_out(uint32_t byte)
{
    emit(1,4);emit(0,4); /* FlexRay BSS, not UART start/stop */
    for(int i=7;i>=0;--i)emit((byte>>i)&1u,4);
}
void TIM4_IRQHandler(void)
{
    R(0x40000810u)=0;
    uint32_t late=R(0x40000824u);
    if(late>student_max_lateness_ticks)student_max_lateness_ticks=late;
    ++student_irq_count;
    if(!tx_wait) {
        if(tx_index==wave_length){tx_index=0;++student_frames;}
        current_entry=tx_index;
        uint32_t entry=wave[tx_index++];
        R(0x40010c10u)=entry&1u ? 1u : 1u<<16;
        tx_wait=entry>>1;
    }
    if(current_entry==ack_entry && tx_wait==2) {
        if(!(R(0x40010c08u)&(1u<<8)))++tx_ack_count;else ++tx_no_ack_count;
    }
    --tx_wait;
}
static void start(void)
{
    R(0x40021018u)|=1u<<3;R(0x40010c10u)=(1u<<8)|1;
    R(0x40010c00u)=(R(0x40010c00u)&~15u)|2;
    R(0x40010c04u)=(R(0x40010c04u)&~15u)|8;
    R(0x4002101cu)|=1u<<2;
    R(0x40000828u)=0;R(0x4000082cu)=17999; /* 4kHz, quarter of 1kbit */
    R(0x40000814u)=1;R(0x40000810u)=0;R(0x4000080cu)=1;
    *(volatile uint8_t *)0xe000e41eu=0x10;R(0xe000e100u)=1u<<30;R(0x40000800u)=1;
}
