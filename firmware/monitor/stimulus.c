#include "board.h"
#include "stimulus.h"

#define T1(offset) REG32(0x40012c00u + (offset))
#define D5(offset) REG32(0x40020058u + (offset))
#define BSRR REG32(0x40010c10u)
static uint32_t words[128];
static uint8_t packed[STIMULUS_CAPACITY / 4u]; /* two allowed GPIO bits/symbol */
static uint32_t generated;
static uint32_t generated_symbol, generated_left, generated_word;
static uint32_t trigger_mask, trigger_previous;
static uint32_t trigger_high, trigger_threshold;
volatile stimulus_status_t stimulus_status;

static uint32_t output_word(uint32_t level)
{
    return (level & stimulus_status.mask) |
           ((stimulus_status.mask & ~level) << 16);
}

void stimulus_stop(uint32_t state)
{
    /* Publish stop state BEFORE touching hardware. CH5 (0x10) may preempt
     * USB (0x20), but then sees a non-running job and cannot refill it.
     * USB cannot preempt CH5, and config/upload reject running jobs.
     */
    if (!stimulus_status.state) return;
    uint32_t keep_bridge = state == 3 && stimulus_status.bridge_mask;
    stimulus_status.state = state;
    trigger_mask = 0;
    T1(0x0c) = keep_bridge ? 2u : 0;
    T1(0x00) = keep_bridge ? 1u : 0;
    D5(0x00) = 0;
    BSRR = output_word(stimulus_status.idle);
    if (!keep_bridge && stimulus_status.bridge_mask) {
        stimulus_status.bridge_mask = 0;
        BSRR = 1u << 8;
    }
    stimulus_status.completed_ms = milliseconds;
    stimulus_status.state = state;
}

int stimulus_config(uint32_t hz, uint32_t mask, uint32_t idle, uint32_t mode, uint32_t repeat)
{
    if (!hz || hz > 100000u || !mask || (mask & ~STIMULUS_MASK) ||
        (idle & ~mask) || mode > 1 || !repeat || repeat > 64 ||
        stimulus_status.state == 2 || stimulus_status.state == 7) return 0;
    REG32(0x40021014u) |= 1u; /* DMA1 */
    REG32(0x40021018u) |= (1u << 11) | (1u << 3); /* TIM1 + GPIOB */
    stimulus_stop(4);
    stimulus_status.mask = mask;
    stimulus_status.idle = idle;
    stimulus_status.mode = mode; /* 0 push-pull; 1 open-drain (external pull-up). */
    stimulus_status.repeat = repeat;
    BSRR = output_word(idle); /* Set latch BEFORE enabling output. */
    uint32_t crh = REG32(0x40010c04u);
    for (uint32_t pin = 8; pin <= 10; ++pin) {
        if (mask & (1u << pin)) {
            uint32_t shift = (pin - 8u) * 4u;
            crh = (crh & ~(15u << shift)) | ((mode ? 6u : 2u) << shift);
        }
    }
    REG32(0x40010c04u) = crh;
    uint32_t divisor = (72000000u + hz / 2u) / hz;
    uint32_t prescale = (divisor + 65535u) / 65536u;
    uint32_t period = (divisor + prescale / 2u) / prescale;
    if (!period) period = 1;
    T1(0x00) = T1(0x0c) = 0;
    D5(0x00) = 0;
    T1(0x28) = prescale - 1u;
    T1(0x2c) = period - 1u;
    T1(0x34) = period / 2u; /* CCR1: resolve AFTER update DMA has driven peer. */
    T1(0x30) = 0; /* RCR: one update per period. */
    T1(0x14) = 1;
    T1(0x10) = T1(0x24) = 0;
    stimulus_status.ticks = prescale * period;
    stimulus_status.loaded = stimulus_status.count = 0;
    stimulus_status.dma_flags = 0;
    stimulus_status.emitted = stimulus_status.underruns = generated = 0;
    stimulus_status.completed_ms = 0;
    ++stimulus_status.id;
    stimulus_status.state = 1; /* configured/uploading */
    return 1;
}

