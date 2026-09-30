# Firmware project setup

## Active boundary

`can-usb-fw` is the active firmware repository. Its runtime CAN interface is
`gs_usb`, supplied by pinned CANnectivity and Zephyr. An app-owned EP0 vendor
request reboots into MCUboot; its standard USB DFU 1.1 interface transfers an
MCUboot-signed application. The desktop `can-viewer` currently implements the
different ECU1/protobuf transport and cannot consume this firmware yet. The
older ECU1 firmware handoff remains historical context, not this project's wire
specification.

## Source ownership

| Location | Owner and purpose |
| --- | --- |
| `west.yml` | Sole source for exact upstream repository revisions and checkout paths |
| `.west/` | Ignored local West workspace configuration |
| `.deps/` | Ignored upstream checkouts, optional local toolchain and lab signing key |
| `platform/mcxn236_control/` | Local EP0 entry command, MCUboot mailbox, WinUSB binding and slot-1 writer selection |
| `board/` | FRDM-MCXN236 pins, channels, partitions and Kconfig overlays |
| `scripts/fw.py` | Portable clean-revision verification and app/bootloader build; never fetches repositories |
| `scripts/` | DFU packaging and authorized lab probes |
| `verification/` | Committed outcomes, including failed checks and hardware limits |
| `build/`, `evidence/` | Ignored generated artifacts and full run logs |

The application builds upstream `cannectivity/app` directly. Its build manifest
fetches upstream Zephyr, CANnectivity and NXP HAL, not the GitHub forks. West
fetches the seven pinned repositories. `scripts/fw.py prepare` verifies every
revision and requires a clean checkout; `check`, `app` and `bootloader` never
fetch repositories. The bootloader and application share one partition
overlay and signing key; changing either requires a paired image and recovery
review. Python packages come from Zephyr's pinned build requirements and
MCUboot's requirements after `west update`; the developer supplies the Arm GNU
14.2.rel1 toolchain separately. See the README for exact commands.

The user requires an upstream-compatible `gs_usb` implementation. The app has
only CANnectivity's vendor interface and its existing bulk endpoints. Local
device-recipient vendor requests 0x5A (capability) and 0x5B (enter DFU) use
EP0; they do not change `gs_usb` requests or frames. `platform/mcxn236_control`
wraps Zephyr's `usb_enable` to register those requests, and wraps MCUboot's
button check to consume a one-shot 16-byte SRAM reboot mailbox. Bootloader
WinUSB descriptors and the slot-1 image-writer selection are also local. They
do not replace MCUboot's DFU state machine, image verification or signing
policy. The mailbox requires a software-reset cause. The matching images passed
a physical signed update and two-channel internal loopback; power-loss and SW2
recovery remain untested for this revision. See `DFU-ENTRY.md`.

The exact source commits and compiler version are pinned; upstream Python
requirements specify minimum versions and are not yet hash-locked. Only the
Windows build host has been checked with this portable workflow.

## Code dependencies

| Component | Pinned role |
| --- | --- |
| Zephyr 4.4.0 | RTOS, CAN/USB drivers, device model and build system |
| CANnectivity | Apache-2.0 `gs_usb` application and CAN channel handling; clean pinned checkout |
| NXP HAL | MCXN236 device definitions and FlexCAN/USB peripheral drivers |
| CMSIS and CMSIS 6 | Arm core support required by the Zephyr/NXP build |
| MCUboot | Signed-image format, image validation and DFU recovery bootloader |
| Mbed TLS | Crypto dependency in the Zephyr/MCUboot build |
| `platform/mcxn236_control` | Project-owned entry, mailbox and bootloader USB/flash integration; not downloaded |

The exact Git revisions and source URLs are in `west.yml`. Build tools are
Python 3.12+, West 1.5.0, CMake 3.30+, Ninja 1.12+ and Arm GNU 14.2.rel1.
Python build packages come from the pinned Zephyr and MCUboot requirements.
The optional `scripts/requirements-lab.txt` supplies PyUSB/libusb, pyserial
and python-can for USB/UART bench probes; Candle is a separate optional host
tool. None of those lab packages are firmware runtime dependencies. The
desktop viewer is a separate project and is not a firmware build dependency.

## MCU port rule

Keep the `gs_usb` host contract, firmware update policy and user-visible model
independent of the MCU. A new Zephyr-supported MCU gets a separate board profile
for pin control, CAN mapping, USB controller, flash layout, clocks and hardware
capabilities. It must not change the MCXN236 profile to make another board
build. Platform-specific code belongs under a named platform module. A
non-Zephyr port may reuse the host protocol and acceptance checks, but it will
need its own device stack and bootloader integration; this repository is not
currently an RTOS-independent application core.

Build output must record the selected board, toolchain, upstream revisions,
image hash and signing-key identity without publishing the private key. Lab
VID/PID `1FC9:00A2` and the development key cannot become production defaults.

## Next engineering gates

1. Qualify power-loss, stale-mailbox and SW2 recovery behavior. The EP0 entry
   and running-channel rejection passed on the board, but upstream `gs_usb`
   does not expose an authoritative pending-TX drain check. The 500 ms grace
   period is a handoff delay, not proof that all queued TX completed.
2. Add a second named board profile before porting to another MCU. The portable
   builder currently supports the `frdm_mcxn236` profile only; do not reuse its
   pin, clock, USB identity or partition overlays on another board.
3. Test interrupted-transfer recovery. Signed update and corrupted-image
   rejection passed through the newly flashed matching MCUboot.
4. Resolve host `gs_usb` TX echo behavior and add a desktop host adapter if
   `can-viewer` is to use this firmware. This is a host integration task, not a
   firmware implementation of ECU1/protobuf.
5. Qualify both channels on external CAN hardware, timestamp behavior, USB
   latency and sustained traffic. Existing loopback is host-paced and does not
   establish physical performance.

These remaining gates are not closed by a successful build or internal
loopback run.
