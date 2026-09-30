#include <stdbool.h>
#include <zephyr/devicetree.h>
#include <zephyr/drivers/hwinfo.h>
#include <zephyr/dfu/flash_img.h>
#include <zephyr/storage/flash_map.h>
#include <zephyr/sys/util.h>
#include "fw/boot_request.h"

#define SRAM_NODE DT_CHOSEN(zephyr_sram)
BUILD_ASSERT(DT_REG_ADDR(SRAM_NODE) + DT_REG_SIZE(SRAM_NODE) == FW_BOOT_REQUEST_ADDRESS,
             "The DFU mailbox must remain outside the bootloader SRAM region");

bool __real_io_detect_pin(void);

/* Zephyr's default image writer selects slot 0 when running in MCUboot.
 * The DFU class names slot 1 as its download area for this partition layout. */
int __wrap_flash_img_init(struct flash_img_context *context)
{
    return flash_img_init_id(context, FIXED_PARTITION_ID(slot1_partition));
}

bool __wrap_io_detect_pin(void)
{
    volatile struct fw_boot_request *request =
        (volatile struct fw_boot_request *)FW_BOOT_REQUEST_ADDRESS;
    uint32_t cause = 0;
    const bool valid = request->magic == FW_BOOT_REQUEST_MAGIC &&
                       request->inverse == ~FW_BOOT_REQUEST_MAGIC &&
                       request->version == FW_BOOT_REQUEST_VERSION &&
                       request->reserved == 0;

    /* Consume before entering DFU. A later reset must not replay the request. */
    request->magic = 0;
    request->inverse = 0;
    request->version = 0;
    request->reserved = 0;

    if (valid && hwinfo_get_reset_cause(&cause) == 0 && (cause & RESET_SOFTWARE)) {
        (void)hwinfo_clear_reset_cause();
        return true;
    }

    return __real_io_detect_pin();
}
