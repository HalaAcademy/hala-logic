#include "board.h"
#include "usb_cdc.h"
#include "layout.h"
#include "capture.h"
#include "stimulus.h"

extern volatile uint32_t student_running, boot_reason, image_error, monitor_ticks;
extern volatile boot_mailbox_t boot_mailbox;
extern uint32_t _stack_limit, _ebss;
void reboot_to_mode(uint32_t safe) __attribute__((noreturn));
static char line[128];
static uint16_t line_len;
static uint32_t session, previous_lines, reboot_mode, reboot_at;
static uint8_t overflow, skip_lf;

static char *text(char *p, const char *s) { while (*s) *p++ = *s++; return p; }
static char *number(char *p, uint32_t n)
{
    char digits[10]; uint8_t len = 0;
    do { digits[len++] = '0' + n % 10u; n /= 10u; } while (n);
    while (len) *p++ = digits[--len];
    return p;
}
static char *field(char *p, const char *name, uint32_t n)
{
    p = text(p, ",\""); p = text(p, name); p = text(p, "\":");
    return number(p, n);
}
static void send(const char *s)
{
    uint16_t n = 0; while (s[n]) ++n;
    (void)usb_cdc_write((const uint8_t *)s, n);
}
static int equal(const char *a, const char *b)
{
    while (*a && *a == *b) { ++a; ++b; }
    return *a == *b;
}
static int parse(const char *s, uint32_t *out)
{
    if (!*s) return 0;
    uint32_t value = 0, base = 10;
    if (s[0] == '0' && s[1] == 'x') { s += 2; base = 16; if (!*s) return 0; }
    while (*s) {
        uint32_t d = *s >= '0' && *s <= '9' ? (uint32_t)(*s - '0') :
                     *s >= 'a' && *s <= 'f' ? (uint32_t)(*s - 'a' + 10) :
                     *s >= 'A' && *s <= 'F' ? (uint32_t)(*s - 'A' + 10) : 99u;
        if (d >= base || value > (0xffffffffu - d) / base) return 0;
        value = value * base + d; ++s;
    }
    *out = value; return 1;
}
static int readable(uint32_t addr)
{
    if (addr & 3u) return 0;
    if (addr >= B_RAM_BASE && addr <= B_RAM_END - 4u) return 1;
    if (addr >= 0x40021000u && addr <= 0x40021024u) return 1; /* RCC */
    if (addr >= 0x40020000u && addr <= 0x40020090u) return 1; /* DMA1 */
    if (addr == 0xe000ed08u || addr == 0xe000ed28u || addr == 0xe000ed2cu) return 1;
    for (uint32_t port = 0; port < 3; ++port) {
        uint32_t base = 0x40010800u + port * 0x400u;
        if (addr >= base && addr <= base + 12u) return 1; /* GPIO config/IDR/ODR */
    }
    for (uint32_t timer = 0; timer < 3; ++timer) {
        uint32_t base = 0x40000000u + timer * 0x400u;
        if (addr >= base && addr <= base + 0x40u && addr != base + 0x14u) return 1;
    }
    const uint32_t uart[3] = {0x40013800u, 0x40004400u, 0x40004800u};
    for (uint32_t i = 0; i < 3; ++i)
        if (addr >= uart[i] + 8u && addr <= uart[i] + 0x14u) return 1;
    return 0; /* In particular, never read UART DR or arbitrary MMIO. */
}
static char *capture_json(char *p)
{
    p = text(p, "{\"id\":"); p = number(p, capture_status.id);
    p = field(p, "state", capture_status.state);
    p = field(p, "count", capture_status.count);
    p = field(p, "remaining", capture_status.state ? REG32(0x40020020u) : 0);
    p = field(p, "ticks", capture_status.ticks);
    p = field(p, "requested_hz", capture_status.requested_hz);
    p = field(p, "port", capture_status.port);
    p = field(p, "mask", capture_status.mask);
    p = field(p, "t0_cycles", capture_status.t0_cycles);
    p = field(p, "t0_ms", capture_status.t0_ms);
    p = field(p, "dma_flags", capture_status.dma_flags);
    p = field(p, "stream", capture_status.stream);
    p = field(p, "produced", capture_status.produced);
    p = field(p, "target", capture_status.target);
    p = field(p, "ready0", capture_status.ready[0]);
    p = field(p, "ready1", capture_status.ready[1]);
    p = field(p, "lost", capture_status.lost);
    return text(p, "}\r\n");
}
static char *stimulus_json(char *p)
{
    p = text(p, "{\"id\":"); p = number(p, stimulus_status.id);
    p = field(p, "state", stimulus_status.state);
    p = field(p, "loaded", stimulus_status.loaded);
    p = field(p, "count", stimulus_status.count);
    p = field(p, "mask", stimulus_status.mask);
    p = field(p, "idle", stimulus_status.idle);
    p = field(p, "ticks", stimulus_status.ticks);
    p = field(p, "t0_cycles", stimulus_status.t0_cycles);
    p = field(p, "t0_ms", stimulus_status.t0_ms);
    p = field(p, "dma_flags", stimulus_status.dma_flags);
    p = field(p, "completed_ms", stimulus_status.completed_ms);
    p = field(p, "repeat", stimulus_status.repeat);
    p = field(p, "emitted", stimulus_status.emitted);
    p = field(p, "underruns", stimulus_status.underruns);
    p = field(p, "bridge_mask", stimulus_status.bridge_mask);
    p = field(p, "bridge_ticks", stimulus_status.bridge_ticks);
    p = field(p, "bridge_max_lateness", stimulus_status.bridge_max_lateness);
    return text(p, "}\r\n");
}
static void command(void)
{
    char *arg[6], *s = line;
    uint8_t argc = 0;
    while (*s && argc < 6) {
        while (*s == ' ') ++s;
        if (!*s) break;
        arg[argc++] = s;
        while (*s && *s != ' ') ++s;
        if (*s) *s++ = 0;
    }
    if (!argc) return;
    while (*s == ' ') ++s;
    if (*s) { send("ERR arguments\r\n"); return; }
    char reply[512], *p = reply;
    uint32_t a, b, c, d, e;
    if (equal(arg[0], "PING") && argc == 1) { send("PONG\r\n"); return; }
    if (equal(arg[0], "HELP") && argc == 1) {
        send("PING INFO CAPS CAPTURE CAPSTATUS READ STOP REG MODE TXCONFIG TXDATA TXSTART TXSTATUS TXSTOP\r\n");
        return;
    }
    if (equal(arg[0], "INFO") && argc == 1) {
        p = text(p, "{\"version\":\"BP-AB-MASTER-20261023-R002-dev9\"");
        p = field(p, "running", student_running);
        p = field(p, "boot_reason", boot_reason);
        p = field(p, "image_error", image_error);
        p = field(p, "b_flash", B_FLASH_BASE);
        p = field(p, "b_ram", B_RAM_BASE);
        p = field(p, "vtor", REG32(0xe000ed08u));
        p = field(p, "clock_error", clock_error);
        p = field(p, "ticks", monitor_ticks);
        p = field(p, "usb_errors", usb_stats.errors);
        p = field(p, "fault_pc", boot_mailbox.fault_pc);
        p = field(p, "fault_cfsr", boot_mailbox.cfsr);
        p = field(p, "capture_max", CAPACITY);
        p = text(p, "}\r\n");
    } else if (equal(arg[0], "CAPS") && argc == 1) {
        send("{\"transport\":1,\"capture_max\":2048,\"capture_hz_max\":1000000,"
             "\"tx_steps_max\":4096,\"tx_hz_max\":100000,\"tx_gpio\":\"B\","
             "\"tx_mask\":1280,\"tx_modes\":[\"push_pull\",\"open_drain\"],"
             "\"reactive\":false,\"streaming\":true,\"stream_hz_max\":50000,"
             "\"stream_block\":1024,\"no_wire_same_pad\":true}\r\n");
        return;
    } else if (equal(arg[0], "STACK") && argc == 1) {
        uint32_t *q = &_stack_limit;
        while ((uint32_t)q < A_RAM_BASE + A_RAM_SIZE && *q == 0xa55a55a5u) ++q;
        p = text(p, "{\"a_msp_unwritten_bytes\":"); p = number(p, (uint32_t)q - (uint32_t)&_stack_limit);
        q = (uint32_t *)0x20004c00u;
        while ((uint32_t)q < B_RAM_END && *q == 0xb55b55b5u) ++q;
        p = field(p, "b_psp_unwritten_bytes", (uint32_t)q - 0x20004c00u);
        p = field(p, "a_static_free_bytes", (uint32_t)&_stack_limit - (uint32_t)&_ebss);
        p = text(p, "}\r\n");
    } else if (equal(arg[0], "TXCONFIG") && (argc == 5 || argc == 6) && parse(arg[1], &a) &&
               parse(arg[2], &b) && parse(arg[3], &c) && parse(arg[4], &d) &&
               (argc == 5 || parse(arg[5], &e))) {
        if (!stimulus_config(a, b, c, d, argc == 5 ? 1u : e)) {
            send("ERR stimulus parameters or busy\r\n"); return;
        }
        p = stimulus_json(p);
    } else if (equal(arg[0], "TXDATA") && argc == 3 && parse(arg[1], &a)) {
        if (!stimulus_append(a, arg[2])) {
            send("ERR stimulus offset data or state\r\n"); return;
        }
        p = stimulus_json(p);
    } else if (equal(arg[0], "TXSTART") && argc == 2 && parse(arg[1], &a)) {
        if (a != stimulus_status.id ||
            ((stimulus_status.state != 2 && stimulus_status.state != 3) &&
             !stimulus_start())) {
            send("ERR stimulus id state or final idle\r\n"); return;
        }
        p = stimulus_json(p);
    } else if (equal(arg[0], "TXSTATUS") && argc == 1) {
        p = stimulus_json(p);
    } else if (equal(arg[0], "TXARM") && argc == 4 && parse(arg[1], &a) &&
               parse(arg[2], &b) && parse(arg[3], &c)) {
        if (a != stimulus_status.id ||
            (stimulus_status.state != 7 && !stimulus_arm(b, c))) {
            send("ERR stimulus arm id state or source\r\n"); return;
        }
        p = stimulus_json(p);
    } else if (equal(arg[0], "TXSTOP") && argc == 1) {
        stimulus_stop(4); p = stimulus_json(p);
    } else if (equal(arg[0], "BRIDGE") && argc == 2 && parse(arg[1], &a)) {
        if (!stimulus_bridge(a)) { send("ERR bridge source mask or state\r\n"); return; }
        p = stimulus_json(p);
    } else if ((equal(arg[0], "CAPTURE") || equal(arg[0], "CAPSTREAM")) &&
               argc == 5 && arg[1][1] == 0 &&
               arg[1][0] >= 'A' && arg[1][0] <= 'C' && parse(arg[2], &a) &&
               parse(arg[3], &b) && parse(arg[4], &c)) {
        int ok = equal(arg[0], "CAPSTREAM") ?
            capture_stream_start((uint32_t)(arg[1][0] - 'A'), a, b, c) :
            capture_start((uint32_t)(arg[1][0] - 'A'), a, b, c);
        if (!ok) {
            send("ERR capture parameters or busy\r\n"); return;
        }
        p = capture_json(p);
    } else if (equal(arg[0], "CAPSTATUS") && argc == 1) {
        p = capture_json(p);
    } else if (equal(arg[0], "BLOCK") && argc == 4 && parse(arg[1], &a) &&
               parse(arg[2], &b) && parse(arg[3], &c)) {
        const uint16_t *samples;
        if (!capture_block(a, b, c, &samples)) { send("ERR block not ready or lost\r\n"); return; }
        p = text(p, "BLOCK "); p = number(p, capture_status.id);
        p = text(p, " "); p = number(p, a);
        p = text(p, " "); p = number(p, b);
        p = text(p, " "); p = number(p, c);
        p = text(p, " "); p = number(p, crc32_bytes((const uint8_t *)samples, c * 2u));
        p = text(p, "\r\n");
        (void)usb_cdc_write((const uint8_t *)reply, (uint16_t)(p - reply));
        (void)usb_cdc_write((const uint8_t *)samples, (uint16_t)(c * 2u));
        return;
    } else if (equal(arg[0], "ACKBLOCK") && argc == 2 && parse(arg[1], &a)) {
        if (!capture_ack(a)) { send("ERR block ack\r\n"); return; }
        p = capture_json(p);
    } else if (equal(arg[0], "STOP") && argc == 1) {
        capture_stop(); p = capture_json(p);
    } else if (equal(arg[0], "READ") && argc == 3 &&
               parse(arg[1], &a) && parse(arg[2], &b)) {
        if (capture_status.stream || capture_status.state != 2 || !b || b > 512 || a > capture_status.count ||
            b > capture_status.count - a) { send("ERR capture not ready or range\r\n"); return; }
        const uint8_t *data = (const uint8_t *)(capture_samples + a);
        p = text(p, "DATA "); p = number(p, capture_status.id);
        p = text(p, " "); p = number(p, a);
        p = text(p, " "); p = number(p, b);
        p = text(p, " "); p = number(p, crc32_bytes(data, 2u * b));
        p = text(p, "\r\n");
        (void)usb_cdc_write((const uint8_t *)reply, (uint16_t)(p - reply));
        (void)usb_cdc_write(data, (uint16_t)(2u * b));
        return;
    } else if (equal(arg[0], "REG") && argc == 3 &&
               parse(arg[1], &a) && parse(arg[2], &b)) {
        if (!b || b > 8 || a > 0xffffffffu - b * 4u) { send("ERR register range\r\n"); return; }
        for (c = 0; c < b; ++c)
            if (!readable(a + 4u * c)) { send("ERR register not whitelisted\r\n"); return; }
        p = text(p, "[");
        for (c = 0; c < b; ++c) {
            if (c) p = text(p, ",");
            d = REG32(a + 4u * c); p = number(p, d);
        }
        p = text(p, "]\r\n");
    } else if (equal(arg[0], "MODE") && argc == 2 &&
               (equal(arg[1], "SAFE") || equal(arg[1], "RUN"))) {
        reboot_mode = equal(arg[1], "SAFE") ? 1u : 2u;
        reboot_at = milliseconds;
        send("OK reboot\r\n"); return;
    } else { send("ERR command\r\n"); return; }
    (void)usb_cdc_write((const uint8_t *)reply, (uint16_t)(p - reply));
}

