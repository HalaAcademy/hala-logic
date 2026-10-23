ENTRY(Reset_Handler)
MEMORY {
    FLASH (rx) : ORIGIN = 0x08000000, LENGTH = 24K
    RAM (rwx)  : ORIGIN = 0x20000000, LENGTH = 12K
}
_estack = ORIGIN(RAM) + LENGTH(RAM);
_stack_limit = _estack - 2048;
SECTIONS {
    .isr_vector : { KEEP(*(.isr_vector)) } > FLASH
    .text : { *(.text*) *(.rodata*) . = ALIGN(4); } > FLASH
    .ram_vectors (NOLOAD) : {
        . = ALIGN(512); _ram_vectors = .; . += 512;
    } > RAM
    .mailbox (NOLOAD) : { KEEP(*(.mailbox)) } > RAM
    ASSERT(ADDR(.ram_vectors) == 0x20000000, "RAM VTOR moved")
    ASSERT(ADDR(.mailbox) == 0x20000200, "mailbox moved")
    ASSERT(SIZEOF(.mailbox) == 32, "mailbox size")
    .data : {
        . = ALIGN(4); _sdata = .; *(.data*) . = ALIGN(4); _edata = .;
    } > RAM AT > FLASH
    _sidata = LOADADDR(.data);
    .bss (NOLOAD) : {
        . = ALIGN(4); _sbss = .; *(.bss*) *(COMMON) . = ALIGN(4); _ebss = .;
    } > RAM
    ASSERT(_ebss <= _stack_limit, "A RAM collides with 2 KiB exception stack")
    .stack _stack_limit (NOLOAD) : { . += 2048; } > RAM
    /DISCARD/ : { *(.comment) *(.note*) *(.ARM.exidx*) *(.ARM.extab*) }
}
