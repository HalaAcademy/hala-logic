/* STM32F103 USB FS device + CDC ACM, direct register access, no HAL/SPL.
 * Register semantics: ST RM0008, USB chapter. All calls run in main context.
 */
#include "board.h"
#include "usb_cdc.h"

#define EP(n)       REG16(0x40005c00u + 4u * (n))
#define USB_CNTR    REG16(0x40005c40u)
#define USB_ISTR    REG16(0x40005c44u)
#define USB_DADDR   REG16(0x40005c4cu)
#define USB_BTABLE  REG16(0x40005c50u)
#define CTR_RX 0x8000u
#define DTOG_RX 0x4000u
#define STAT_RX 0x3000u
#define SETUP 0x0800u
#define CTR_TX 0x0080u
#define DTOG_TX 0x0040u
#define STAT_TX 0x0030u
#define EP_NORMAL 0x070fu /* TYPE, KIND, address; excludes toggle/rc_w0 bits. */
#define RX_VALID 0x3000u
#define RX_NAK 0x2000u
#define RX_STALL 0x1000u
#define TX_VALID 0x0030u
#define TX_NAK 0x0020u
#define TX_STALL 0x0010u
#define EP0_RX 0x0040u
#define EP0_TX 0x0080u
#define EP1_RX 0x00c0u
#define EP1_TX 0x0100u
#define EP2_TX 0x0140u
#define QSIZE 2048u
#define QMASK (QSIZE - 1u)
#ifdef RESIDENT_MONITOR
#define RX_QSIZE 1024u
#else
#define RX_QSIZE QSIZE
#endif
#define RX_QMASK (RX_QSIZE - 1u)

/* pid.codes 1209:0001 is for private testing only, NOT a unique product ID.
 * Obtain your own VID/PID before distributing/manufacturing devices.
 */
static const uint8_t device_descriptor[] = {
    18, 1, 0x00, 0x02, 0x02, 0x00, 0x00, 64,
    0x09, 0x12, 0x01, 0x00, 0x00, 0x02, 1, 2, 3, 1
};
static const uint8_t config_descriptor[] = {
    9, 2, 67, 0, 2, 1, 0, 0x80, 50,
    9, 4, 0, 0, 1, 0x02, 0x02, 0x01, 0,
    5, 0x24, 0x00, 0x10, 0x01,       /* CDC 1.10 */
    5, 0x24, 0x01, 0x00, 1,          /* Call management */
    4, 0x24, 0x02, 0x02,             /* ACM: line coding/control supported */
    5, 0x24, 0x06, 0, 1,             /* Union: control IF0, data IF1 */
    7, 5, 0x82, 0x03, 16, 0, 16,    /* Interrupt IN notifications */
    9, 4, 1, 0, 2, 0x0a, 0x00, 0x00, 0,
    7, 5, 0x01, 0x02, 64, 0, 0,     /* Bulk OUT */
    7, 5, 0x81, 0x02, 64, 0, 0      /* Bulk IN */
};
_Static_assert(sizeof(config_descriptor) == 67, "configuration length");

volatile usb_stats_t usb_stats;
static uint8_t rx_queue[RX_QSIZE], tx_queue[QSIZE];
static uint16_t rx_head, rx_tail, tx_head, tx_tail;
static uint8_t tx_busy, tx_need_zlp, tx_inflight, notify_pending;
static uint8_t line_coding[7] = {0x00, 0xc2, 0x01, 0x00, 0, 0, 8};
static uint8_t ctrl_buffer[64];
static const uint8_t *ctrl_ptr;
static uint16_t ctrl_remaining;
static uint8_t ctrl_zlp;
static int16_t pending_address = -1, pending_config = -1;
enum { CTRL_IDLE, CTRL_DATA_IN, CTRL_STATUS_OUT, CTRL_LINE_OUT, CTRL_STATUS_IN };
static uint8_t ctrl_state;

