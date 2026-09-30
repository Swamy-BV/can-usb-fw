# Verification record

- The single-entry CMake build produced the paired MCUboot, signed app and
  DFU file from one external PEM key. MCUboot imgtool verified the signature;
  the DFU suffix CRC and payload match were checked. No image from this build
  was flashed. See `cmake-build-20260930.json`.

- The active source setup now uses `west.yml` for all seven dependencies and
  has no Git submodules. `west manifest --validate`, `west update`, the clean
  revision check, and app/bootloader builds passed at the same source commits.
  See `west-migration-20260930.json`. No image was flashed for this migration.
  Older submodule records below are retained as historical evidence.

- The two public fork branches originally named `development` and matching Git
  submodule links were verified at the pinned Zephyr and CANnectivity commits.
  The fork branches were later replaced with `develop` at current `main` and
  made GitHub defaults; the firmware links remain at the tested commits.
  Targeted West
  update of the five support modules, dependency revision check and both app
  and MCUboot builds passed. See `submodule-setup/README.md` and retained build
  result JSON files. These are build checks; no board was flashed in this change.

- The current clean-upstream app/MCUboot pair passed EP0 entry, MCUboot's
  standard runtime DETACH and DFU slot-1 download, signed-image activation,
  corrupted-image rejection, full-serial identity in both modes, and return
  to both `gs_usb` channels. A running channel caused EP0 entry to stall. The
  4,096 FD64-frame/channel internal-loopback probe reconciled RX and TX echo.
  See `dfu-entry-hardware.json` and `../docs/DFU-ENTRY.md`. These checks do
  not establish external-bus timing, power-loss recovery or SW2 recovery for
  this revision. The prior bullets below describe the historical patched
  runtime-DFU image and remain as retained evidence.

- MCXN236-only timing pass: the connected board enumerated at USB high speed.
  At 1 Mbit/s nominal, its 50/48 MHz FlexCAN clocks accepted the data-phase
  settings in `mcu-timing-internal.json`; both channels simultaneously
  reconciled 256 FD64 RX frames and TX echoes each in internal loopback.
  The current clocks cannot generate exact 12 Mbit/s under the advertised
  minimum timing segments. NXP's MCXN236 SDK feature header also defines a
  10 Mbit/s CAN FD data-rate maximum. This is controller configuration
  evidence, not electrical CAN timing or sustained throughput qualification. See
  `../docs/MCXN236-QUALIFICATION.md`. On 2026-09-29 the ELROOT target was
  revised to up to 10 Mbit/s data phase; exact 10 Mbit/s on both channels and
  physical-bus operation remain open.

- Application 1.2.0 builds for `frdm_mcxn236`, is signed with the installed
  development key, and packages as a DFU 1.1 file. Offline wrong-key,
  tampered-image and suffix corruption checks pass.
- The USB DFU transfer completed on the authorized board, and a reset UART
  log identifies MCUboot image version 1.2.0 and CANnectivity v1.3.0 with
  two FlexCAN channels.
- USB enumeration exposes two CAN channels under one vendor interface with
  three bulk endpoints, plus a DFU runtime interface. Channel 0 maps to
  FlexCAN1 and channel 1 to FlexCAN0. The probe passed Classical CAN, CAN FD,
  extended-ID, 64-byte payload and TX echo in internal loopback on each.
  A bounded 4,096-frame FD64 run per channel reconciled every RX frame and TX
  echo while checking channel IDs. It was host-paced; see `usb-loopback.json`.
- A locally modified Candle scanner discovered two channels. `python-can`
  opened both through Candle at once and received a CAN FD frame on each;
  see `candle-two-channel.json`.
- Opening channel 0 and then channel 1 as separate Candle bus objects in one
  process failed to reopen the device after the first close. The result is
  retained in `candle-sequential-open-failure.json`. A single two-channel bus
  object opened and received on both successfully.
- The separate MCUboot build is a build check only. The board still runs its
  previously installed, compatible MCUboot; the newly built bootloader binary
  was not flashed.
- A clean application and MCUboot build used the Arm GNU 14.2.1 toolchain
  copied under this project's ignored `.deps/toolchains`. Both CMake caches
  point into `can-usb-fw`, and the resulting signed application was flashed
  and rechecked with this project's Python, LinkServer and Candle tools.
  `standalone-cutover.json` records the compiler paths and image hash.
- The first standalone build-check attempt failed because the check assumed
  CMake stored `CMAKE_C_COMPILER` as `FILEPATH`; the fresh application cache
  stored it as `STRING`. The check now accepts both CMake cache types. The
  failure is retained in `standalone-cache-check-failure.json`.
- The initial fresh bootloader/app integration build failed at link because
  `flash_img_init` was wrapped when its MCUboot-specific wrapper was absent.
  The CMake guard now enables that wrapper only when `CONFIG_MCUBOOT=y`.
  The failure is retained in `initial-build-failure.json`.
- An intermediate UART capture saved the boot log but its console print failed
  on a Windows code page conversion of stale debug bytes. `boot-log.py` now
  prints the latest boot section with replacement-safe encoding. The final
  command exits successfully and its capture is `board-boot-log.txt`.

These results do not qualify a physical CAN bus, second external transceiver, hardware
timestamp accuracy, full bus speed, production update security or power-loss
recovery. Windows Candle 1.2.4 discovers the upstream CANnectivity interface,
but its local adapter treats CANnectivity's header-only TX echo as a zero-data
CAN frame. The new Candle test validates channel opening and RX traffic but
does not validate its TX echo presentation. Windows host echo interoperability
remains a separate task.
