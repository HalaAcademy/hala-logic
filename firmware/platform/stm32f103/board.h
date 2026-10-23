#ifndef BOARD_H
#define BOARD_H
#include <stdint.h>
#define REG32(a) (*(volatile uint32_t *)(a))
#define REG16(a) (*(volatile uint16_t *)(a))
extern volatile uint32_t milliseconds;
extern volatile uint32_t clock_error;
int board_init(void);
void board_led(uint32_t on);
void board_delay(uint32_t ms);
#endif
