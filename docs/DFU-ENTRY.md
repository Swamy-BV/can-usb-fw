# Application DFU entry on FRDM-MCXN236

The application has one upstream CANnectivity `gs_usb` vendor interface. It has
no DFU runtime interface. MCUboot exposes the standard USB DFU 1.1 interface
after a reboot. The application adds only these device-recipient EP0 requests:

| Request | bmRequestType | bRequest | wValue | wIndex | wLength | Result |
| --- | --- | --- | --- | --- | --- | --- |
| Entry capability | `0xC0` | `0x5A` | 0 | 0 | 4 | `45 4c 01 01` (`EL`, version 1, entry available) |
| Enter MCUboot | `0x40` | `0x5B` | `0xD0F1` | 0 | 0 | ACK, then reboot |

Other vendor requests are forwarded to the interface handler. `gs_usb` control
requests and bulk frame layout stay upstream. The magic value prevents an
accidental request; it is not authentication. Only an authorized lab device
with VID/PID `1FC9:00A2` and matching full serial is a supported target.

The host sends `gs_usb` MODE_RESET to both channels before entry. The firmware
also requires both FlexCAN controllers to report STOPPED and rejects an entry
request while a reboot is already queued. A 500 ms delay lets EP0 complete.
Upstream `gs_usb` has no authoritative pending-TX count exposed here, so this
does not prove that all queued TX frames reached the bus. The host should stop
its TX producers and settle outstanding requests before MODE_RESET.

At the delayed reboot, the app checks STOPPED again, clears reset-cause state,
writes a magic/inverse/version/reserved record in 16 bytes reserved at the top
of translated MCXN236 SRAM (`0x3002FFF0`), and makes a software reset. The
project-owned MCUboot hook consumes the record, checks the software-reset
cause and enters the existing DFU recovery path. An absent or invalid record
falls through to MCUboot's physical SW2 button check. Both images exclude the
mailbox from their linked SRAM regions. Neither upstream source tree is patched.

MCUboot first exposes a standard DFU runtime interface (class/subclass/protocol
`FE/01/01`). The host issues standard DFU DETACH, reconnects in a fresh libusb
process, selects alternate setting 1 in DFU mode (`FE/01/02`), and downloads
the signed app. The project module registers the bootloader's WinUSB OS
descriptor and keeps the full board serial in both modes. A local flash-image
initialization hook selects the 432 KiB slot 1 partition for MCUboot's DFU
writer; Zephyr's default image writer otherwise chooses slot 0 while running
inside the bootloader. The upstream DFU state machine, image validation and
`gs_usb` implementation are unchanged.

The matching app and bootloader passed board enumeration, full-serial match,
capability readback, running-channel rejection, signed update, corrupted-image
rejection and return to the app, and two-channel internal loopback. See
`../verification/dfu-entry-hardware.json`. SW2 recovery, interrupted transfer,
power-loss handling, stale-mailbox behavior after power cycling, and external
CAN remain open. Keep the pre-flash backup for recovery. Bootloader replacement
uses SWD; the EP0 command never updates the bootloader itself.
