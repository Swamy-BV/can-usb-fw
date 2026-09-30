# Verification record

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
