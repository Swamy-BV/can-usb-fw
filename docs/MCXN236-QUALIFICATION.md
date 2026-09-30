# MCXN236 controller qualification — first pass

This pass isolates the MCU and current Zephyr/FlexCAN port from transceiver and
custom-board selection. The signed application already on the FRDM board was
used; the test did not flash or rebuild it. The exact host script and results
are retained in [`mcu-timing-internal.json`](../verification/mcu-timing-internal.json).

## Observed on the connected board

The device enumerated at USB **high speed** and reported two independent CAN FD
controllers. `gs_usb` exposed a 50 MHz source clock for channel 0 (FlexCAN1)
and a 48 MHz source clock for channel 1 (FlexCAN0). The nominal phase was
configured for 1 Mbit/s in each test. Each listed data-phase setting was
accepted, and one 64-byte FD frame returned both an RX frame and TX echo in
internal loopback:

| Channel | Internal timing settings accepted, Mbit/s |
| --- | --- |
| 0, 50 MHz | 2, 5, 8.333, 10 |
| 1, 48 MHz | 2, 4.8, 8, 9.6 |

At the smallest advertised data-phase time quantum count, both controllers ran
simultaneously in internal loopback: 256 FD64 frames per channel returned 256
RX frames and 256 TX echoes per channel, with channel isolation preserved. The
host paced this run. Its elapsed time is **not** a CAN frame-rate measurement.

With the current 50/48 MHz sources and five minimum time quanta per data bit,
12 Mbit/s cannot be generated exactly on either controller. The mathematical
configurable ceilings are 10 and 9.6 Mbit/s respectively. Those values are
**timing configurations accepted in internal loopback**, not qualified bus
rates. The [MCXN23x datasheet, Rev 3](https://www.nxp.com/docs/en/data-sheet/MCXN23x.pdf)
lists two CAN FD controllers but does not publish a CAN FD data-rate maximum.
NXP's [MCUXpresso SDK release notes](https://mcuxpresso.nxp.com/mcuxsdk/25.09.00-pvw1/html/_assets/boards/frdmmcxn236/mcuxsdk-frdmmcxn236.pdf)
explicitly say the CAN FD maximum was updated to 10 Mbit/s for MCX Nx3x/Nx4x.
The pinned NXP MCUXpresso device feature header
(`.deps/zephyr/modules/hal/nxp/mcux/mcux-sdk-ng/devices/MCX/MCXN/MCXN236/MCXN236_features.h`)
defines `FSL_FEATURE_FLEXCAN_MAX_CANFD_BITRATE` as **10,000,000 bit/s** for
MCXN236. NXP's FlexCAN driver uses that device-specific value as its CAN FD
bitrate limit; its generic 8 Mbit/s fallback applies only when no device value
is defined. An older [NXP MCXN adapter application note](https://www.nxp.com/docs/en/application-note/AN14253.pdf)
also says 8 Mbit/s, so the SDK update is the newer, device-specific guidance.
**10 Mbit/s is NXP's declared SDK ceiling, not a datasheet-guaranteed external
bus measurement or proof of a hard silicon limit.** The former 12 Mbit/s
data phase exceeds that ceiling. A different clock or transceiver alone does
not establish support above it; seek explicit NXP confirmation before treating
12 Mbit/s as possible on MCXN236.

On 2026-09-29 the ELROOT product target was revised to **up to 10 Mbit/s CAN FD
data phase at 1 Mbit/s nominal**, beginning with two channels. PEAK's advertised
12 Mbit/s remains a comparison point, not this firmware's target. The present
48 MHz source on channel 1 generated 9.6 Mbit/s in internal loopback, so an
exact 10 Mbit/s configuration on both channels still needs clock work and
external-bus qualification. Do not advertise 10 Mbit/s on both channels yet.

## Qualification still needed before selecting product hardware

1. Confirm the 10 Mbit/s SDK limit and applicable FlexCAN clock, data timing
   and TDC limits with NXP, including both controllers active and the intended
   payload/message-buffer configuration.
2. Measure actual CAN_TX/CAN_RX timing at controller pins with suitable test
   equipment or a temporary known-good PHY/bus. Internal loopback does not
   exercise bus pins, transceiver delay, arbitration or errors.
3. Measure simultaneous receive capacity, loss accounting, timestamp origin and
   cross-channel skew; the 256-frame host-paced check proves none of these.
4. If firmware-side periodic TX is required, implement a bounded target job
   engine and measure dispatch jitter and final bus completion separately.
5. Recheck USB high-speed enumeration and sustained bidirectional throughput
   with independent traffic. Enumeration alone does not prove the data path.

External transceivers, isolation, termination and a second connector remain
board-design choices. No production CAN speed or PCAN parity is claimed from
this first pass.
