#ifndef FW_BOOT_REQUEST_H
#define FW_BOOT_REQUEST_H

#include <stdint.h>

/* Last 16 bytes of FRDM-MCXN236 SRAM, excluded from both image linkers. */
#define FW_BOOT_REQUEST_ADDRESS UINT32_C(0x3002FFF0)
#define FW_BOOT_REQUEST_MAGIC UINT32_C(0x454C4446)
#define FW_BOOT_REQUEST_VERSION UINT32_C(1)

struct fw_boot_request {
    uint32_t magic;
    uint32_t inverse;
    uint32_t version;
    uint32_t reserved;
};

#endif
