/* Bai GPIO: truy cap thanh ghi, khong goi API monitor. */
#include <stdint.h>
#define R(a) (*(volatile uint32_t *)(a))
volatile uint32_t student_loop_count;
volatile uint32_t student_irq_count;
void TIM4_IRQHandler(void)
{
    R(0x40000810u) = 0;
    ++student_irq_count;
}
int main(void)
{
    R(0x40021018u) |= 1u << 3; /* GPIOB */
    R(0x40010c00u) = (R(0x40010c00u) & ~15u) | 0xbu; /* PB0 TIM3_CH3 */
    R(0x4002101cu) |= (1u << 1) | (1u << 2); /* TIM3, TIM4 */
    R(0x40000428u) = 71; R(0x4000042cu) = 999; R(0x4000043cu) = 500;
    R(0x4000041cu) = (6u << 4) | (1u << 3); /* OC3 PWM1, preload */
    R(0x40000420u) = 1u << 8;
    R(0x40000414u) = 1;
    R(0x40000400u) = (1u << 7) | 1u; /* 1 kHz, 50% PWM */
    R(0x40000828u) = 71; R(0x4000082cu) = 999;
    R(0x40000814u) = 1; R(0x40000810u) = 0;
    R(0x4000080cu) = 1;
    R(0xe000e100u) = 1u << 30; /* TIM4_IRQn */
    R(0x40000800u) = 1;
    for (;;) ++student_loop_count; /* Main remains busy while USB and capture keep working. */
}
