# Firmware project setup

## Active boundary

`can-usb-fw` is the active firmware repository. Its runtime CAN interface is
`gs_usb`, supplied by pinned CANnectivity and Zephyr. USB DFU 1.1 transfers an
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
| `patches/` | Reviewable CANnectivity compatibility delta |
| `platform/usb_guard/` | Local USB identity, DFU and Windows descriptor integration |
| `board/` | FRDM-MCXN236 pins, channels, partitions and Kconfig overlays |
| `scripts/fw.py` | Portable revision/patch verification and app/bootloader build; never fetches repositories |
| `scripts/` | DFU packaging and authorized lab probes |
| `verification/` | Committed outcomes, including failed checks and hardware limits |
| `build/`, `evidence/` | Ignored generated artifacts and full run logs |

The application builds upstream `cannectivity/app` directly. The project does
not fork Zephyr, CANnectivity or the NXP HAL. West fetches the seven pinned
repositories. `scripts/fw.py prepare` verifies every revision and applies only
the reviewed CANnectivity compatibility patch; `check`, `app` and `bootloader`
never fetch repositories. The bootloader and application share one partition
overlay and signing key; changing either requires a paired image and recovery
review. Python packages come from Zephyr's pinned build requirements and
MCUboot's requirements after `west update`; the developer supplies the Arm GNU
14.2.rel1 toolchain separately. See the README for exact commands.
The exact source commits and compiler version are pinned; upstream Python
requirements specify minimum versions and are not yet hash-locked. Only the
Windows build host has been checked with this portable workflow.

## Code dependencies

| Component | Pinned role |
| --- | --- |
| Zephyr 4.4.0 | RTOS, CAN/USB drivers, device model and build system |
| CANnectivity | Apache-2.0 `gs_usb` application and CAN channel handling; two upstream files carry the reviewed local patch |
| NXP HAL | MCXN236 device definitions and FlexCAN/USB peripheral drivers |
| CMSIS and CMSIS 6 | Arm core support required by the Zephyr/NXP build |
| MCUboot | Signed-image format, image validation and DFU recovery bootloader |
| Mbed TLS | Crypto dependency in the Zephyr/MCUboot build |
| `platform/usb_guard` | Our own DFU and WinUSB descriptor integration; not downloaded |

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

1. Replace the unconditional weak `fw_dfu_app_quiescent()` implementation with
   an authoritative CAN/TX stop state before treating DFU detach as interlocked.
2. Add a second named board profile before porting to another MCU. The portable
   builder currently supports the `frdm_mcxn236` profile only; do not reuse its
   pin, clock, USB identity or partition overlays on another board.
3. Test a signed update from the newly built matching MCUboot, including
   failed-image recovery and interrupted-transfer behavior. Its current binary
   has only been built; the board runs an older compatible bootloader.
4. Resolve host `gs_usb` TX echo behavior and add a desktop host adapter if
   `can-viewer` is to use this firmware. This is a host integration task, not a
   firmware implementation of ECU1/protobuf.
5. Qualify both channels on external CAN hardware, timestamp behavior, USB
   latency and sustained traffic. Existing loopback is host-paced and does not
   establish physical performance.

These are open gates; none are closed by a successful build or internal
loopback run.