void monitor_service(void)
{
    if (session != usb_stats.session ||
        ((previous_lines & 1u) && !(usb_stats.control_lines & 1u))) {
        stimulus_disconnect();
        session = usb_stats.session;
        line_len = overflow = skip_lf = 0;
    }
    previous_lines = usb_stats.control_lines;
    if (reboot_mode && usb_cdc_tx_idle() && (uint32_t)(milliseconds - reboot_at) >= 20u)
        reboot_to_mode(reboot_mode == 1 ? 1u : 0u);
    /* Parser and output have bounded work per interrupt, no blocking waits. */
    for (uint32_t n = 0; n < 64 && usb_cdc_tx_free() >= 1300; ++n) {
        uint8_t c;
        if (!usb_cdc_read(&c, 1)) break;
        if (skip_lf) { skip_lf = 0; if (c == '\n') continue; }
        if (c == '\r' || c == '\n') {
            skip_lf = c == '\r';
            line[line_len] = 0;
            if (overflow) send("ERR line too long\r\n");
            else if (line_len) command();
            line_len = overflow = 0;
        } else if (line_len < sizeof(line) - 1u && !overflow) line[line_len++] = (char)c;
        else overflow = 1;
    }
    board_led((milliseconds / (student_running ? 500u : 125u)) & 1u);
}
