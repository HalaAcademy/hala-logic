#ifndef CAPTURE_H
#define CAPTURE_H
#include <stdint.h>
#define CAPACITY 2048u
typedef struct {
    uint32_t id, state, count, ticks, requested_hz, port, mask, t0_cycles, t0_ms;
    uint32_t dma_flags;
    uint32_t stream, produced, target, ready[2], lost;
} capture_status_t;
extern volatile capture_status_t capture_status;
extern uint16_t capture_samples[CAPACITY];
int capture_start(uint32_t port, uint32_t hz, uint32_t n, uint32_t mask);
void capture_stop(void);
int capture_stream_start(uint32_t port, uint32_t hz, uint32_t n, uint32_t mask);
int capture_block(uint32_t seq, uint32_t offset, uint32_t count, const uint16_t **data);
int capture_ack(uint32_t seq);
void DMA1_Channel2_IRQHandler(void);
#endif
