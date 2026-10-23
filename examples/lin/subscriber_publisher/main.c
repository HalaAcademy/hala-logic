/* LIN software slave, 1000 bit/s. REAL PB8 RX/PB0 TX. No monitor calls.
 * Frame table: ID12 subscriber (2 bytes), ID22 publisher (34 56).
 * The fixture resolves device TX + host peer into PB8; no external jumper or LIN controller.
 */
#include <stdint.h>
#define R(a) (*(volatile uint32_t *)(a))
volatile uint32_t rx_count, rx_errors, pid_errors, checksum_errors, publisher_count;
volatile uint32_t rx_id, rx_pid, student_loop_count, student_irq_count;
volatile uint32_t student_max_lateness_ticks;
volatile uint8_t rx_data[2];
static uint32_t uart_state, uart_wait, uart_bit, uart_value, last=1, low_ticks;
static uint32_t lin_state, pid, index, sum;
static uint8_t data[2];
static uint16_t tx_words[3];
static uint32_t tx_delay, tx_index, tx_bits, tx_word;

static uint32_t protected_id(uint32_t id)
{
    uint32_t p0=((id>>0)^(id>>1)^(id>>2)^(id>>4))&1u;
    uint32_t p1=(~((id>>1)^(id>>3)^(id>>4)^(id>>5)))&1u;
    return id|(p0<<6)|(p1<<7);
}
static uint32_t checksum(uint32_t total)
{
    while(total>255) total=(total&255)+(total>>8);
    return (~total)&255;
}
static void received(uint32_t byte)
{
    if(lin_state==1) { lin_state=byte==0x55 ? 2 : 0; }
    else if(lin_state==2) {
        pid=byte;
        if(protected_id(pid&63)!=pid) { ++rx_errors; ++pid_errors; lin_state=0; return; }
        if((pid&63)==0x12) { lin_state=3; index=0; sum=pid; }
        else if((pid&63)==0x22) {
            uint32_t bytes[3]={0x34,0x56,checksum(pid+0x34+0x56)};
            for(uint32_t i=0;i<3;++i) tx_words[i]=(uint16_t)((1u<<9)|(bytes[i]<<1));
            tx_index=0; tx_bits=0; tx_delay=24; lin_state=0; ++publisher_count;
        } else lin_state=0;
    } else if(lin_state==3) {
        if(index<2) { data[index++]=(uint8_t)byte; sum+=byte; }
        else {
            if(byte==checksum(sum)) {
                rx_id=pid&63; rx_pid=pid;
                rx_data[0]=data[0]; rx_data[1]=data[1]; ++rx_count;
            } else { ++rx_errors; ++checksum_errors; }
            lin_state=0;
        }
    }
}
void TIM4_IRQHandler(void)
{
    R(0x40000810u)=0;
    uint32_t late=R(0x40000824u);
    if(late>student_max_lateness_ticks) student_max_lateness_ticks=late;
    ++student_irq_count;
    uint32_t level=(R(0x40010c08u)>>8)&1u;
    if(!level) {
        if(low_ticks<1000) ++low_ticks;
        if(low_ticks==11*16) { lin_state=1; uart_state=0; }
    } else low_ticks=0;
    if(low_ticks<11*16) {
        if(!uart_state) {
            if(last && !level) { uart_state=1; uart_wait=8; }
        } else if(!--uart_wait) {
            if(uart_state==1) {
                if(level) uart_state=0;
                else { uart_state=2; uart_bit=uart_value=0; uart_wait=16; }
            } else if(uart_state==2) {
                uart_value|=level<<uart_bit;
                if(++uart_bit==8) uart_state=3;
                uart_wait=16;
            } else { if(level) received(uart_value); uart_state=0; }
        }
    }
    last=level;
    if(tx_delay && !--tx_delay) {
        if(!tx_bits && tx_index<3) { tx_word=tx_words[tx_index++]; tx_bits=10; }
        if(tx_bits) {
            R(0x40010c10u)=tx_word&1 ? 1u : 1u<<16;
            tx_word>>=1; --tx_bits; tx_delay=16;
        }
    }
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
