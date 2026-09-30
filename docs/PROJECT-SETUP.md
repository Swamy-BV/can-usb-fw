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
| `deps.lock.json` | Exact upstream revisions and compiler version |
| `.deps/` | Ignored upstream checkouts, tools, Python environments and lab signing key |
| `patches/` | Reviewable CANnectivity compatibility delta |
| `platform/usb_guard/` | Local USB identity, DFU and Windows descriptor integration |
| `board/` | FRDM-MCXN236 pins, channels, partitions and Kconfig overlays |
| `scripts/` | Reproducible setup, build, package and lab probes |
| `verification/` | Committed outcomes, including failed checks and hardware limits |
| `build/`, `evidence/` | Ignored generated artifacts and full run logs |

The application builds upstream `cannectivity/app` directly. The project does
not fork Zephyr, CANnectivity or the NXP HAL. `setup.ps1` validates pinned
revisions and the exact allowed patch. The bootloader and application share one
partition overlay and signing key; changing either requires a paired image and
recovery review.

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
2. Give board selection, output paths and identity a named build profile so a
   second MCU can be added without copying the MCXN236 build scripts.
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
