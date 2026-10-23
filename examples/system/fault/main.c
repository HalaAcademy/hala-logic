/* Intentionally fault after ~one second. Used only for recovery acceptance. */
#include <stdint.h>
volatile uint32_t fault_delay;
int main(void)
{
    for (fault_delay = 0; fault_delay < 5000000u; ++fault_delay) {}
    __asm volatile ("udf #7");
    for (;;) {}
}
