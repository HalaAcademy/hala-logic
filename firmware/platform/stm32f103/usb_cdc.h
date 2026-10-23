#ifndef USB_CDC_H
#define USB_CDC_H
#include <stdint.h>

typedef struct {
    uint32_t resets, setups, rx_bytes, tx_bytes, rx_packets, tx_packets;
    uint32_t errors, suspends, configured, address, control_lines, session;
} usb_stats_t;
extern volatile usb_stats_t usb_stats;

void usb_cdc_init(void);
void usb_cdc_poll(void);
uint16_t usb_cdc_read(uint8_t *data, uint16_t max_len);
uint16_t usb_cdc_tx_free(void);
/* Atomic enqueue: returns 1 if the entire payload fits, otherwise 0. */
int usb_cdc_write(const uint8_t *data, uint16_t len);
void usb_cdc_irq_enable(void);
int usb_cdc_tx_idle(void);
#endif
