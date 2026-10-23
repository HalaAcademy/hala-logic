#include "board.h"

#define RCC_CR      REG32(0x40021000u)
#define RCC_CFGR    REG32(0x40021004u)
#define RCC_APB2ENR REG32(0x40021018u)
#define FLASH_ACR   REG32(0x40022000u)
#define GPIOC_CRH   REG32(0x40011004u)
#define GPIOC_BSRR  REG32(0x40011010u)

volatile uint32_t milliseconds;
/* 0=OK, 1=HSE timeout, 2=PLL timeout, 3=SYSCLK switch timeout. */
volatile uint32_t clock_error;

static int wait_bits(volatile uint32_t *reg, uint32_t mask, uint32_t value)
{
    for (uint32_t i = 0; i < 2000000u; ++i)
        if ((*reg & mask) == value) return 1;
    return 0;
}

int board_init(void)
{
    uint32_t hz = 8000000u;
    RCC_APB2ENR |= (1u << 2) | (1u << 4); /* GPIO A, C */
    board_led(0);
    GPIOC_CRH = (GPIOC_CRH & ~(0xfu << 20)) | (2u << 20);

    RCC_CR |= 1u << 16; /* Blue Pill crystal: 8 MHz HSE. */
    if (!wait_bits(&RCC_CR, 1u << 17, 1u << 17)) {
        clock_error = 1;
    } else {
        FLASH_ACR = (1u << 4) | 2u; /* Prefetch, two wait states. */
        /* PLL=HSE*9=72 MHz; APB1=36 MHz; USB=PLL/1.5=48 MHz. */
        RCC_CFGR = (7u << 18) | (1u << 16) | (4u << 8);
        RCC_CR |= 1u << 24;
        if (!wait_bits(&RCC_CR, 1u << 25, 1u << 25)) {
            clock_error = 2;
        } else {
            RCC_CFGR = (RCC_CFGR & ~3u) | 2u;
            if (!wait_bits(&RCC_CFGR, 3u << 2, 2u << 2))
                clock_error = 3;
            else
                hz = 72000000u;
        }
    }
    REG32(0xe000e014u) = hz / 1000u - 1u;
    REG32(0xe000e018u) = 0;
    REG32(0xe000e010u) = 7u;
    return clock_error == 0;
}

#ifndef RESIDENT_MONITOR
void SysTick_Handler(void) { ++milliseconds; }
#endif
void board_led(uint32_t on)
{
    GPIOC_BSRR = on ? (1u << 29) : (1u << 13);
}
void board_delay(uint32_t ms)
{
    uint32_t start = milliseconds;
    while ((uint32_t)(milliseconds - start) < ms) {}
}
