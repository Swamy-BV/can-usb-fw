#ifndef FW_DFU_GUARD_H
#define FW_DFU_GUARD_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
typedef struct {
    size_t capacity, received;
    uint32_t next_block;
    bool complete, faulted;
} fw_dfu_guard_t;
bool fw_dfu_identity_valid(uint16_t vid, uint16_t runtime_pid, uint16_t dfu_pid);
bool fw_dfu_quiescent(bool acquiring, bool tx_pending);
void fw_dfu_guard_reset(fw_dfu_guard_t *guard, size_t capacity);
bool fw_dfu_guard_check(const fw_dfu_guard_t *guard, uint32_t block, size_t size,
                        size_t transfer_size);
void fw_dfu_guard_commit(fw_dfu_guard_t *guard, size_t size);
#endif
