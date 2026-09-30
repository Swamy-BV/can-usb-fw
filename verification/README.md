# Verification record

- Application 1.1.9 builds for `frdm_mcxn236`, is signed with the installed
  development key, and packages as a DFU 1.1 file. Offline wrong-key,
  tampered-image and suffix corruption checks pass.
- The USB DFU transfer completed on the authorized board, and a reset UART
  log identifies MCUboot image version 1.1.9 and CANnectivity v1.3.0 with
  one actual channel.
- USB enumeration exposes one vendor CAN interface with three bulk endpoints
  and a DFU runtime interface. The probe passed Classical CAN, CAN FD,
  extended-ID, 64-byte payload and TX echo in controller internal loopback.
  A bounded 4,096-frame FD64 run reconciled all 4,096 RX frames and all
  4,096 TX echoes. It was host-paced at about 1,068 frames/s.
- The separate MCUboot build is a build check only. The board still runs its
  previously installed, compatible MCUboot; the newly built bootloader binary
  was not flashed.
- The initial fresh bootloader/app integration build failed at link because
  `flash_img_init` was wrapped when its MCUboot-specific wrapper was absent.
  The CMake guard now enables that wrapper only when `CONFIG_MCUBOOT=y`.
  The failure is retained in `initial-build-failure.json`.
- An intermediate UART capture saved the boot log but its console print failed
  on a Windows code page conversion of stale debug bytes. `boot-log.py` now
  prints the latest boot section with replacement-safe encoding. The final
  command exits successfully and its capture is `board-boot-log.txt`.

These results do not qualify a physical CAN bus, second controller, hardware
timestamp accuracy, full bus speed, production update security or power-loss
recovery. Windows Candle 1.2.4 discovers the upstream CANnectivity interface,
but its local adapter treats CANnectivity's header-only TX echo as a zero-data
CAN frame; a direct libusb probe validates the echo semantics. Windows host
library interoperability remains a separate task.
