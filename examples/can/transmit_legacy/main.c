/* Software classic-CAN base-format bit pattern on PB0, 20 kbit/s.
 * 11-bit ID 0x123, DE AD; CRC-15 and stuffing included. ACK remains recessive:
 * this is a single-pin teaching stimulus, not an arbitration/error/retry stack.
 */
#include "soft_tx.h"
static uint8_t raw[128];
static uint16_t raw_len;
static void raw_bit(uint8_t b) { raw[raw_len++] = b != 0; }
static void raw_word(uint32_t value, uint8_t width)
{
    while (width) { --width; raw_bit((value >> width) & 1u); }
}
int main(void)
{
    raw_bit(0); raw_word(0x123, 11);
    raw_bit(0); raw_bit(0); raw_bit(0); /* RTR, IDE, r0 */
    raw_word(2, 4); raw_word(0xde, 8); raw_word(0xad, 8);
    uint16_t crc = 0;
    for (uint16_t i = 0; i < raw_len; ++i) {
        uint8_t feedback = ((crc >> 14) & 1u) ^ raw[i];
        crc = (crc << 1) & 0x7fffu;
        if (feedback) crc ^= 0x4599u;
    }
    raw_word(crc, 15);
    uint8_t previous = 2, run = 0;
    for (uint16_t i = 0; i < raw_len; ++i) {
        uint8_t b = raw[i]; bit(b);
        run = b == previous ? run + 1u : 1u; previous = b;
        if (run == 5) { bit(!b); previous = !b; run = 1; }
    }
    bit(1); bit(1); bit(1); /* CRC delimiter, unacknowledged ACK, ACK delimiter */
    for (uint8_t i = 0; i < 7 + 3 + 16; ++i) bit(1);
    soft_tx_start(20000);
    for (;;) ++student_loop_count;
}
