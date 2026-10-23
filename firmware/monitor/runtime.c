#include "board.h"
#include "usb_cdc.h"
#include "layout.h"
#include "capture.h"
#include "stimulus.h"

extern uint32_t _estack, _ram_vectors, _stack_limit;
extern const uintptr_t vectors[VECTOR_COUNT];
void monitor_service(void);
void monitor_vectors_init(void);
void Fault_Record(uint32_t *frame, uint32_t exc_return) __attribute__((noreturn));
void Fault_Handler(void);
void reboot_to_mode(uint32_t safe) __attribute__((noreturn));

__attribute__((section(".mailbox"), used)) volatile boot_mailbox_t boot_mailbox;
volatile uint32_t student_running, boot_reason, image_error, monitor_ticks;
static volatile uint32_t usb_irq_ready;

static uint32_t crc_step(uint32_t crc, uint8_t value)
{
    crc ^= value;
    for (uint8_t bit = 0; bit < 8; ++bit)
        crc = (crc >> 1) ^ ((0u - (crc & 1u)) & 0xedb88320u);
    return crc;
}
uint32_t crc32_bytes(const uint8_t *data, uint32_t len)
{
    uint32_t crc = 0xffffffffu;
    while (len--) crc = crc_step(crc, *data++);
    return ~crc;
}
static uint32_t image_validate(void)
{
    const image_manifest_t *m = (const image_manifest_t *)B_MANIFEST;
    const uint32_t *v = (const uint32_t *)B_FLASH_BASE;
    if (m->magic != IMAGE_MAGIC || m->version != IMAGE_VERSION) return 1;
    if (m->size < 0x240u || m->size > B_FLASH_SIZE || m->flash_base != B_FLASH_BASE ||
        m->ram_base != B_RAM_BASE || m->ram_end != B_RAM_END) return 2;
    if (v[0] <= B_RAM_BASE || v[0] > B_RAM_END || (v[0] & 7u) ||
        !(v[1] & 1u) || v[1] != m->entry ||
        (v[1] & ~1u) < B_FLASH_BASE + 0x240u ||
        (v[1] & ~1u) >= B_FLASH_BASE + m->size) return 3;
    for (uint32_t i = 2; i < VECTOR_COUNT; ++i) {
        if (v[i] && (!(v[i] & 1u) || (v[i] & ~1u) < B_FLASH_BASE + 0x240u ||
                     (v[i] & ~1u) >= B_FLASH_BASE + m->size)) return 4;
    }
    uint32_t crc = 0xffffffffu;
    const uint8_t *image = (const uint8_t *)B_FLASH_BASE;
    for (uint32_t i = 0; i < m->size; ++i)
        crc = crc_step(crc, i >= 0x200u && i < 0x240u ? 0 : image[i]);
    return ~crc == m->crc32 ? 0 : 5;
}

void SysTick_Handler(void)
{
    ++milliseconds;
    ++monitor_ticks;
    if (usb_irq_ready) REG32(0xe000e200u) = 1u << 20;
}
void USB_LP_CAN1_RX0_IRQHandler(void)
{
    /* All CDC queue/parser access is serialized here. Bound each visit. */
    for (uint32_t n = 0; n < 32; ++n) {
        usb_cdc_poll();
        monitor_service();
        if (!(REG16(0x40005c44u) & 0xfc00u)) break;
    }
}
void USB_HP_CAN1_TX_IRQHandler(void) { USB_LP_CAN1_RX0_IRQHandler(); }
void USBWakeUp_IRQHandler(void)
{
    REG32(0x40010414u) = 1u << 18;
}
void Default_Handler(void)
{
    /* A malformed/unhandled IRQ becomes a recorded fault, never a stuck IRQ. */
    __asm volatile ("udf #0");
    for (;;) {}
}
void reboot_to_mode(uint32_t safe)
{
    __asm volatile ("cpsid i" ::: "memory");
    stimulus_stop(4);
    boot_mailbox.magic = MAILBOX_MAGIC;
    boot_mailbox.guard = MAILBOX_GUARD;
    boot_mailbox.safe = safe;
    __asm volatile ("dsb" ::: "memory");
    REG32(0xe000ed0cu) = 0x05fa0004u;
    for (;;) {}
}
void Fault_Record(uint32_t *frame, uint32_t exc_return)
{
    __asm volatile ("cpsid i" ::: "memory");
    boot_mailbox.fault_pc = 0;
    boot_mailbox.fault_lr = exc_return;
    uint32_t addr = (uint32_t)frame;
    if (((addr >= A_RAM_BASE && addr <= A_RAM_BASE + A_RAM_SIZE - 32u) ||
         (addr >= B_RAM_BASE && addr <= B_RAM_END - 32u)) && !(addr & 3u)) {
        boot_mailbox.fault_pc = frame[6];
        boot_mailbox.fault_lr = frame[5];
    }
    boot_mailbox.cfsr = REG32(0xe000ed28u);
    boot_mailbox.hfsr = REG32(0xe000ed2cu);
    boot_mailbox.bfar = REG32(0xe000ed38u);
    reboot_to_mode(2); /* Recorded fault, stay in A until explicit RUN. */
}
__attribute__((naked)) void Fault_Handler(void)
{
    __asm volatile (
        "tst lr, #4\n"
        "ite eq\n"
        "mrseq r0, msp\n"
        "mrsne r0, psp\n"
        "mov r1, lr\n"
        "b Fault_Record\n");
}
static int monitor_owned(uint32_t vector)
{
    return vector < 7 || vector == 15 || vector == 16 + 12 || vector == 16 + 15 ||
           vector == 16 + 19 || vector == 16 + 20 || vector == 16 + 28 ||
           vector == 16 + 27 || vector == 16 + 42;
}
static void install_student_vectors(void)
{
    uint32_t *ram = &_ram_vectors;
    const uint32_t *b = (const uint32_t *)B_FLASH_BASE;
    for (uint32_t i = 2; i < VECTOR_COUNT; ++i)
        if (!monitor_owned(i) && b[i]) ram[i] = b[i];
    __asm volatile ("dsb\nisb" ::: "memory");
}
__attribute__((naked, noreturn)) static void enter_student(uint32_t sp, uint32_t pc)
{
    (void)sp; (void)pc;
    __asm volatile (
        "cpsid i\n"
        "msr psp, r0\n"
        "ldr r2, =_estack\n"
        "msr msp, r2\n"
        "movs r2, #2\n" /* privileged Thread mode on PSP; handlers use A MSP */
        "msr control, r2\n"
        "isb\n"
        "cpsie i\n"
        "bx r1\n");
}

