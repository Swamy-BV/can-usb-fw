# CAN USB firmware

This is the fresh CANnectivity-based firmware project for the FRDM-MCXN236.
It builds a Zephyr application with an upstream `gs_usb` CAN/CAN FD interface
and a matching MCUboot recovery bootloader. The app source comes from a clean,
pinned CANnectivity checkout. Project-owned DFU entry control lives in
`platform/mcxn236_control`; board settings live in `board`. The app exposes a
device-level EP0 vendor command to reboot into MCUboot. A standard DFU DETACH
then selects MCUboot's download mode for the signed application transfer. No
CANnectivity or MCUboot source
patch is required.

See [project setup](docs/PROJECT-SETUP.md) for module ownership, the MCU port
rule, and the next integration gates.
The first [MCXN236 controller qualification](docs/MCXN236-QUALIFICATION.md)
records current clock/timing limits and simultaneous internal loopback; it does
not establish a physical CAN data rate.

The intended product is **ELROOT CANFD (2 channel)**. MCXN236 has two FlexCAN
controllers. This build maps USB channel 0 to FlexCAN1 and channel 1 to
FlexCAN0. Both can be operated in internal loopback. The FRDM board has one
documented external CAN transceiver/connector; connecting channel 1 to an
external CAN bus still needs hardware and electrical qualification.

## Portable workspace and build (Windows verified)

Install Python 3.12+, Git, CMake 3.30+, Ninja 1.12+ and Arm GNU Toolchain
14.2.rel1. The compiler must be supplied separately. Clone this repository,
create and activate a Python virtual environment, then run:

```text
python -m pip install -r scripts/requirements-bootstrap.txt
mkdir .west
west config --local manifest.path .
west config --local manifest.file west.yml
west update
python -m pip install -r .deps/zephyr/zephyr/scripts/requirements-base.txt
python -m pip install -r .deps/zephyr/bootloader/mcuboot/scripts/requirements.txt
python scripts/fw.py prepare
python scripts/fw.py bootloader --toolchain /path/to/arm-gnu-toolchain --key /path/to/development.pem
python scripts/fw.py app --toolchain /path/to/arm-gnu-toolchain --key /path/to/development.pem
```

All seven firmware source dependencies are fetched by West at the exact
commits in `west.yml`. Zephyr and CANnectivity come from the public `Swamy-BV`
forks; the other five come from Zephyr project repositories. CANnectivity is
pinned to commit `878670b`, an
ancestor of fork `develop` and the last commit before upstream removed the
legacy USB stack. It is 65 commits behind the 2026-09-30 `develop` tip.
The tip requires newer Zephyr USB APIs and does not compile with the pinned
4.4.0 release. Zephyr stays at 4.4.0 for this release; consider an
upgrade with the next major firmware release and qualify it before changing
the pin. West places the checkouts under `.deps/`; `west update` follows the
immutable manifest revisions rather than branch tips. The portable
`scripts/fw.py` builder checks those revisions and clean checkouts; it does
not download or install dependencies.
Run `python scripts/fw.py check` for a read-only check. If CMake
or Ninja is installed but not on `PATH`, pass `--cmake` or `--ninja` with its
executable path. Set `GNUARMEMB_TOOLCHAIN_PATH` instead of `--toolchain` if
preferred. The supported first board profile is `frdm_mcxn236`; other MCUs
need their own board profiles.
The same commands are intended for Linux and macOS; builds on those hosts
have not yet been verified. Python build packages follow upstream version
constraints rather than a hash-locked wheel set.
The Arm compiler, development signing key, build outputs and local West
configuration remain outside Git. There are no Git submodules in this project.

Keep a compatible MCUboot P-256 **development** signing key outside Git. A
new lab-only pair can be created with
`python .deps/zephyr/bootloader/mcuboot/scripts/imgtool.py keygen -k .deps/dfu-development.pem -t ecdsa-p256`.
An existing board accepts updates only from a key matching its installed
bootloader. The build writes the signed application to
`build/standalone/frdm_mcxn236/zephyr/zephyr.signed.bin`, the DFU package to
`build/standalone/frdm_mcxn236/zephyr/can-usb.dfu`, and MCUboot to
`build/standalone/mcuboot-frdm_mcxn236/zephyr/zephyr.bin`. Full build logs and
machine-readable results are under ignored `evidence/`; selected outcomes are
committed in `verification/`.

The bootloader and application share the 432 KiB slot layout in
`board/partitions.overlay`. The lab board currently has an MCUboot build that
accepts the development signing key. Building a new bootloader does **not**
install or update it; bootloader replacement requires SWD. The application
can be updated through DFU when the installed bootloader and key match.

## Board checks

On the authorized board only, with the app already running:

Install `scripts/requirements-lab.txt` in the same Python environment before
running USB/UART probes. These packages are not needed to compile firmware.

```text
python scripts/dfu-lab.py --image build/standalone/frdm_mcxn236/zephyr/can-usb.dfu --serial <authorized-board-serial> --evidence evidence/dfu-run
python scripts/probe.py --serial <authorized-board-serial> --evidence evidence/usb-run --loopback --load-count 4096
python scripts/probe-dfu-entry.py --serial <authorized-board-serial> --evidence evidence/dfu-entry-run
```

The DFU checker stops both `gs_usb` channels, requests DFU entry through EP0,
issues standard DFU DETACH in MCUboot, validates the signed image and suffix,
transfers through MCUboot's standard USB DFU interface, then waits for `gs_usb`
runtime enumeration. The entry probe checks rejection with a running channel.
The CAN probe checks both channels,
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
upstream notices, and modification attribution with distributions. The
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
