# CAN USB firmware project

This repository is a fresh CANnectivity-based firmware port for FRDM-MCXN236.
Read README.md before changes. Upstream CANnectivity and Zephyr modules are
external, pinned dependencies under ignored `.deps/`; the patch in `patches/`
is the complete upstream source delta. Preserve its Apache-2.0 license and
copyright notices when distributing firmware.

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