/* PMA has one 16-bit word per 32-bit CPU slot. Offsets are USB byte offsets. */
static void pma_put(uint16_t offset, uint16_t value)
{
    REG16(0x40006000u + 2u * offset) = value;
}
static uint16_t pma_get(uint16_t offset)
{
    return REG16(0x40006000u + 2u * offset);
}
static void pma_write(uint16_t offset, const uint8_t *data, uint16_t len)
{
    for (uint16_t i = 0; i < len; i += 2) {
        uint16_t value = data[i];
        if (i + 1u < len) value |= (uint16_t)data[i + 1u] << 8;
        pma_put(offset + i, value);
    }
}
static void pma_read(uint8_t *data, uint16_t offset, uint16_t len)
{
    for (uint16_t i = 0; i < len; i += 2) {
        uint16_t value = pma_get(offset + i);
        data[i] = (uint8_t)value;
        if (i + 1u < len) data[i + 1u] = (uint8_t)(value >> 8);
    }
}

/* EPnR mixes normal, toggle-on-write-1, and clear-on-write-0 fields.
 * Never use |= or &= on this register. Preserve both CTR bits unless clearing.
 */
static void ep_status(uint8_t ep, uint16_t mask, uint16_t desired)
{
    uint16_t old = EP(ep);
    EP(ep) = (old & EP_NORMAL) | CTR_RX | CTR_TX | ((old ^ desired) & mask);
}
static void ep_clear_ctr(uint8_t ep, uint16_t flag)
{
    EP(ep) = (EP(ep) & EP_NORMAL) | ((CTR_RX | CTR_TX) & ~flag);
}
static void ep_reset(uint8_t ep, uint16_t type)
{
    uint16_t old = EP(ep);
    EP(ep) = type | ep | (old & (DTOG_RX | DTOG_TX | STAT_RX | STAT_TX));
}
static void ep_clear_toggle(uint8_t ep, uint16_t mask)
{
    uint16_t old = EP(ep);
    EP(ep) = (old & EP_NORMAL) | CTR_RX | CTR_TX | (old & mask);
}
static void ep_send(uint8_t ep, uint16_t addr, const uint8_t *data, uint16_t len)
{
    pma_write(addr, data, len);
    pma_put(8u * ep + 2u, len);
    ep_status(ep, STAT_TX, TX_VALID);
}
static void ep_rx_ready(uint8_t ep)
{
    /* Take ONE snapshot: a packet can arrive between two register reads.
     * Never overwrite COUNT_RX or rearm a buffer containing an unread packet.
     * Likewise, leave an already VALID receiver alone.
     */
    uint16_t state = EP(ep);
    if ((state & CTR_RX) || (state & STAT_RX) == RX_VALID) return;
    /* BL_SIZE=32, NUM_BLOCK=1 => 64 bytes. Count overwritten after RX. */
    pma_put(8u * ep + 6u, 0x8400u);
    ep_status(ep, STAT_RX, RX_VALID);
}

static uint16_t rx_free(void) { return (rx_tail - rx_head - 1u) & RX_QMASK; }
uint16_t usb_cdc_tx_free(void) { return (tx_tail - tx_head - 1u) & QMASK; }

static void configure(uint8_t value)
{
    usb_stats.configured = value;
    usb_stats.control_lines = 0;
    ++usb_stats.session;
    rx_head = rx_tail = tx_head = tx_tail = 0;
    tx_busy = tx_need_zlp = notify_pending = 0;
    ep_reset(1, 0); /* BULK */
    ep_reset(2, 0x0600u); /* INTERRUPT */
    if (value) {
        pma_put(8, EP1_TX);
        pma_put(12, EP1_RX);
        pma_put(16, EP2_TX);
        ep_status(1, STAT_TX, TX_NAK);
        ep_status(2, STAT_TX, TX_NAK);
        ep_rx_ready(1);
    }
}

static void bus_reset(void)
{
    ++usb_stats.resets;
    USB_BTABLE = 0;
    USB_DADDR = 0x80;
    usb_stats.address = 0;
    configure(0);
    ep_reset(0, 0x0200u); /* CONTROL */
    pma_put(0, EP0_TX);
    pma_put(4, EP0_RX);
    ep_status(0, STAT_TX, TX_NAK);
    ep_rx_ready(0);
    ctrl_state = CTRL_IDLE;
    pending_address = pending_config = -1;
}

