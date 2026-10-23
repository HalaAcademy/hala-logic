/* Classical CAN 11/29-bit data/remote RX, 1000 bit/s, 16x TIM4 sampling.
 * PB8 reads REAL bus pad. PB0 is TX intent/ACK output; the generic pad
 * resolver ANDs physical PB0 and peer PB10 into PB8, without an external wire.
 * This lesson validates frame RX/CRC/stuffing/ACK; no error-confinement
 * or arbitration implementation is claimed by this file.
 */
#include <stdint.h>
#define R(a) (*(volatile uint32_t *)(a))
volatile uint32_t rx_count, rx_errors, rx_crc_errors, rx_stuff_errors, rx_form_errors;
volatile uint32_t rx_id, rx_dlc, ack_count, student_irq_count, student_loop_count;
volatile uint32_t rx_extended,rx_remote;
volatile uint32_t student_max_lateness_ticks;
volatile uint8_t rx_data[8];
static uint8_t raw[118];
static uint32_t active, idle, wait, size, target, run, previous, complete, footer;
static uint32_t header,remote;
static uint32_t ack_wait, ack_hold;

static void error(uint32_t kind)
{
    ++rx_errors;
    if (kind==1) ++rx_crc_errors;
    else if (kind==2) ++rx_stuff_errors;
    else ++rx_form_errors;
    active=idle=0;
}

static uint32_t value(uint32_t start, uint32_t n)
{
    uint32_t v=0;
    while(n--) v=(v<<1)|raw[start++];
    return v;
}

static void sampled_bit(uint32_t bit)
{
    if (complete==2) {
        if (footer==0) {
            if (!bit) { error(3); return; }
            ack_wait=8; /* from delimiter sample centre to ACK slot boundary */
        } else if (footer>=2 && !bit) { error(3); return; }
        if (++footer==10) { /* CRC delim + ACK + ACK delim + seven EOF */
            rx_extended=header==39;rx_remote=remote;
            rx_id=rx_extended ? (value(1,11)<<18)|value(14,18) : value(1,11);
            rx_dlc=value(header-4,4);
            for(uint32_t i=0;i<8;++i)rx_data[i]=i<rx_dlc && !remote ? (uint8_t)value(header+i*8,8) : 0;
            ++rx_count; active=0; idle=8*16; /* ACK delimiter + seven EOF */
        }
        return;
    }
    if (run==5) {
        if (bit==previous) { error(2); return; }
        previous=bit; run=1;
        if (complete) { complete=2; footer=0; }
        return;
    }
    run=bit==previous ? run+1 : 1;
    previous=bit;
    if (size>=sizeof(raw)) { error(3); return; }
    raw[size++]=(uint8_t)bit;
    if(size==14)header=raw[13] ? 39 : 19;
    if (size==header) {
        uint32_t dlc=value(header-4,4);
        if (dlc>8) { error(3); return; }
        remote=raw[header==39 ? 32 : 12];
        target=header+(remote ? 0 : dlc*8)+15;
    }
    if (size==target) {
        uint32_t crc=0;
        for(uint32_t i=0;i<size-15;++i) {
            uint32_t feedback=((crc>>14)&1u)^raw[i];
            crc=(crc<<1)&0x7fffu;
            if(feedback) crc^=0x4599u;
        }
        if(crc!=value(size-15,15)) { error(1); return; }
        complete=run==5 ? 1 : 2; footer=0;
    }
}

void TIM4_IRQHandler(void)
{
    R(0x40000810u)=0;
    uint32_t late=R(0x40000824u);
    if(late>student_max_lateness_ticks) student_max_lateness_ticks=late;
    ++student_irq_count;
    if(ack_wait && !--ack_wait) {
        R(0x40010c10u)=1u<<16; ack_hold=16; ++ack_count;
    } else if(ack_hold && !--ack_hold) R(0x40010c10u)=1;
    uint32_t bit=(R(0x40010c08u)>>8)&1u;
    if(!active) {
        if(bit) { if(idle<1000) ++idle; }
        else {
            if(idle>=11*16) {
                active=1; wait=8; size=run=complete=footer=0;
                previous=1; target=header=0xffffffffu;
            }
            idle=0;
        }
    } else if(!--wait) { sampled_bit(bit); wait=16; }
}

int main(void)
{
    R(0x40021018u)|=1u<<3;
    R(0x40010c10u)=(1u<<8)|1u;
    R(0x40010c04u)=(R(0x40010c04u)&~15u)|8u;
    R(0x40010c00u)=(R(0x40010c00u)&~15u)|2u;
    R(0x4002101cu)|=1u<<2;
    R(0x40000828u)=0; R(0x4000082cu)=4499;
    R(0x40000814u)=1; R(0x40000810u)=0; R(0x4000080cu)=1;
    *(volatile uint8_t *)0xe000e41eu=0x10;
    R(0xe000e100u)=1u<<30; R(0x40000800u)=1;
    for(;;) ++student_loop_count;
}
