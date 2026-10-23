#ifndef STIMULUS_H
#define STIMULUS_H
#include <stdint.h>
#define STIMULUS_CAPACITY 4096u
#define STIMULUS_MASK 0x0500u /* PB8/PB10, not USB, SWD or Safe. */
typedef struct {
    uint32_t id, state, count, loaded, mask, idle, ticks, mode;
    uint32_t t0_cycles, t0_ms, dma_flags, completed_ms, repeat, emitted, underruns;
    uint32_t bridge_mask, bridge_ticks, bridge_max_lateness;
} stimulus_status_t;
extern volatile stimulus_status_t stimulus_status;
int stimulus_config(uint32_t hz, uint32_t mask, uint32_t idle, uint32_t mode, uint32_t repeat);
int stimulus_append(uint32_t offset, const char *hex);
int stimulus_start(void);
int stimulus_arm(uint32_t source, uint32_t idle_ticks);
void stimulus_stop(uint32_t state);
void stimulus_disconnect(void);
int stimulus_bridge(uint32_t sources);
void TIM1_CC_IRQHandler(void);
void DMA1_Channel5_IRQHandler(void);
#endif
