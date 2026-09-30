# CAN USB firmware

This repository integrates the upstream CANnectivity `gs_usb` application with
the FRDM-MCXN236 board and an MCUboot USB DFU recovery bootloader. It does not
contain a second CAN stack or a fork of the `gs_usb` wire protocol.

| Location | Purpose |
| --- | --- |
| `west.yml` | Pins Zephyr 4.4.0, CANnectivity and five supporting source repositories |
| `board/` | Two CAN channel mapping, USB settings and flash partitions |
| `platform/mcxn236_control/` | Project C code for DFU entry, bootloader handoff and Windows USB binding |
| `CMakeLists.txt` | Builds both images and calls Zephyr/MCUboot signing |
| `tools/dfu_suffix.c` | Adds the standard DFU suffix through CANnectivity's CMake target |
| `verification/` | Retained build and hardware results, including failures |

The application runs CANnectivity code from `.deps/cannectivity/app`. West
downloads its pinned sources into the ignored `.deps/` directory. The Arm
compiler and development signing key are supplied separately and are not
committed.

## Build on a new machine

Install Python 3.12+, Git, CMake 3.30+, Ninja 1.12+, a host C compiler and
Arm GNU Toolchain 14.2.rel1. Create a Python virtual environment in the cloned
repository, then:

```text
python -m pip install west==1.5.0
mkdir .west
west config --local manifest.path .
west config --local manifest.file west.yml
west update
python -m pip install -r .deps/zephyr/zephyr/scripts/requirements-base.txt
python -m pip install -r .deps/zephyr/bootloader/mcuboot/scripts/requirements.txt
cmake -S . -B build/fw -DFW_TOOLCHAIN_ROOT=<arm-toolchain-dir> -DFW_SIGNING_KEY=<private-p256.pem> -DFW_PYTHON_EXECUTABLE=<venv-python>
cmake --build build/fw --config Release
```

`west update` fetches the exact revisions in `west.yml`. The one CMake build
produces `build/fw/bootloader/zephyr/zephyr.bin`,
`build/fw/app/zephyr/zephyr.signed.bin` and
`build/fw/app/zephyr/zephyr.signed.bin.dfu`. Zephyr/MCUboot signs the app with
the one private PEM key; CANnectivity's CMake target packages the DFU file.
The key, toolchain and downloaded sources stay outside Git. The VID/PID
`1FC9:00A2` in the FRDM profile is lab-only. `FW_VERSION` sets the app image
version (default `1.2.0`). See [project setup](docs/PROJECT-SETUP.md).

## Current status

- USB exposes two CAN/CAN FD channels: channel 0 is FlexCAN1 and channel 1 is
  FlexCAN0. The FRDM board has one documented external CAN transceiver;
  channel 1 external-bus operation remains unqualified.
- The paired app and MCUboot previously passed signed DFU update and internal
  loopback on the board. The current source pin and West-only setup build, but
  the newly built images have not been flashed. See [DFU entry](docs/DFU-ENTRY.md)
  and [verification](verification/README.md).
- Zephyr stays at 4.4.0. CANnectivity is pinned to the latest tested commit
  compatible with its legacy USB stack; its current `develop` tip needs a
  newer Zephyr USB API.
- The desktop CAN viewer still uses ECU1/protobuf and does not yet speak this
  firmware's `gs_usb` protocol.

Historical lab results do not qualify external CAN timing, production
identity, signing key custody or power-loss recovery. CANnectivity is
Apache-2.0 licensed; its license is retained in `LICENSE-CANNECTIVITY`.
