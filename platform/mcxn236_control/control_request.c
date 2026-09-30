#include <errno.h>
#include <stdbool.h>
#include <zephyr/device.h>
#include <zephyr/devicetree.h>
#include <zephyr/drivers/can.h>
#include <zephyr/drivers/hwinfo.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/atomic.h>
#include <zephyr/sys/reboot.h>
#include <zephyr/sys/util.h>
#include <zephyr/usb/usb_device.h>
#include "fw/boot_request.h"

#define SRAM_NODE DT_CHOSEN(zephyr_sram)
BUILD_ASSERT(DT_REG_ADDR(SRAM_NODE) + DT_REG_SIZE(SRAM_NODE) == FW_BOOT_REQUEST_ADDRESS,
             "The DFU mailbox must remain outside the application SRAM region");

/* Device-recipient vendor requests, independent of the gs_usb interface. */
#define FW_REQUEST_CAPABILITIES 0x5AU
#define FW_REQUEST_ENTER_DFU 0x5BU
#define FW_REQUEST_DFU_MAGIC 0xD0F1U

static const uint8_t capabilities[] = {'E', 'L', 1, 1};
static atomic_t reboot_queued;
static usb_request_handler upstream_vendor_handler;

static bool channels_stopped(void)
{
    const struct device *const channels[] = {
        DEVICE_DT_GET(DT_NODELABEL(flexcan1)),
        DEVICE_DT_GET(DT_NODELABEL(flexcan0)),
    };

    for (size_t i = 0; i < ARRAY_SIZE(channels); ++i) {
        enum can_state state;
        if (!device_is_ready(channels[i]) ||
            can_get_state(channels[i], &state, NULL) != 0 ||
            state != CAN_STATE_STOPPED) {
            return false;
        }
    }
    return true;
}

static void reboot_to_dfu(struct k_work *work)
{
    ARG_UNUSED(work);
    volatile struct fw_boot_request *request =
        (volatile struct fw_boot_request *)FW_BOOT_REQUEST_ADDRESS;

    if (!channels_stopped() || hwinfo_clear_reset_cause() != 0) {
        atomic_clear(&reboot_queued);
        return;
    }

    request->reserved = 0;
    request->version = FW_BOOT_REQUEST_VERSION;
    request->inverse = ~FW_BOOT_REQUEST_MAGIC;
    request->magic = FW_BOOT_REQUEST_MAGIC;
    __DSB();
    sys_reboot(SYS_REBOOT_WARM);
}

K_WORK_DELAYABLE_DEFINE(dfu_reboot_work, reboot_to_dfu);

static int control_vendor_handler(struct usb_setup_packet *setup, int32_t *length,
                                  uint8_t **data)
{
    if (setup->bmRequestType == 0xC0U && setup->bRequest == FW_REQUEST_CAPABILITIES &&
        setup->wValue == 0 && setup->wIndex == 0 &&
        setup->wLength == sizeof(capabilities)) {
        *length = sizeof(capabilities);
        *data = (uint8_t *)capabilities;
        return 0;
    }

    if (setup->bmRequestType == 0x40U && setup->bRequest == FW_REQUEST_ENTER_DFU &&
        setup->wValue == FW_REQUEST_DFU_MAGIC && setup->wIndex == 0 &&
        setup->wLength == 0) {
        if (!channels_stopped() || !atomic_cas(&reboot_queued, 0, 1)) {
            return -EBUSY;
        }
        if (k_work_schedule(&dfu_reboot_work, K_MSEC(500)) <= 0) {
            atomic_clear(&reboot_queued);
            return -EIO;
        }
        *length = 0;
        return 0;
    }

    return upstream_vendor_handler != NULL ?
           upstream_vendor_handler(setup, length, data) : -ENOTSUP;
}

int __real_usb_enable(usb_dc_status_callback status_cb);

int __wrap_usb_enable(usb_dc_status_callback status_cb)
{
    bool found = false;

    STRUCT_SECTION_FOREACH(usb_cfg_data, cfg) {
        const struct usb_if_descriptor *descriptor = cfg->interface_descriptor;
        if (descriptor == NULL || descriptor->bInterfaceClass != 0xFFU ||
            descriptor->bInterfaceSubClass != 0 || descriptor->bInterfaceProtocol != 0) {
            continue;
        }
        if (found) {
            return -ENOTSUP;
        }
        found = true;
        upstream_vendor_handler = cfg->interface.vendor_handler;
        cfg->interface.vendor_handler = control_vendor_handler;
    }

    return found ? __real_usb_enable(status_cb) : -ENODEV;
}
