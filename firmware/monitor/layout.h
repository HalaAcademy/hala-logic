#ifndef AB_LAYOUT_H
#define AB_LAYOUT_H
#include <stdint.h>
#define A_FLASH_BASE 0x08000000u
#define A_FLASH_SIZE 0x00006000u
#define B_FLASH_BASE 0x08006000u
#define B_FLASH_SIZE 0x0000a000u
#define B_MANIFEST   (B_FLASH_BASE + 0x200u)
#define A_RAM_BASE   0x20000000u
#define A_RAM_SIZE   0x00003000u
#define B_RAM_BASE   0x20003000u
#define B_RAM_END    0x20005000u
#define VECTOR_COUNT 76u
#define MAILBOX_ADDR 0x20000200u
#define MAILBOX_MAGIC 0x53414645u
#define MAILBOX_GUARD 0xacbeb9bau
#define IMAGE_MAGIC 0x42414250u
#define IMAGE_VERSION 1u
typedef struct {
    uint32_t magic, version, size, crc32, flash_base, ram_base, ram_end, entry;
    uint8_t sha256[32];
} image_manifest_t;
typedef struct {
    uint32_t magic, safe, guard, fault_pc, fault_lr, cfsr, hfsr, bfar;
} boot_mailbox_t;
uint32_t crc32_bytes(const uint8_t *data, uint32_t len);
#endif
