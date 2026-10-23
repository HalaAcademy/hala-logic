/* Student-local GPIO/timer helper; no dependency on monitor API. */
#ifndef STUDENT_SOFT_TX_H
#define STUDENT_SOFT_TX_H
#include <stdint.h>
#define R(a) (*(volatile uint32_t *)(a))
static uint8_t tx_bits[256];
static uint16_t tx_length;
static volatile uint16_t tx_index;
volatile uint32_t student_frames;
volatile uint32_t student_loop_count;
volatile uint32_t student_max_lateness_ticks;
static void bit(uint8_t value) { tx_bits[tx_length++] = value != 0; }
static void uart_byte(uint8_t value) __attribute__((unused));
static void uart_byte(uint8_t value)
{
    bit(0);
    for (uint8_t i = 0; i < 8; ++i) bit((value >> i) & 1u);
    bit(1);
}
void TIM4_IRQHandler(void)
{
    R(0x40000810u) = 0;
    uint32_t late = R(0x40000824u); /* TIM4 ticks since scheduled update. */
    if (late > student_max_lateness_ticks) student_max_lateness_ticks = late;
    R(0x40010c10u) = tx_bits[tx_index] ? 1u : 1u << 16;
    if (++tx_index == tx_length) { tx_index = 0; ++student_frames; }
}
static void soft_tx_start(uint32_t baud)
{
    R(0x40021018u) |= 1u << 3; /* GPIOB */
    R(0x40010c10u) = 1;
    R(0x40010c00u) = (R(0x40010c00u) & ~15u) | 2u; /* PB0 GPIO, NOT AF */
    R(0x4002101cu) |= 1u << 2; /* TIM4 */
    R(0x40000828u) = 0;
    R(0x4000082cu) = 72000000u / baud - 1u;
    R(0x40000814u) = 1; R(0x40000810u) = 0;
    R(0x4000080cu) = 1;
    /* A timing-critical, SHORT timer ISR can preempt USB (priority 0x20).
     * Default application IRQ priority is 0x80. GPIO bit-banging needs this explicit
     * scheduling choice; a long/hung high-priority ISR would starve USB service.
     */
    *(volatile uint8_t *)0xe000e41eu = 0x10; /* TIM4_IRQn = 30 */
    R(0xe000e100u) = 1u << 30;
    R(0x40000800u) = 1;
}
#endif
