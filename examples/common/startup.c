#include <stdint.h>
extern uint32_t _estack, _sidata, _sdata, _edata, _sbss, _ebss;
extern uint32_t _stack_limit;
int main(void);
void Reset_Handler(void);
void Default_Handler(void);
void NMI_Handler(void) __attribute__((weak, alias("Default_Handler")));
void HardFault_Handler(void) __attribute__((weak, alias("Default_Handler")));
void MemManage_Handler(void) __attribute__((weak, alias("Default_Handler")));
void BusFault_Handler(void) __attribute__((weak, alias("Default_Handler")));
void UsageFault_Handler(void) __attribute__((weak, alias("Default_Handler")));
void SVC_Handler(void) __attribute__((weak, alias("Default_Handler")));
void DebugMon_Handler(void) __attribute__((weak, alias("Default_Handler")));
void PendSV_Handler(void) __attribute__((weak, alias("Default_Handler")));
void SysTick_Handler(void) __attribute__((weak, alias("Default_Handler")));
void WWDG_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void PVD_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void TAMPER_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void RTC_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void FLASH_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void RCC_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void EXTI0_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void EXTI1_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void EXTI2_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void EXTI3_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void EXTI4_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void DMA1_Channel1_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void DMA1_Channel2_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void DMA1_Channel3_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void DMA1_Channel4_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void DMA1_Channel5_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void DMA1_Channel6_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void DMA1_Channel7_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void ADC1_2_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void USB_HP_CAN1_TX_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void USB_LP_CAN1_RX0_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void CAN1_RX1_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void CAN1_SCE_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void EXTI9_5_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void TIM1_BRK_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void TIM1_UP_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void TIM1_TRG_COM_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void TIM1_CC_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void TIM2_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void TIM3_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void TIM4_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void I2C1_EV_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void I2C1_ER_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void I2C2_EV_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void I2C2_ER_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void SPI1_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void SPI2_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void USART1_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void USART2_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void USART3_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void EXTI15_10_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void RTCAlarm_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void USBWakeUp_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void ReservedIRQ43_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void ReservedIRQ44_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void ReservedIRQ45_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void ReservedIRQ46_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void ReservedIRQ47_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void ReservedIRQ48_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void ReservedIRQ49_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void ReservedIRQ50_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void ReservedIRQ51_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void ReservedIRQ52_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void ReservedIRQ53_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void ReservedIRQ54_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void ReservedIRQ55_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void ReservedIRQ56_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void ReservedIRQ57_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void ReservedIRQ58_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));
void ReservedIRQ59_IRQHandler(void) __attribute__((weak, alias("Default_Handler")));

__attribute__((section(".manifest"), used))
const uint8_t student_manifest[64] = {0};

