/* Software LIN-shaped master frame, PB0, 9600 baud: ID 0x12, data 34 56.
 * Logic-level demonstrator, not a LIN transceiver or a complete LIN scheduler.
 */
#include "soft_tx.h"
int main(void)
{
    const uint8_t pid = 0x92, data0 = 0x34, data1 = 0x56;
    for (uint8_t i = 0; i < 13; ++i) bit(0);
    bit(1);
    uart_byte(0x55); uart_byte(pid); uart_byte(data0); uart_byte(data1);
    uint16_t sum = (uint16_t)pid + data0 + data1;
    while (sum > 255u) sum = (sum & 255u) + (sum >> 8);
    uart_byte((uint8_t)~sum);
    for (uint8_t i = 0; i < 20; ++i) bit(1);
    soft_tx_start(9600);
    for (;;) ++student_loop_count;
}