int main(void)
{
    monitor_vectors_init();
    if (boot_mailbox.magic != MAILBOX_MAGIC || boot_mailbox.guard != MAILBOX_GUARD ||
        (REG32(0x40021024u) & (1u << 27))) { /* PORRSTF: power-on clears requests. */
        volatile uint32_t *p = (volatile uint32_t *)&boot_mailbox;
        for (uint32_t i = 0; i < sizeof(boot_mailbox) / 4u; ++i) p[i] = 0;
        boot_mailbox.magic = MAILBOX_MAGIC;
        boot_mailbox.guard = MAILBOX_GUARD;
    }
    REG32(0x40021024u) |= 1u << 24; /* RMVF */
    if (!board_init()) for (;;) { board_led(1); }
    /* PB12 pull-up: strap to GND at reset forces physical Safe Boot. */
    REG32(0x40021018u) |= 1u << 3;
    REG32(0x40010c10u) = 1u << 12;
    REG32(0x40010c04u) = (REG32(0x40010c04u) & ~(15u << 16)) | (8u << 16);
    board_delay(5); /* Let the weak pull-up and input synchronizer settle. */
    uint32_t pin_safe = !(REG32(0x40010c08u) & (1u << 12));
    REG32(0xe000ed0cu) = 0x05fa0300u; /* 4 preemption priority bits */
    for (uint32_t irq = 0; irq < 60; ++irq)
        *(volatile uint8_t *)(0xe000e400u + irq) = 0x80;
    *(volatile uint8_t *)0xe000e40cu = 0x10; /* DMA1 CH2 */
    *(volatile uint8_t *)0xe000e40fu = 0x10; /* CH5 refill preempts USB CRC/parse */
    *(volatile uint8_t *)0xe000e41bu = 0x10; /* TIM1_CC bounded pad resolver */
    *(volatile uint8_t *)0xe000e413u = 0x20; /* USB HP */
    *(volatile uint8_t *)0xe000e414u = 0x20; /* USB LP */
    *(volatile uint8_t *)0xe000ed23u = 0x40; /* SysTick */
    REG32(0xe000ed24u) |= 7u << 16; /* Fault reporting */
    REG32(0xe000edfcu) |= 1u << 24; /* DWT cycle timestamps */
    REG32(0xe0001004u) = 0;
    REG32(0xe0001000u) |= 1u;
    image_error = image_validate();
    boot_reason = pin_safe ? 3u : boot_mailbox.safe ?
                  (boot_mailbox.safe == 2 ? 5u : 4u) : image_error ? 2u : 1u;
    usb_cdc_init();
    usb_irq_ready = 1;
    usb_cdc_irq_enable();
    uint32_t start = milliseconds;
    while ((uint32_t)(milliseconds - start) < 1000u) __asm volatile ("wfi");
    if (boot_reason == 1) {
        install_student_vectors();
        student_running = 1;
        const uint32_t *b = (const uint32_t *)B_FLASH_BASE;
        enter_student(b[0], b[1]);
    }
    for (;;) __asm volatile ("wfi");
}
