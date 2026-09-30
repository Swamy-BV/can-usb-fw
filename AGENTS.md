# CAN USB firmware project

This repository is a fresh CANnectivity-based firmware port for FRDM-MCXN236.
Read README.md before changes. Upstream CANnectivity and Zephyr modules are
external, pinned dependencies under ignored `.deps/`; the patch in `patches/`
is the complete upstream source delta. Preserve its Apache-2.0 license and
copyright notices when distributing firmware.

The board currently has one real CAN controller. Keep the two-channel product
milestone separate from its current capabilities. Do not advertise hardware
timestamps, electrical bus performance or production USB identity without
physical evidence. The VID/PID `1FC9:00A2` is authorized for this lab only.
Keep MCX board and USB/DFU integration here; future MCU ports should use
separate board configuration and preserve the gs_usb host contract. Record
build and hardware outcomes separately, retain failed results, and commit
verified changes. Do not push or publish unless asked.
