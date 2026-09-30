#include "fw/dfu_guard.h"
bool fw_dfu_identity_valid(uint16_t vid, uint16_t runtime_pid, uint16_t dfu_pid)
{
    return vid != 0U && vid != UINT16_MAX && runtime_pid != 0U &&
           runtime_pid != UINT16_MAX && dfu_pid != 0U && dfu_pid != UINT16_MAX;
}
bool fw_dfu_quiescent(bool acquiring, bool tx_pending) { return !acquiring && !tx_pending; }
void fw_dfu_guard_reset(fw_dfu_guard_t *guard, size_t capacity)
{
    guard->capacity = capacity;
    guard->received = 0;
    guard->next_block = 0;
    guard->complete = false;
    guard->faulted = capacity == 0U;
}
bool fw_dfu_guard_check(const fw_dfu_guard_t *guard, uint32_t block, size_t size,
                        size_t transfer_size)
{
    if (guard == NULL || guard->faulted || guard->complete || block > UINT16_MAX ||
        block != guard->next_block || size > transfer_size || transfer_size == 0U ||
        guard->received > guard->capacity) { return false; }
    if (size == 0U) { return guard->received != 0U; }
    /* Leave a block number for the terminal zero-length DNLOAD. */
    return block < UINT16_MAX && size <= guard->capacity - guard->received;
}
void fw_dfu_guard_commit(fw_dfu_guard_t *guard, size_t size)
{
    guard->received += size;
    ++guard->next_block;
    guard->complete = size == 0U;
}