static int nibble(char c)
{
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

int stimulus_append(uint32_t offset, const char *hex)
{
    if (stimulus_status.state != 1 || offset != stimulus_status.loaded) return 0;
    uint32_t len = 0;
    while (hex[len]) ++len;
    if (!len || (len & 3u) || len > 64 ||
        len / 4u > STIMULUS_CAPACITY - offset) return 0;
    /* Validate the complete chunk first: rejected data must not partially
     * change a previously accepted job. Four hex digits encode a pin level.
     */
    for (uint32_t i = 0; i < len; i += 4) {
        uint32_t level = 0;
        for (uint32_t j = 0; j < 4; ++j) {
            int n = nibble(hex[i + j]);
            if (n < 0) return 0;
            level = (level << 4) | (uint32_t)n;
        }
        if (level & ~stimulus_status.mask) return 0;
    }
    for (uint32_t i = 0; i < len; i += 4) {
        uint32_t level = 0;
        for (uint32_t j = 0; j < 4; ++j)
            level = (level << 4) | (uint32_t)nibble(hex[i + j]);
        uint32_t shift = (offset & 3u) * 2u;
        uint32_t symbol = ((level >> 8) & 1u) | (((level >> 10) & 1u) << 1);
        packed[offset / 4u] = (uint8_t)((packed[offset / 4u] & ~(3u << shift)) |
                                     (symbol << shift));
        ++offset;
    }
    stimulus_status.loaded = offset;
    return 1;
}

static uint32_t pattern_level(uint32_t index)
{
    uint32_t symbol = (packed[index / 4u] >> ((index & 3u) * 2u)) & 3u;
    return ((symbol & 1u) << 8) | ((symbol & 2u) << 9);
}

static void fill_half(uint32_t half)
{
    uint32_t total = stimulus_status.count * stimulus_status.repeat;
    uint32_t idle_word = output_word(stimulus_status.idle);
    for (uint32_t i = half * 64u; i < half * 64u + 64u; ++i) {
        if (generated < total) {
            if (!generated_left) {
                generated_word = output_word(pattern_level(generated_symbol++));
                generated_left = stimulus_status.repeat;
            }
            words[i] = generated_word;
            --generated_left;
        } else words[i] = idle_word;
        ++generated;
    }
}

static int start_internal(uint32_t arm_source)
{
    if (stimulus_status.state != 1 || !stimulus_status.loaded ||
        pattern_level(stimulus_status.loaded - 1u) != stimulus_status.idle) return 0;
    /* Final entry MUST be idle: DMA completion IRQ latency may not shorten
     * the last active symbol. The final idle entry remains held afterwards.
     */
    REG32(0x40020004u) = 0xfu << 16; /* DMA1 CH5 flags */
    REG32(0xe000e280u) = 1u << 15;
    REG32(0xe000e100u) = 1u << 15;
    D5(0x08) = 0x40010c10u; /* CPAR GPIOB_BSRR */
    D5(0x0c) = (uint32_t)words;
    D5(0x04) = 128;
    stimulus_status.count = stimulus_status.loaded;
    generated = stimulus_status.emitted = 0;
    generated_symbol = generated_left = 0;
    fill_half(0); fill_half(1);
    stimulus_status.state = arm_source ? 7u : 2u;
    /* Circular word/word double half buffer. Refill touches only free half. */
    D5(0x00) = (2u << 12) | (2u << 10) | (2u << 8) | (1u << 7) |
               (1u << 5) | (1u << 4) | (1u << 3) | (1u << 2) | (1u << 1) |
               (arm_source ? 0u : 1u);
    __asm volatile ("dmb" ::: "memory");
    trigger_mask = arm_source;
    trigger_high = 0;
    trigger_previous = REG32(0x40010c08u) & arm_source;
    stimulus_status.t0_cycles = REG32(0xe0001004u);
    stimulus_status.t0_ms = milliseconds;
    T1(0x0c) = (arm_source ? 0u : 1u << 8) |
               ((stimulus_status.bridge_mask || arm_source) ? 2u : 0u);
    T1(0x00) = 1;
    return 1;
}

int stimulus_start(void) { return start_internal(0); }
int stimulus_arm(uint32_t source, uint32_t idle_ticks)
{
    if (source != 1u || !idle_ticks || idle_ticks > 1000000u) return 0;
    trigger_threshold = idle_ticks;
    REG32(0xe000e280u) = 1u << 27;
    REG32(0xe000e100u) = 1u << 27;
    return start_internal(source);
}

void DMA1_Channel5_IRQHandler(void)
{
    uint32_t flags = REG32(0x40020000u) & (0xfu << 16);
    REG32(0x40020004u) = 0xfu << 16;
    stimulus_status.dma_flags = flags;
    if (stimulus_status.state != 2) return;
    if (flags & (1u << 19)) { stimulus_stop(5); return; }
    uint32_t events = flags & (3u << 17);
    if (!events) return;
    uint32_t remaining = D5(0x04);
    if (events == (3u << 17) ||
        ((events & (1u << 18)) ? remaining > 64u || remaining < 8u :
                                           remaining < 72u)) {
        ++stimulus_status.underruns; stimulus_stop(6); return;
    }
    stimulus_status.emitted += 64;
    if (stimulus_status.emitted >= stimulus_status.count * stimulus_status.repeat) {
        stimulus_stop(3); return;
    }
    fill_half(events & (1u << 18) ? 0u : 1u);
}

void stimulus_disconnect(void)
{
    if (stimulus_status.state == 2 || stimulus_status.state == 7 || stimulus_status.bridge_mask) stimulus_stop(4);
}

int stimulus_bridge(uint32_t sources)
{
    if (sources & ~0x0401u) return 0; /* only PB0/B_TX and PB10/peer */
    if (sources && (stimulus_status.state != 1 || stimulus_status.mask != 0x400u)) return 0;
    stimulus_status.bridge_mask = sources;
    stimulus_status.bridge_ticks = stimulus_status.bridge_max_lateness = 0;
    if (!sources) {
        T1(0x0c) &= ~2u;
        if (stimulus_status.state != 2) T1(0x00) = 0;
        BSRR = 1u << 8;
        return 1;
    }
    BSRR = 1u << 8;
    REG32(0x40010c04u) = (REG32(0x40010c04u) & ~15u) | 2u;
    T1(0x18) = 0; /* CC1 output compare, frozen; no pad AF output. */
    T1(0x20) = 0;
    REG32(0xe000e280u) = 1u << 27;
    REG32(0xe000e100u) = 1u << 27;
    return 1;
}

void TIM1_CC_IRQHandler(void)
{
    T1(0x10) = ~2u;
    uint32_t sources = stimulus_status.bridge_mask;
    if (!sources && !trigger_mask) return;
    uint32_t now = T1(0x24), match = T1(0x34), period = T1(0x2c) + 1u;
    uint32_t late = now >= match ? now - match : now + period - match;
    if (late > stimulus_status.bridge_max_lateness)
        stimulus_status.bridge_max_lateness = late;
    /* This is a generic pad resolver, not the capture engine. Capture still
     * reads GPIO IDR with DMA; no protocol parser runs in this handler.
     */
    uint32_t level = REG32(0x40010c08u);
    if (trigger_mask) {
        uint32_t current = level & trigger_mask;
        if (trigger_previous && !current && trigger_high >= trigger_threshold) {
            trigger_mask = 0;
            stimulus_status.state = 2;
            stimulus_status.t0_cycles = REG32(0xe0001004u);
            stimulus_status.t0_ms = milliseconds;
            REG32(0x40020004u) = 0xfu << 16;
            D5(0x00) |= 1u;
            T1(0x0c) |= 1u << 8;
        }
        trigger_high = current ? trigger_high + (trigger_high < trigger_threshold) : 0u;
        trigger_previous = current;
    }
    if (sources) BSRR = (level & sources) == sources ? 1u << 8 : 1u << 24;
    ++stimulus_status.bridge_ticks;
}
