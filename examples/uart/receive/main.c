/* UART GPIO/timer lesson: PB8 RX, PB0 TX, 1000 baud 8N1.
 * This program uses REAL GPIO_IDR/BSRR. The no-jumper fixture
 * drives PB8's output stage after this init; the pad input buffer stays on.
 * The program echoes each received byte XOR 0x20, providing a fresh RX oracle.
 */
#include <stdint.h>
#define R(a) (*(volatile uint32_t *)(a))
#ifndef BAUD
#define BAUD 1000u
#endif
volatile uint32_t rx_count, rx_errors, rx_false_starts, rx_dropped;
volatile uint32_t student_loop_count, student_irq_count, student_max_lateness_ticks;
volatile uint8_t rx_buffer[64];
static volatile uint16_t tx_queue[64];
static volatile uint32_t tx_head, tx_tail;
static uint32_t rx_state, rx_wait, rx_value, rx_bit, previous = 1;
static uint32_t tx_wait, tx_word, tx_bits;

void TIM4_IRQHandler(void)
{
    R(0x40000810u) = 0;
    uint32_t late = R(0x40000824u);
    if (late > student_max_lateness_ticks) student_max_lateness_ticks = late;
    ++student_irq_count;
    uint32_t level = (R(0x40010c08u) >> 8) & 1u;
    if (!rx_state) {
        if (previous && !level) { rx_state = 1; rx_wait = 8; }
    } else if (!--rx_wait) {
        if (rx_state == 1) {
            if (level) { ++rx_false_starts; rx_state = 0; }
            else { rx_state = 2; rx_value = rx_bit = 0; rx_wait = 16; }
        } else if (rx_state == 2) {
            rx_value |= level << rx_bit;
            if (++rx_bit == 8) rx_state = 3;
            rx_wait = 16;
        } else {
            if (level) {
                rx_buffer[rx_count & 63u] = (uint8_t)rx_value;
                ++rx_count;
            } else ++rx_errors;
            rx_state = 0;
        }
    }
    previous = level;
    if (tx_wait) --tx_wait;
    if (!tx_wait) {
        if (!tx_bits && tx_tail != tx_head) {
            tx_word = tx_queue[tx_tail];
            tx_tail = (tx_tail + 1u) & 63u;
            tx_bits = 10;
        }
        if (tx_bits) {
            R(0x40010c10u) = tx_word & 1u ? 1u : 1u << 16;
            tx_word >>= 1; --tx_bits; tx_wait = 16;
        }
    }
}

int main(void)
{
    R(0x40021018u) |= 1u << 3;
    R(0x40010c10u) = (1u << 8) | 1u;
    R(0x40010c04u) = (R(0x40010c04u) & ~15u) | 8u; /* PB8 input pull-up */
    R(0x40010c00u) = (R(0x40010c00u) & ~15u) | 2u; /* PB0 output */
    R(0x4002101cu) |= 1u << 2;
    R(0x40000828u) = 0;
    R(0x4000082cu) = 72000000u / (BAUD * 16u) - 1u;
    R(0x40000814u) = 1; R(0x40000810u) = 0;
    R(0x4000080cu) = 1;
    *(volatile uint8_t *)0xe000e41eu = 0x10;
    R(0xe000e100u) = 1u << 30;
    R(0x40000800u) = 1;
    uint32_t consumed = 0;
    for (;;) {
        ++student_loop_count;
        if (consumed != rx_count) {
            if (rx_count - consumed > 64u) {
                ++rx_dropped; consumed = rx_count; continue;
            }
            uint32_t next = (tx_head + 1u) & 63u;
            if (next != tx_tail) {
                uint32_t value = rx_buffer[consumed++ & 63u] ^ 0x20u;
                tx_queue[tx_head] = (uint16_t)((1u << 9) | (value << 1));
                __asm volatile ("dmb" ::: "memory");
                tx_head = next;
            }
        }
    }
}
