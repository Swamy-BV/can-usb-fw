#include <errno.h>
#include <zephyr/kernel.h>
#include <zephyr/usb/usb_device.h>
#include <zephyr/usb/class/usb_dfu.h>
#include <zephyr/storage/flash_map.h>
#include <zephyr/dfu/flash_img.h>
#include "fw/dfu_guard.h"

static usb_request_handler original_class;
#ifdef CONFIG_MCUBOOT
int __wrap_flash_img_init(struct flash_img_context *context)
{
    return flash_img_init_id(context, FIXED_PARTITION_ID(slot1_partition));
}
#endif
static fw_dfu_guard_t transfer;
void fw_dfu_windows_init(void);
void fw_dfu_windows_mode(void);
__weak bool fw_dfu_app_quiescent(void) { return true; }
/* Pinned legacy Zephyr DFU provides the wire state machine and flash staging.
 * This adapter adds sequential/bounded download guards without modifying SDKs. */
static int guarded_class(struct usb_setup_packet *setup, int32_t *len, uint8_t **data)
{
    if (setup->bRequest == DFU_DETACH && !fw_dfu_app_quiescent()) {
        return -EBUSY;
    }
    if (setup->bRequest == DFU_DNLOAD) {
        if (!fw_dfu_guard_check(&transfer, setup->wValue, setup->wLength,
                                CONFIG_USB_REQUEST_BUFFER_SIZE)) {
            transfer.faulted = true;
            return -EINVAL;
        }
    }
    int result = original_class(setup, len, data);
    if (result == 0 && setup->bRequest == DFU_DETACH) { fw_dfu_windows_mode(); }
    if (result == 0 && setup->bRequest == DFU_DNLOAD) {
        fw_dfu_guard_commit(&transfer, setup->wLength);
    }
    if (result == 0 && (setup->bRequest == DFU_ABORT || setup->bRequest == DFU_CLRSTATUS)) {
        fw_dfu_guard_reset(&transfer, FIXED_PARTITION_SIZE(slot1_partition));
    }
    return result;
}
int __real_usb_enable(usb_dc_status_callback status_cb);
int __wrap_usb_enable(usb_dc_status_callback status_cb)
{
    if (!fw_dfu_identity_valid(CONFIG_USB_DEVICE_VID, CONFIG_USB_DEVICE_PID,
                               CONFIG_USB_DEVICE_DFU_PID)) {
        printk("USB disabled: supply authorized lab VID/PIDs\n");
        return -ENODEV;
    }
    fw_dfu_guard_reset(&transfer, FIXED_PARTITION_SIZE(slot1_partition));
    STRUCT_SECTION_FOREACH(usb_cfg_data, cfg) {
        struct usb_if_descriptor *desc = cfg->interface_descriptor;
        if (desc == NULL || desc->bInterfaceClass != 0xfeU ||
            desc->bInterfaceSubClass != 1U) { continue; }
        if (cfg->interface.class_handler != guarded_class) {
            if (original_class != NULL && original_class != cfg->interface.class_handler) {
                return -ENOTSUP;
            }
            original_class = cfg->interface.class_handler;
            cfg->interface.class_handler = guarded_class;
        }
    }
    if (original_class == NULL) { return -ENODEV; }
    fw_dfu_windows_init();
    return __real_usb_enable(status_cb);
}