static void control_stall(void)
{
    ctrl_state = CTRL_IDLE;
    ep_status(0, STAT_TX, TX_STALL);
    ep_status(0, STAT_RX, RX_STALL);
}
static void control_next(void)
{
    uint16_t len = ctrl_remaining > 64u ? 64u : ctrl_remaining;
    if (len || ctrl_zlp) {
        if (!len) ctrl_zlp = 0;
        ep_send(0, EP0_TX, ctrl_ptr, len);
        ctrl_ptr += len;
        ctrl_remaining -= len;
    } else {
        ctrl_state = CTRL_STATUS_OUT;
    }
    ep_rx_ready(0);
}
static void control_data(const uint8_t *data, uint16_t len, uint16_t requested)
{
    ctrl_zlp = len < requested && (len % 64u) == 0;
    ctrl_remaining = len < requested ? len : requested;
    ctrl_ptr = data;
    ctrl_state = CTRL_DATA_IN;
    control_next();
}
static void control_ack(void)
{
    ctrl_state = CTRL_STATUS_IN;
    ep_send(0, EP0_TX, ctrl_buffer, 0);
    ep_rx_ready(0);
}

static uint16_t string_descriptor(uint8_t index)
{
    if (!index) {
        ctrl_buffer[0] = 4; ctrl_buffer[1] = 3;
        ctrl_buffer[2] = 0x09; ctrl_buffer[3] = 0x04;
        return 4;
    }
    const char *s = index == 1 ? "Blue Pill Lab" : "BluePill USB CDC";
    uint16_t len = 2;
    if (index == 3) {
        const char hex[] = "0123456789ABCDEF";
        for (uint8_t i = 0; i < 12; ++i) {
            uint8_t uid = *(volatile uint8_t *)(0x1ffff7e8u + i);
            ctrl_buffer[len++] = (uint8_t)hex[uid >> 4];
            ctrl_buffer[len++] = 0;
            ctrl_buffer[len++] = (uint8_t)hex[uid & 15u];
            ctrl_buffer[len++] = 0;
        }
    } else {
        while (*s) { ctrl_buffer[len++] = (uint8_t)*s++; ctrl_buffer[len++] = 0; }
    }
    ctrl_buffer[0] = (uint8_t)len; ctrl_buffer[1] = 3;
    return len;
}
static int valid_endpoint(uint16_t index)
{
    return index == 0 || index == 0x80 ||
           (usb_stats.configured && (index == 1 || index == 0x81 || index == 0x82));
}

