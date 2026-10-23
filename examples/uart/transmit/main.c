/* Software UART TX on PB0, 9600 8N1. No USART peripheral is enabled. */
#include "soft_tx.h"
int main(void)
{
    const char *s = "Hello BluePill\r\n";
    while (*s) uart_byte((uint8_t)*s++);
    for (uint8_t i = 0; i < 10; ++i) bit(1);
    soft_tx_start(9600);
    for (;;) ++student_loop_count;
}
