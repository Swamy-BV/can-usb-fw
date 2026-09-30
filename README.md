# CAN USB firmware

This is the fresh CANnectivity-based firmware project for the FRDM-MCXN236.
It builds a Zephyr application with a `gs_usb` CAN/CAN FD interface and a
standard USB DFU 1.1 runtime interface, plus a matching MCUboot recovery
bootloader. The app source comes from pinned CANnectivity; the ELROOT-specific
USB/DFU integration lives in `platform/usb_guard`, board settings in `board`,
and the small upstream compatibility delta in `patches`.

See [project setup](docs/PROJECT-SETUP.md) for module ownership, the MCU port
rule, and the next integration gates.

The intended product is **ELROOT CANFD (2 channel)**. MCXN236 has two FlexCAN
controllers. This build maps USB channel 0 to FlexCAN1 and channel 1 to
FlexCAN0. Both can be operated in internal loopback. The FRDM board has one
documented external CAN transceiver/connector; connecting channel 1 to an
external CAN bus still needs hardware and electrical qualification.

## Build on Windows

Requirements: PowerShell 7, Git, CMake, Ninja, Python 3.12+, and Arm GNU
Toolchain 14.2.rel1. The lab toolchain is installed under ignored
`.deps/toolchains`; builds do not read the old firmware checkout. Keep a
compatible MCUboot P-256 development signing key
at `.deps/dfu-development.pem`; do not commit a private key. Use the same key
as the installed lab bootloader when testing the current board.

```powershell
pwsh -File scripts/setup.ps1 -PythonExecutable C:\path\to\python.exe
pwsh -File scripts/build-bootloader.ps1 -ToolchainPath .deps/toolchains
pwsh -File scripts/build.ps1 -ToolchainPath .deps/toolchains
```

`setup.ps1` fetches the exact commits in `deps.lock.json` into ignored
`.deps/` and applies `patches/cannectivity-elroot-port.patch`. The build writes
the signed application to `build/standalone/frdm_mcxn236/zephyr/zephyr.signed.bin`, the
standard DFU file to `build/standalone/frdm_mcxn236/zephyr/can-usb.dfu`, and the MCUboot
binary to `build/standalone/mcuboot-frdm_mcxn236/zephyr/zephyr.bin`. Build logs and
machine-readable results are under ignored `evidence/`; selected verification
results are committed in `verification/`.

The bootloader and application share the 432 KiB slot layout in
`board/partitions.overlay`. The lab board currently has an MCUboot build that
accepts the development signing key. Building a new bootloader does **not**
install or update it; bootloader replacement requires SWD. The application
can be updated through DFU when the installed bootloader and key match.

## Board checks

On the authorized board only, with the app already running:

```powershell
.deps/python/Scripts/python.exe scripts/dfu-lab.py --image build/standalone/frdm_mcxn236/zephyr/can-usb.dfu --serial 3A1F978456DF8D06D535A9A5BD62C632 --evidence evidence/dfu-run
.deps/python/Scripts/python.exe scripts/probe.py --serial 3A1F978456DF8D06D535A9A5BD62C632 --evidence evidence/usb-run --loopback --load-count 4096
```

The DFU checker validates the signed image and suffix, transfers over USB
EP0, then waits for runtime enumeration. The probe checks both channels,
vendor interface, endpoints, capabilities, CAN FD internal loopback and
channel isolation. Its load count applies to **each** channel and is
host-paced, so it is **not** a physical bus throughput or latency measurement.
Do not run it against an unrelated USB device or use the lab VID/PID as a
production identity.

The optional `scripts/discover-candle.py` check uses a locally built
`python-can-candle` 1.2.4 / `candle-api` 0.0.12 host environment whose device
scanner includes the authorized lab ID. It opens both channels together and
receives a CAN FD frame on each. The unmodified Candle scanner does not
recognize this lab identity.

## Boundaries and licensing

CANnectivity is [Apache-2.0 licensed](https://github.com/CANnectivity/cannectivity)
and its license is included in `LICENSE-CANNECTIVITY`. Preserve that license,
upstream notices, and modification attribution with distributions. This
project's patch remains separate from upstream source for review. The
development key is for lab use only; production key custody, production USB
identity, secure boot policy, bootloader self-update, power-loss recovery,
second external CAN transceiver, hardware timestamps and external CAN bus
qualification remain open. The USB protocol is `gs_usb`; this fresh port does
not implement the desktop viewer's ECU1 protobuf contract or integrate its UI.

See `verification/README.md` for evidence and remaining host compatibility
issues.

## Project cutover

This repository is the active MCXN236 firmware source and can build, sign,
package, update and probe the two-channel lab application without reading
`can-analyzer-fw`. The old firmware checkout is retained as historical ECU1
work; its four uncommitted CANnectivity bring-up files are not needed by this
repository. The development signing key and the board's currently installed
MCUboot remain lab assets, not production release credentials.

The desktop viewer still uses ECU1/protobuf and cannot acquire frames from
this `gs_usb` firmware yet. Retiring the old *device application* is complete;
the old repositories remain in place only for historical links from
`can-viewer` documentation and are not build inputs. Second-channel external
wiring, product signing/identity and electrical CAN qualification remain open.

The legacy firmware and separate bootloader projects were archived as local
ZIPs under `../archives/` on 2026-09-30. Their Git history, working files,
build outputs and evidence are included; downloaded `.deps` and private keys
are omitted. The archive names, SHA-256 checksums and retained uncommitted
file list are in `../archives/legacy-firmware-archives-20260930.json`.