static void control_setup(void)
{
    uint8_t req[8];
    uint16_t count = pma_get(6) & 0x3ffu;
    pma_read(req, EP0_RX, 8);
    ep_clear_ctr(0, CTR_RX | CTR_TX); /* Abort any preceding control transfer. */
    ep_status(0, STAT_TX, TX_NAK);
    ep_status(0, STAT_RX, RX_NAK);
    pending_address = pending_config = -1;
    ctrl_state = CTRL_IDLE;
    ++usb_stats.setups;
    if (count != 8) { control_stall(); return; }
    uint16_t value = req[2] | ((uint16_t)req[3] << 8);
    uint16_t index = req[4] | ((uint16_t)req[5] << 8);
    uint16_t length = req[6] | ((uint16_t)req[7] << 8);

    if (req[0] == 0x80 && req[1] == 6) { /* GET_DESCRIPTOR */
        uint8_t type = value >> 8, number = value & 0xffu;
        if (type == 1 && !number && !index)
            control_data(device_descriptor, sizeof(device_descriptor), length);
        else if (type == 2 && !number && !index)
            control_data(config_descriptor, sizeof(config_descriptor), length);
        else if (type == 3 && number <= 3 && (!index || index == 0x0409)) {
            uint16_t n = string_descriptor(number);
            control_data(ctrl_buffer, n, length);
        } else control_stall();
        return;
    }
    if (req[0] == 0 && req[1] == 5 && !index && !length && value <= 127 &&
        !usb_stats.configured) { /* SET_ADDRESS after status ACK */
        pending_address = (int16_t)value; control_ack(); return;
    }
    if (req[0] == 0 && req[1] == 9 && !index && !length && value <= 1) {
        pending_config = (int16_t)value; control_ack(); return;
    }
    if (req[0] == 0x80 && req[1] == 8 && !value && !index && length == 1) {
        ctrl_buffer[0] = (uint8_t)usb_stats.configured;
        control_data(ctrl_buffer, 1, length); return;
    }
    if ((req[0] == 0x80 || req[0] == 0x81 || req[0] == 0x82) &&
        req[1] == 0 && !value && length == 2 &&
        ((req[0] == 0x80 && !index) ||
         (req[0] == 0x81 && usb_stats.configured && index <= 1) ||
         (req[0] == 0x82 && valid_endpoint(index)))) { /* GET_STATUS */
        ctrl_buffer[0] = ctrl_buffer[1] = 0;
        if (req[0] == 0x82) {
            uint16_t e = EP(index & 0x0fu);
            ctrl_buffer[0] = (index & 0x80) ? ((e & STAT_TX) == TX_STALL) :
                                                        ((e & STAT_RX) == RX_STALL);
        }
        control_data(ctrl_buffer, 2, length); return;
    }
    if (req[0] == 2 && (req[1] == 1 || req[1] == 3) && !value && !length &&
        (index & 0x0fu) && valid_endpoint(index)) { /* endpoint HALT */
        uint8_t ep = index & 15u, in = index & 0x80u;
        if (req[1] == 1) {
            ep_clear_toggle(ep, in ? DTOG_TX : DTOG_RX);
            if (in) ep_status(ep, STAT_TX, tx_busy && ep == 1 ? TX_VALID : TX_NAK);
            else if (rx_free() >= 64) ep_rx_ready(ep);
            else ep_status(ep, STAT_RX, RX_NAK);
        } else ep_status(ep, in ? STAT_TX : STAT_RX, in ? TX_STALL : RX_STALL);
        control_ack(); return;
    }
    if (req[0] == 0x81 && req[1] == 10 && !value && index <= 1 &&
        length == 1 && usb_stats.configured) { /* GET_INTERFACE */
        ctrl_buffer[0] = 0; control_data(ctrl_buffer, 1, length); return;
    }
    if (req[0] == 1 && req[1] == 11 && !value && index <= 1 &&
        !length && usb_stats.configured) { control_ack(); return; }

    if (!index && usb_stats.configured) { /* CDC requests on control IF0 */
        if (req[0] == 0xa1 && req[1] == 0x21 && !value && length == 7) {
            control_data(line_coding, 7, length); return;
        }
        if (req[0] == 0x21 && req[1] == 0x20 && !value && length == 7) {
            ctrl_state = CTRL_LINE_OUT; ep_rx_ready(0); return;
        }
        if (req[0] == 0x21 && req[1] == 0x22 && !length) {
            usb_stats.control_lines = value & 3u;
            notify_pending = 1; control_ack(); return;
        }
        if (req[0] == 0x21 && req[1] == 0x23 && !length) {
            control_ack(); return; /* No physical UART BREAK output. */
        }
    }
    control_stall();
}

static void control_out(void)
{
    uint16_t count = pma_get(6) & 0x3ffu;
    ep_clear_ctr(0, CTR_RX);
    if (ctrl_state == CTRL_LINE_OUT && count == 7) {
        pma_read(line_coding, EP0_RX, 7);
        control_ack();
    } else if ((ctrl_state == CTRL_STATUS_OUT || ctrl_state == CTRL_DATA_IN) &&
               count == 0) {
        ctrl_state = CTRL_IDLE;
        ep_status(0, STAT_TX, TX_NAK);
        ep_rx_ready(0);
    } else control_stall();
}
static void control_in(void)
{
    ep_clear_ctr(0, CTR_TX);
    if (ctrl_state == CTRL_DATA_IN) control_next();
    else if (ctrl_state == CTRL_STATUS_IN) {
        if (pending_address >= 0) {
            USB_DADDR = 0x80u | (uint16_t)pending_address;
            usb_stats.address = (uint32_t)pending_address;
            pending_address = -1;
        }
        if (pending_config >= 0) {
            configure((uint8_t)pending_config); pending_config = -1;
        }
        ctrl_state = CTRL_IDLE;
        ep_rx_ready(0);
    }
}

void usb_cdc_init(void)
{
    /* Force D+ low for 25 ms to detach even with Blue Pill's fixed pull-up. */
    uint32_t crh = REG32(0x40010804u);
    REG32(0x40010810u) = 1u << 28;
    REG32(0x40010804u) = (crh & ~((0xfu << 12) | (0xfu << 16))) |
                         (4u << 12) | (2u << 16);
    board_delay(25);
    REG32(0x4002101cu) |= 1u << 23; /* APB1 USB clock */
    REG32(0x40021010u) |= 1u << 23;
    REG32(0x40021010u) &= ~(1u << 23);
    USB_CNTR = 1; /* FRES, transceiver powered. */
    board_delay(1);
    USB_CNTR = 0;
    USB_ISTR = 0;
    bus_reset();
    REG32(0x40010804u) = (REG32(0x40010804u) & ~(0xfu << 16)) | (4u << 16);
}