__attribute__((section(".isr_vector"), used))
const uintptr_t vectors[76] = {
    (uintptr_t)&_estack, /* 0 */
    (uintptr_t)Reset_Handler, /* 1 */
    (uintptr_t)NMI_Handler, /* 2 */
    (uintptr_t)HardFault_Handler, /* 3 */
    (uintptr_t)MemManage_Handler, /* 4 */
    (uintptr_t)BusFault_Handler, /* 5 */
    (uintptr_t)UsageFault_Handler, /* 6 */
    0, /* 7 */
    0, /* 8 */
    0, /* 9 */
    0, /* 10 */
    (uintptr_t)SVC_Handler, /* 11 */
    (uintptr_t)DebugMon_Handler, /* 12 */
    0, /* 13 */
    (uintptr_t)PendSV_Handler, /* 14 */
    (uintptr_t)SysTick_Handler, /* 15 */
    (uintptr_t)WWDG_IRQHandler, /* 16 */
    (uintptr_t)PVD_IRQHandler, /* 17 */
    (uintptr_t)TAMPER_IRQHandler, /* 18 */
    (uintptr_t)RTC_IRQHandler, /* 19 */
    (uintptr_t)FLASH_IRQHandler, /* 20 */
    (uintptr_t)RCC_IRQHandler, /* 21 */
    (uintptr_t)EXTI0_IRQHandler, /* 22 */
    (uintptr_t)EXTI1_IRQHandler, /* 23 */
    (uintptr_t)EXTI2_IRQHandler, /* 24 */
    (uintptr_t)EXTI3_IRQHandler, /* 25 */
    (uintptr_t)EXTI4_IRQHandler, /* 26 */
    (uintptr_t)DMA1_Channel1_IRQHandler, /* 27 */
    (uintptr_t)DMA1_Channel2_IRQHandler, /* 28 */
    (uintptr_t)DMA1_Channel3_IRQHandler, /* 29 */
    (uintptr_t)DMA1_Channel4_IRQHandler, /* 30 */
    (uintptr_t)DMA1_Channel5_IRQHandler, /* 31 */
    (uintptr_t)DMA1_Channel6_IRQHandler, /* 32 */
    (uintptr_t)DMA1_Channel7_IRQHandler, /* 33 */
    (uintptr_t)ADC1_2_IRQHandler, /* 34 */
    (uintptr_t)USB_HP_CAN1_TX_IRQHandler, /* 35 */
    (uintptr_t)USB_LP_CAN1_RX0_IRQHandler, /* 36 */
    (uintptr_t)CAN1_RX1_IRQHandler, /* 37 */
    (uintptr_t)CAN1_SCE_IRQHandler, /* 38 */
    (uintptr_t)EXTI9_5_IRQHandler, /* 39 */
    (uintptr_t)TIM1_BRK_IRQHandler, /* 40 */
    (uintptr_t)TIM1_UP_IRQHandler, /* 41 */
    (uintptr_t)TIM1_TRG_COM_IRQHandler, /* 42 */
    (uintptr_t)TIM1_CC_IRQHandler, /* 43 */
    (uintptr_t)TIM2_IRQHandler, /* 44 */
    (uintptr_t)TIM3_IRQHandler, /* 45 */
    (uintptr_t)TIM4_IRQHandler, /* 46 */
    (uintptr_t)I2C1_EV_IRQHandler, /* 47 */
    (uintptr_t)I2C1_ER_IRQHandler, /* 48 */
    (uintptr_t)I2C2_EV_IRQHandler, /* 49 */
    (uintptr_t)I2C2_ER_IRQHandler, /* 50 */
    (uintptr_t)SPI1_IRQHandler, /* 51 */
    (uintptr_t)SPI2_IRQHandler, /* 52 */
    (uintptr_t)USART1_IRQHandler, /* 53 */
    (uintptr_t)USART2_IRQHandler, /* 54 */
    (uintptr_t)USART3_IRQHandler, /* 55 */
    (uintptr_t)EXTI15_10_IRQHandler, /* 56 */
    (uintptr_t)RTCAlarm_IRQHandler, /* 57 */
    (uintptr_t)USBWakeUp_IRQHandler, /* 58 */
    (uintptr_t)ReservedIRQ43_IRQHandler, /* 59 */
    (uintptr_t)ReservedIRQ44_IRQHandler, /* 60 */
    (uintptr_t)ReservedIRQ45_IRQHandler, /* 61 */
    (uintptr_t)ReservedIRQ46_IRQHandler, /* 62 */
    (uintptr_t)ReservedIRQ47_IRQHandler, /* 63 */
    (uintptr_t)ReservedIRQ48_IRQHandler, /* 64 */
    (uintptr_t)ReservedIRQ49_IRQHandler, /* 65 */
    (uintptr_t)ReservedIRQ50_IRQHandler, /* 66 */
    (uintptr_t)ReservedIRQ51_IRQHandler, /* 67 */
    (uintptr_t)ReservedIRQ52_IRQHandler, /* 68 */
    (uintptr_t)ReservedIRQ53_IRQHandler, /* 69 */
    (uintptr_t)ReservedIRQ54_IRQHandler, /* 70 */
    (uintptr_t)ReservedIRQ55_IRQHandler, /* 71 */
    (uintptr_t)ReservedIRQ56_IRQHandler, /* 72 */
    (uintptr_t)ReservedIRQ57_IRQHandler, /* 73 */
    (uintptr_t)ReservedIRQ58_IRQHandler, /* 74 */
    (uintptr_t)ReservedIRQ59_IRQHandler, /* 75 */
};
void Reset_Handler(void)
{
    uint32_t sp;
    __asm volatile ("mrs %0, psp" : "=r" (sp));
    for (uint32_t *dst = &_stack_limit; (uint32_t)dst + 128u < sp; ++dst)
        *dst = 0xb55b55b5u;
    /* Clock, VTOR, priorities and PSP are already configured at entry. */
    uint32_t *src = &_sidata;
    for (uint32_t *dst = &_sdata; dst < &_edata; ++dst) *dst = *src++;
    for (uint32_t *dst = &_sbss; dst < &_ebss; ++dst) *dst = 0;
    (void)main();
    __asm volatile ("udf #1");
    for (;;) {}
}
void Default_Handler(void) { __asm volatile ("udf #2"); for (;;) {} }
