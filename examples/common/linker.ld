ENTRY(Reset_Handler)
MEMORY {
    FLASH (rx) : ORIGIN = 0x08006000, LENGTH = 40K
    RAM (rwx)  : ORIGIN = 0x20003000, LENGTH = 8K
}
_estack = ORIGIN(RAM) + LENGTH(RAM);
_stack_limit = _estack - 1024;
/* Explicit PHDRS keep ELF headers/padding out of the load image. Otherwise
 * GNU ld's 64 KiB maximum page size can create a PT_LOAD starting before the application region. */
PHDRS {
    flash PT_LOAD FLAGS(5);
    data PT_LOAD FLAGS(6);
    stack PT_LOAD FLAGS(6);
}
SECTIONS {
    .isr_vector : { KEEP(*(.isr_vector)) } > FLASH :flash
    ASSERT(SIZEOF(.isr_vector) <= 512, "Application vector table exceeds 512 bytes")
    .manifest 0x08006200 : { KEEP(*(.manifest)) } > FLASH :flash
    ASSERT(SIZEOF(.manifest) == 64, "Application manifest must be 64 bytes")
    .text : { *(.text*) *(.rodata*) . = ALIGN(4); } > FLASH :flash
    .data : {
        . = ALIGN(4); _sdata = .; *(.data*) . = ALIGN(4); _edata = .;
    } > RAM AT > FLASH :data
    _sidata = LOADADDR(.data);
    .bss (NOLOAD) : {
        . = ALIGN(4); _sbss = .; *(.bss*) *(COMMON) . = ALIGN(4); _ebss = .;
    } > RAM :data
    ASSERT(_ebss <= _stack_limit, "Application RAM collides with 1 KiB thread stack")
    .stack _stack_limit (NOLOAD) : { . += 1024; } > RAM :stack
    /DISCARD/ : { *(.comment) *(.note*) *(.ARM.exidx*) *(.ARM.extab*) }
}