void usb_cdc_poll(void)
{
    uint16_t istr = USB_ISTR;
    if (istr & 0x0400u) {
        USB_ISTR = (uint16_t)~0x0400u;
        bus_reset();
        return;
    }
    if (istr & 0x2000u) { USB_ISTR = (uint16_t)~0x2000u; ++usb_stats.errors; }
    if (istr & 0x4000u) { USB_ISTR = (uint16_t)~0x4000u; ++usb_stats.errors; }
    if (istr & 0x0800u) { USB_ISTR = (uint16_t)~0x0800u; ++usb_stats.suspends; }
    if (istr & 0x1000u) USB_ISTR = (uint16_t)~0x1000u;
    /* Process one endpoint per poll to keep application/SysTick responsive. */
    if (istr & 0x8000u) {
        uint8_t ep = istr & 15u;
        uint16_t epr = EP(ep);
        if (ep == 0) {
            if (epr & CTR_RX) {
                if (epr & SETUP) control_setup(); else control_out();
            } else if (epr & CTR_TX) control_in();
        } else if (ep == 1) {
            if (epr & CTR_RX) {
                uint8_t data[64];
                uint16_t n = pma_get(14) & 0x3ffu;
                if (n <= 64 && rx_free() >= n) {
                    pma_read(data, EP1_RX, n);
                    for (uint16_t i = 0; i < n; ++i) {
                        rx_queue[rx_head] = data[i]; rx_head = (rx_head + 1u) & RX_QMASK;
                    }
                    usb_stats.rx_bytes += n; ++usb_stats.rx_packets;
                    ep_clear_ctr(1, CTR_RX);
                }
            }
            if (epr & CTR_TX) {
                ep_clear_ctr(1, CTR_TX);
                tx_busy = 0;
                usb_stats.tx_bytes += tx_inflight; ++usb_stats.tx_packets;
            }
        } else ep_clear_ctr(ep, CTR_RX | CTR_TX);
    }
    if (!usb_stats.configured) return;
    uint16_t bulk_state = EP(1);
    if (!(bulk_state & CTR_RX) && rx_free() >= 64 &&
        (bulk_state & STAT_RX) == RX_NAK)
        ep_rx_ready(1);
    if (!tx_busy && (EP(1) & STAT_TX) == TX_NAK) {
        uint8_t data[64];
        uint16_t n = 0;
        while (n < 64 && tx_tail != tx_head) {
            data[n++] = tx_queue[tx_tail]; tx_tail = (tx_tail + 1u) & QMASK;
        }
        if (n || tx_need_zlp) {
            tx_need_zlp = n == 64;
            tx_busy = 1; tx_inflight = (uint8_t)n;
            ep_send(1, EP1_TX, data, n);
        }
    }
    if (notify_pending && (EP(2) & STAT_TX) == TX_NAK) {
        const uint8_t state[] = {0xa1, 0x20, 0, 0, 0, 0, 2, 0, 3, 0};
        ep_send(2, EP2_TX, state, sizeof(state));
        notify_pending = 0;
    }
}

uint16_t usb_cdc_read(uint8_t *data, uint16_t max_len)
{
    uint16_t n = 0;
    while (n < max_len && rx_tail != rx_head) {
        data[n++] = rx_queue[rx_tail]; rx_tail = (rx_tail + 1u) & RX_QMASK;
    }
    return n;
}
int usb_cdc_write(const uint8_t *data, uint16_t len)
{
    if (!usb_stats.configured || len > usb_cdc_tx_free()) return 0;
    for (uint16_t i = 0; i < len; ++i) {
        tx_queue[tx_head] = data[i]; tx_head = (tx_head + 1u) & QMASK;
    }
    return 1;
}

/* Resident monitor: only USB IRQ context may touch driver queues/state after
 * enabling this. SysTick can pend USB IRQ, but must not call the driver itself.
 */
void usb_cdc_irq_enable(void)
{
    USB_CNTR = 0xfc00u; /* CTR, PMAOVR, ERR, WKUP, SUSP, RESET */
    REG32(0xe000e100u) = 1u << 20; /* USB_LP_CAN1_RX0 */
}
int usb_cdc_tx_idle(void)
{
    return tx_head == tx_tail && !tx_busy && !tx_need_zlp;
}
