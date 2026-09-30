/* Project-owned Windows binding for runtime composite and recovery DFU. */
#include <zephyr/usb/usb_device.h>
#include <zephyr/usb/bos.h>
#include <zephyr/usb/msos_desc.h>
#include <zephyr/sys/byteorder.h>
#include <string.h>
static uint8_t set[768];
static bool dfu_mode;
static bool registered;
static usb_request_handler original_vendor[4];
static uint8_t original_interface[4];
static unsigned original_count;
USB_DEVICE_BOS_DESC_DEFINE_CAP struct {
    struct usb_bos_platform_descriptor platform;
    struct usb_bos_capability_msos capability;
} __packed dfu_bos={
    .platform={.bLength=sizeof(struct usb_bos_platform_descriptor)+sizeof(struct usb_bos_capability_msos),
        .bDescriptorType=USB_DESC_DEVICE_CAPABILITY,.bDevCapabilityType=USB_BOS_CAPABILITY_PLATFORM,
        .PlatformCapabilityUUID={0xDF,0x60,0xDD,0xD8,0x89,0x45,0xC7,0x4C,0x9C,0xD2,0x65,0x9D,0x9E,0x64,0x8A,0x9F}},
    .capability={0x06030000,0,0x21,0}
};
static size_t descriptors(void)
{
    uint8_t interfaces[4]; unsigned count=0;
    STRUCT_SECTION_FOREACH(usb_cfg_data,cfg) {
        const struct usb_if_descriptor *d=cfg->interface_descriptor;
        if (d && (d->bInterfaceClass==0xff ||
            (d->bInterfaceClass==0xfe && d->bInterfaceProtocol==1))) {
            if (count<4) { interfaces[count++]=d->bInterfaceNumber; }
        }
    }
    if (dfu_mode) { count=1; interfaces[0]=0; }
    size_t offset=sizeof(struct msosv2_descriptor_set_header);
    for (unsigned i=0;i<count;++i) {
        struct msosv2_compatible_id compatible={sizeof(compatible),MS_OS_20_FEATURE_COMPATIBLE_ID,"WINUSB",{0}};
        struct msosv2_guids_property property={.wLength=sizeof(property),.wDescriptorType=MS_OS_20_FEATURE_REG_PROPERTY,
            .wPropertyDataType=MS_OS_20_PROPERTY_DATA_REG_MULTI_SZ,.wPropertyNameLength=42,
            .PropertyName={DEVICE_INTERFACE_GUIDS_PROPERTY_NAME},.wPropertyDataLength=80};
        const char *guid="{49AB4B31-1316-4D74-A1E4-20334A76C0DD}";
        for (unsigned j=0;j<38;++j) { property.bPropertyData[j*2]=(uint8_t)guid[j]; }
        if (count>1) {
            struct msosv2_function_subset_header function={sizeof(function),MS_OS_20_SUBSET_HEADER_FUNCTION,
                interfaces[i],0,sizeof(function)+sizeof(compatible)+sizeof(property)};
            memcpy(set+offset,&function,sizeof(function)); offset+=sizeof(function);
        }
        memcpy(set+offset,&compatible,sizeof(compatible)); offset+=sizeof(compatible);
        memcpy(set+offset,&property,sizeof(property)); offset+=sizeof(property);
    }
    struct msosv2_descriptor_set_header header={sizeof(header),MS_OS_20_SET_HEADER_DESCRIPTOR,0x06030000,offset};
    memcpy(set,&header,sizeof(header));
    dfu_bos.capability.wMSOSDescriptorSetTotalLength=offset;
    return offset;
}
static int vendor(struct usb_setup_packet *setup,int32_t *length,uint8_t **data)
{
    if (setup->bmRequestType==0xc0 && setup->bRequest==0x21 && setup->wIndex==7 && !setup->wValue) {
        *length=descriptors(); *data=set; return 0;
    }
    for (unsigned i=0;i<original_count;++i) {
        if (original_interface[i]==(setup->wIndex & 0xff) &&
            original_vendor[i](setup,length,data)==0) { return 0; }
    }
    return -ENOTSUP;
}
void fw_dfu_windows_init(void)
{
    dfu_mode=false;
    descriptors();
    original_count=0;
    STRUCT_SECTION_FOREACH(usb_cfg_data,cfg) {
        if (cfg->interface.vendor_handler && cfg->interface.vendor_handler!=vendor &&
            original_count<4) {
            original_vendor[original_count]=cfg->interface.vendor_handler;
            original_interface[original_count]=((const struct usb_if_descriptor *)cfg->interface_descriptor)->bInterfaceNumber;
            ++original_count;
        }
        cfg->interface.vendor_handler=vendor;
    }
    if (!registered) { usb_bos_register_cap(&dfu_bos); registered=true; }
}
void fw_dfu_windows_mode(void) { dfu_mode=true; descriptors(); }
int __real_usb_set_config(const uint8_t *description);
int __wrap_usb_set_config(const uint8_t *description)
{
    /* Upstream's alternate descriptor uses USB 2.0. Advertise 2.1 so Windows
     * requests the registered BOS/MS OS 2 descriptor after DFU detach too. */
    if (description && description[1]==USB_DESC_DEVICE) {
        sys_put_le16(0x0210,(uint8_t *)description+2);
    }
    return __real_usb_set_config(description);
}
