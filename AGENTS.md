# CAN USB firmware project

Read README.md first. Keep this repository lean: the project owns only the
FRDM-MCXN236 board profile, MCU control module, CMake entry point and dependency
manifest. Do not add project Python wrappers. West fetches exact commits from
`west.yml`; Zephyr stays at 4.4.0 for this release. Keep CANnectivity and
MCUboot checkouts clean and preserve upstream licenses.

The top-level CMake build makes the paired MCUboot and app images using one
external PEM key. Follow README.md for setup and build commands. Preserve the
upstream `gs_usb` contract; local EP0 requests only enter MCUboot's standard
USB DFU path. A future MCU gets a separate board/platform profile.

The FRDM board has one documented external CAN transceiver. Two-channel USB
enumeration and internal loopback do not qualify two external channels, real
bus speed, timestamps or production identity. VID/PID `1FC9:00A2` is lab-only.
Preserve failures in new evidence or Git history and distinguish build, bench
and physical-bus results. Commit verified changes; push only when requested.
