# CAN USB firmware project

This repository is a fresh CANnectivity-based firmware port for FRDM-MCXN236.
It is the active device-firmware project. The sibling `can-analyzer-fw` is a
historical ECU1/early-gs_usb implementation and must not supply build inputs.
Read README.md before changes. Zephyr and CANnectivity are pinned submodules of
the public `Swamy-BV` forks under `.deps/`, with `development` as their update
branch. `.gitmodules` records their URLs and branches; `west.yml` records exact
tested revisions and the five other West-managed source repositories. Do not
modify the original upstream repositories or run an unqualified `west update`.
`scripts/fw.py` verifies clean pinned revisions and builds without fetching.
CANnectivity and MCUboot checkouts must remain unmodified. Preserve their
Apache-2.0 license and copyright notices when distributing firmware.

The MCU has two real FlexCAN controllers. The FRDM board has one documented
external CAN transceiver/connector; channel 1 currently uses FlexCAN0 in
internal loopback for bench verification. Keep two-channel USB enumeration
separate from two-channel external-bus qualification. Do not advertise hardware
timestamps, electrical bus performance or production USB identity without
physical evidence. The VID/PID `1FC9:00A2` is authorized for this lab only.
Keep MCX board and USB/DFU integration here; future MCU ports should use
separate board configuration and preserve the gs_usb host contract. Record
build and hardware outcomes separately, retain failed results, and commit
verified changes. Do not push or publish unless asked.

The user requires upstream CANnectivity `gs_usb`, without an ELROOT-specific
replacement or private extension to its host protocol. The project-owned EP0
vendor request in `platform/mcxn236_control` enters the unchanged MCUboot DFU
transfer path through a one-shot SRAM mailbox. The app exposes no DFU class.
The matching app and MCUboot now pass physical enumeration, full-serial
matching, signed DFU update, corrupted-image rejection and two-channel internal
loopback. Keep failed runs and the pre-flash backup; SW2/power-loss recovery and
external CAN remain open. See docs/DFU-ENTRY.md.
