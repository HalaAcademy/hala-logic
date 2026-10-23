/* ISO FD 11/29 software RX/ACK, nominal 1000 / BRS data 2000 bit/s.
 * Physical PB8 IDR + PB0 ACK, 32kHz TIM4. No FDCAN/bxCAN/USART or monitor APIs.
 * Implements data frames/all DLC, CRC17/21, ISO stuff count + fixed stuffing.
 * First teaching lesson, not full arbitration/error-confinement implementation.
 */
#include <stdint.h>
#define R(a) (*(volatile uint32_t *)(a))
volatile uint32_t rx_count,rx_errors,rx_crc_errors,rx_stuff_errors,rx_form_errors;
volatile uint32_t rx_id,rx_length,rx_brs,rx_esi,ack_count,student_loop_count,student_irq_count;
volatile uint32_t rx_extended;
volatile uint32_t student_max_lateness_ticks;
volatile uint32_t student_max_irq_gap_us;
volatile uint8_t rx_data[64];
static uint8_t raw[553];
static const uint8_t lengths[16]={0,1,2,3,4,5,6,7,8,12,16,20,24,32,48,64};
static uint32_t active,idle,deadline,period,size,target,run,previous,phase;
static uint32_t header;
static uint32_t crc17,crc21,stuff_count,crc_width,field_size,field,expected_fixed;
static uint32_t crc_value,footer,ack_phase,ack_at,ack_off,last_irq;

static uint32_t update_crc(uint32_t crc,uint32_t bit,uint32_t width,uint32_t poly)
{
    uint32_t feedback=((crc>>(width-1))&1u)^bit;
    crc=(crc<<1)&((1u<<width)-1u);
    return feedback ? crc^poly : crc;
}
static void feed_crc(uint32_t bit)
{
    crc17=update_crc(crc17,bit,17,0x1685b);
    crc21=update_crc(crc21,bit,21,0x102899);
}
static uint32_t value(uint32_t start,uint32_t n)
{
    uint32_t v=0;
    while(n--)v=(v<<1)|raw[start++];
    return v;
}
static void error(uint32_t kind)
{
    ++rx_errors;
    if(kind==1)++rx_crc_errors;
    else if(kind==2)++rx_stuff_errors;
    else ++rx_form_errors;
    active=idle=ack_phase=0;
    R(0x40010c10u)=1;
}
static void sampled_bit(uint32_t bit)
{
    if(phase==2) {
        if(footer==0) {
            if(!bit){error(3);return;}
            period=1000;ack_at=(deadline+500u)&65535u;
            ack_off=(ack_at+1000u)&65535u;ack_phase=1;
        } else if(footer>=2 && !bit){error(3);return;}
        if(++footer==10) {
            rx_extended=header==41;
            rx_id=rx_extended ? (value(1,11)<<18)|value(14,18) : value(1,11);
            rx_length=lengths[value(header-4,4)];
            rx_brs=raw[header-6];rx_esi=raw[header-5];
            for(uint32_t i=0;i<rx_length;++i)rx_data[i]=(uint8_t)value(header+i*8,8);
            ++rx_count;active=0;idle=8*32;
        }
        return;
    }
    if(phase==1) {
        if(expected_fixed) {
            if(bit==previous){error(3);return;}
            previous=bit;expected_fixed=0;return;
        }
        previous=bit;
        field=(field<<1)|bit;
        ++field_size;
        if(field_size<=4)feed_crc(bit);
        if(field_size==4) {
            uint32_t gray=(stuff_count&7u)^((stuff_count&7u)>>1);
            uint32_t parity=(gray^(gray>>1)^(gray>>2))&1u;
            if(field!=((gray<<1)|parity)){error(2);return;}
            field=0;crc_value=crc_width==17 ? crc17 : crc21;
        }
        if(field_size==crc_width+4) {
            if(field!=crc_value){error(1);return;}
            phase=2;footer=0;
        } else if(!(field_size&3u))expected_fixed=1;
        return;
    }
    feed_crc(bit); /* physical stream includes dynamic stuff bits */
    if(run==5) {
        if(bit==previous){error(2);return;}
        ++stuff_count;run=1;previous=bit;return;
    }
    run=bit==previous ? run+1 : 1;previous=bit;
    if(size>=sizeof(raw)){error(3);return;}
    raw[size++]=(uint8_t)bit;
    if(size==14)header=raw[13] ? 41 : 22;
    if(size==header-5 && bit)period=500; /* BRS sample point switches to data bit time */
    if(size==header) {
        if(raw[header==41 ? 32 : 12]||!raw[header-8]||raw[header-7]){error(3);return;}
        uint32_t length=lengths[value(header-4,4)];
        target=header+length*8;crc_width=length<=16 ? 17 : 21;
    }
    if(size==target) {phase=1;field=field_size=0;expected_fixed=1;}
}
void TIM4_IRQHandler(void)
{
    R(0x40000810u)=0;
    uint32_t late=R(0x40000824u);
    if(late>student_max_lateness_ticks)student_max_lateness_ticks=late;
    ++student_irq_count;
    uint32_t now=R(0x40000424u)&65535u; /* TIM3 free-running microseconds */
    uint32_t gap=(now-last_irq)&65535u;last_irq=now;
    if(gap>student_max_irq_gap_us)student_max_irq_gap_us=gap;
    if(ack_phase==1 && (int16_t)(now-ack_at)>=0){R(0x40010c10u)=1u<<16;ack_phase=2;++ack_count;}
    else if(ack_phase==2 && (int16_t)(now-ack_off)>=0){R(0x40010c10u)=1;ack_phase=0;}
    uint32_t bit=(R(0x40010c08u)>>8)&1u;
    if(!active) {
        if(bit){if(idle<1000)++idle;}
        else {
            if(idle>=11*32) {
                active=1;deadline=(now+500u)&65535u;period=1000;size=run=phase=stuff_count=0;
                previous=1;header=22;target=0xffffffffu;crc17=1u<<16;crc21=1u<<20;
            }
            idle=0;
        }
    } else if((int16_t)(now-deadline)>=0){
        sampled_bit(bit);deadline=(deadline+period)&65535u;
    }
}
int main(void)
{
    R(0x40021018u)|=1u<<3;R(0x40010c10u)=(1u<<8)|1;
    R(0x40010c04u)=(R(0x40010c04u)&~15u)|8;
    R(0x40010c00u)=(R(0x40010c00u)&~15u)|2;
    R(0x4002101cu)|=(1u<<2)|(1u<<1);
    R(0x40000428u)=71;R(0x4000042cu)=65535;
    R(0x40000414u)=1;R(0x40000400u)=1;
    R(0x40000828u)=0;R(0x4000082cu)=2249;
    R(0x40000814u)=1;R(0x40000810u)=0;R(0x4000080cu)=1;
    *(volatile uint8_t *)0xe000e41eu=0x10;
    R(0xe000e100u)=1u<<30;R(0x40000800u)=1;
    for(;;)++student_loop_count;
}
