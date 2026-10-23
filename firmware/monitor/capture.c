#include "board.h"
#include "capture.h"

#define TIM2_CR1 REG32(0x40000000u)
#define TIM2_DIER REG32(0x4000000cu)
#define TIM2_SR REG32(0x40000010u)
#define TIM2_EGR REG32(0x40000014u)
#define TIM2_CNT REG32(0x40000024u)
#define TIM2_PSC REG32(0x40000028u)
#define TIM2_ARR REG32(0x4000002cu)
#define DMA_ISR REG32(0x40020000u)
#define DMA_IFCR REG32(0x40020004u)
#define DMA_CCR2 REG32(0x4002001cu)
#define DMA_CNDTR2 REG32(0x40020020u)
#define DMA_CPAR2 REG32(0x40020024u)
#define DMA_CMAR2 REG32(0x40020028u)

uint16_t capture_samples[CAPACITY];
volatile capture_status_t capture_status;

void capture_stop(void)
{
    TIM2_DIER = 0;
    TIM2_CR1 = 0;
    DMA_CCR2 &= ~1u;
    if (capture_status.state == 1) {
        if (capture_status.stream) capture_status.count = capture_status.produced;
        else capture_status.count -= DMA_CNDTR2;
        capture_status.state = 2;
    }
}

int capture_start(uint32_t port, uint32_t hz, uint32_t n, uint32_t mask)
{
    if (port > 2 || !hz || hz > 1000000u || !n || n > CAPACITY ||
        !mask || mask > 0xffffu || capture_status.state == 1) return 0;
    REG32(0x40021014u) |= 1u; /* DMA1 AHB */
    REG32(0x40021018u) |= 1u << (port + 2u); /* GPIO input clock only */
    REG32(0x4002101cu) |= 1u; /* TIM2 APB1 */
    TIM2_CR1 = TIM2_DIER = 0;
    DMA_CCR2 = 0;
    DMA_IFCR = 0xf0u;
    uint32_t divisor = (72000000u + hz / 2u) / hz;
    uint32_t prescale = (divisor + 65535u) / 65536u;
    uint32_t period = (divisor + prescale / 2u) / prescale;
    if (!period) period = 1;
    if (period > 65536u) period = 65536u;
    TIM2_PSC = prescale - 1u;
    TIM2_ARR = period - 1u;
    TIM2_EGR = 1; /* Load PSC/ARR BEFORE DMA requests are enabled. */
    TIM2_SR = 0;
    TIM2_CNT = 0;
    DMA_CPAR2 = 0x40010808u + 0x400u * port; /* GPIOx_IDR, not TIM2 data */
    DMA_CMAR2 = (uint32_t)capture_samples;
    DMA_CNDTR2 = n;
    ++capture_status.id;
    capture_status.count = n;
    capture_status.ticks = prescale * period;
    capture_status.requested_hz = hz;
    capture_status.port = port;
    capture_status.mask = mask;
    capture_status.dma_flags = 0;
    capture_status.stream = capture_status.produced = capture_status.target = 0;
    capture_status.ready[0] = capture_status.ready[1] = capture_status.lost = 0;
    capture_status.state = 1;
    REG32(0xe000e280u) = 1u << 12; /* clear pending DMA1_CH2 */
    REG32(0xe000e100u) = 1u << 12;
    /* Very high DMA priority, halfword peripheral/memory, MINC, TC/TE IRQ.
     * DIR=0, PINC=0, CIRC=0, MEM2MEM=0: each TIM2 update reads GPIO IDR.
     */
    DMA_CCR2 = (3u << 12) | (1u << 10) | (1u << 8) | (1u << 7) |
               (1u << 3) | (1u << 1) | 1u;
    capture_status.t0_ms = milliseconds;
    capture_status.t0_cycles = REG32(0xe0001004u);
    TIM2_DIER = 1u << 8; /* UDE */
    TIM2_CR1 = 1;
    return 1;
}

int capture_stream_start(uint32_t port, uint32_t hz, uint32_t n, uint32_t mask)
{
    if (!n || n > 1048576u || (n & 1023u) || hz > 50000u) return 0;
    if (!capture_start(port, hz, CAPACITY, mask)) return 0;
    /* Configure while timer is stopped; no output trigger is generated. */
    TIM2_CR1 = TIM2_DIER = 0;
    DMA_CCR2 = 0;
    TIM2_CNT = 0;
    TIM2_EGR = 1; TIM2_SR = 0;
    DMA_IFCR = 0xf0u;
    DMA_CNDTR2 = CAPACITY;
    capture_status.stream = 1;
    capture_status.target = n;
    capture_status.count = n;
    DMA_CCR2 = (3u << 12) | (1u << 10) | (1u << 8) | (1u << 7) |
               (1u << 5) | (1u << 3) | (1u << 2) | (1u << 1) | 1u;
    capture_status.t0_ms = milliseconds;
    capture_status.t0_cycles = REG32(0xe0001004u);
    TIM2_DIER = 1u << 8;
    TIM2_CR1 = 1;
    return 1;
}

int capture_block(uint32_t seq, uint32_t offset, uint32_t count, const uint16_t **data)
{
    if (!capture_status.stream || !seq || !count || count > 512 || offset >= 1024 ||
        count > 1024u - offset || capture_status.lost || capture_status.state > 2) return 0;
    uint32_t half = (seq - 1u) & 1u;
    if (capture_status.ready[half] != seq) return 0;
    *data = capture_samples + half * 1024u + offset;
    return 1;
}

int capture_ack(uint32_t seq)
{
    if (!capture_status.stream || !seq || capture_status.lost) return 0;
    uint32_t half = (seq - 1u) & 1u;
    if (capture_status.ready[half] != seq) return 0;
    capture_status.ready[half] = 0;
    return 1;
}

void DMA1_Channel2_IRQHandler(void)
{
    uint32_t flags = DMA_ISR & 0xf0u;
    DMA_IFCR = 0xf0u;
    capture_status.dma_flags = flags;
    if (capture_status.stream && capture_status.state == 1) {
        if (flags & 0x80u) { capture_stop(); capture_status.state = 3; return; }
        uint32_t events = flags & 0x60u;
        if (!events) return;
        uint32_t half = events & 0x40u ? 0u : 1u;
        if (events == 0x60u || capture_status.ready[half ^ 1u] ||
            capture_status.ready[half]) {
            ++capture_status.lost; capture_stop(); capture_status.state = 4; return;
        }
        capture_status.produced += 1024u;
        capture_status.ready[half] = capture_status.produced / 1024u;
        if (capture_status.produced >= capture_status.target) capture_stop();
        return;
    }
    if (flags & 0xa0u) { /* transfer complete or transfer error */
        capture_stop();
        if (flags & 0x80u) capture_status.state = 3;
    }
}
