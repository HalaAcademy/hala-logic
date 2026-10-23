#include "board.h"
#include "layout.h"
extern uint32_t _estack, _sidata, _sdata, _edata, _sbss, _ebss, _ram_vectors;
extern uint32_t _stack_limit;
int main(void);
void Reset_Handler(void);
void DMA1_Channel2_IRQHandler(void);
void DMA1_Channel5_IRQHandler(void);
void TIM1_CC_IRQHandler(void);
void Default_Handler(void);
void Fault_Handler(void);
void SysTick_Handler(void);
void USBWakeUp_IRQHandler(void);
void USB_HP_CAN1_TX_IRQHandler(void);
void USB_LP_CAN1_RX0_IRQHandler(void);
__attribute__((section(".isr_vector"), used))
const uintptr_t vectors[VECTOR_COUNT] = {
    (uintptr_t)&_estack, /* 0 */
    (uintptr_t)Reset_Handler, /* 1 */
    (uintptr_t)Fault_Handler, /* 2 */
    (uintptr_t)Fault_Handler, /* 3 */
    (uintptr_t)Fault_Handler, /* 4 */
    (uintptr_t)Fault_Handler, /* 5 */
    (uintptr_t)Fault_Handler, /* 6 */
    (uintptr_t)Default_Handler, /* 7 */
    (uintptr_t)Default_Handler, /* 8 */
    (uintptr_t)Default_Handler, /* 9 */
    (uintptr_t)Default_Handler, /* 10 */
    (uintptr_t)Default_Handler, /* 11 */
    (uintptr_t)Default_Handler, /* 12 */
    (uintptr_t)Default_Handler, /* 13 */
    (uintptr_t)Default_Handler, /* 14 */
    (uintptr_t)SysTick_Handler, /* 15 */
    (uintptr_t)Default_Handler, /* 16 */
    (uintptr_t)Default_Handler, /* 17 */
    (uintptr_t)Default_Handler, /* 18 */
    (uintptr_t)Default_Handler, /* 19 */
    (uintptr_t)Default_Handler, /* 20 */
    (uintptr_t)Default_Handler, /* 21 */
    (uintptr_t)Default_Handler, /* 22 */
    (uintptr_t)Default_Handler, /* 23 */
    (uintptr_t)Default_Handler, /* 24 */
    (uintptr_t)Default_Handler, /* 25 */
    (uintptr_t)Default_Handler, /* 26 */
    (uintptr_t)Default_Handler, /* 27 */
    (uintptr_t)DMA1_Channel2_IRQHandler, /* 28 */
    (uintptr_t)Default_Handler, /* 29 */
    (uintptr_t)Default_Handler, /* 30 */
    (uintptr_t)DMA1_Channel5_IRQHandler, /* 31 */
    (uintptr_t)Default_Handler, /* 32 */
    (uintptr_t)Default_Handler, /* 33 */
    (uintptr_t)Default_Handler, /* 34 */
    (uintptr_t)USB_HP_CAN1_TX_IRQHandler, /* 35 */
    (uintptr_t)USB_LP_CAN1_RX0_IRQHandler, /* 36 */
    (uintptr_t)Default_Handler, /* 37 */
    (uintptr_t)Default_Handler, /* 38 */
    (uintptr_t)Default_Handler, /* 39 */
    (uintptr_t)Default_Handler, /* 40 */
    (uintptr_t)Default_Handler, /* 41 */
    (uintptr_t)Default_Handler, /* 42 */
    (uintptr_t)TIM1_CC_IRQHandler, /* 43 */
    (uintptr_t)Default_Handler, /* 44 */
    (uintptr_t)Default_Handler, /* 45 */
    (uintptr_t)Default_Handler, /* 46 */
    (uintptr_t)Default_Handler, /* 47 */
    (uintptr_t)Default_Handler, /* 48 */
    (uintptr_t)Default_Handler, /* 49 */
    (uintptr_t)Default_Handler, /* 50 */
    (uintptr_t)Default_Handler, /* 51 */
    (uintptr_t)Default_Handler, /* 52 */
    (uintptr_t)Default_Handler, /* 53 */
    (uintptr_t)Default_Handler, /* 54 */
    (uintptr_t)Default_Handler, /* 55 */
    (uintptr_t)Default_Handler, /* 56 */
    (uintptr_t)Default_Handler, /* 57 */
    (uintptr_t)USBWakeUp_IRQHandler, /* 58 */
    (uintptr_t)Default_Handler, /* 59 */
    (uintptr_t)Default_Handler, /* 60 */
    (uintptr_t)Default_Handler, /* 61 */
    (uintptr_t)Default_Handler, /* 62 */
    (uintptr_t)Default_Handler, /* 63 */
    (uintptr_t)Default_Handler, /* 64 */
    (uintptr_t)Default_Handler, /* 65 */
    (uintptr_t)Default_Handler, /* 66 */
    (uintptr_t)Default_Handler, /* 67 */
    (uintptr_t)Default_Handler, /* 68 */
    (uintptr_t)Default_Handler, /* 69 */
    (uintptr_t)Default_Handler, /* 70 */
    (uintptr_t)Default_Handler, /* 71 */
    (uintptr_t)Default_Handler, /* 72 */
    (uintptr_t)Default_Handler, /* 73 */
    (uintptr_t)Default_Handler, /* 74 */
    (uintptr_t)Default_Handler, /* 75 */
};
void monitor_vectors_init(void)
{
    uint32_t *dst = &_ram_vectors;
    for (uint32_t i = 0; i < VECTOR_COUNT; ++i) dst[i] = (uint32_t)vectors[i];
    __asm volatile ("dsb" ::: "memory");
    REG32(0xe000ed08u) = (uint32_t)dst;
    __asm volatile ("isb" ::: "memory");
}
void Reset_Handler(void)
{
    uint32_t sp;
    __asm volatile ("mrs %0, msp" : "=r" (sp));
    for (uint32_t *dst = &_stack_limit; (uint32_t)dst + 128u < sp; ++dst)
        *dst = 0xa55a55a5u;
    uint32_t *src = &_sidata;
    for (uint32_t *dst = &_sdata; dst < &_edata; ++dst) *dst = *src++;
    for (uint32_t *dst = &_sbss; dst < &_ebss; ++dst) *dst = 0;
    (void)main();
    for (;;) {}
}
