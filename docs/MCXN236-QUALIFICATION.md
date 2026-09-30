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
**timing configurations accepted in internal loopback**, not MCU electrical
ratings or usable bus rates. NXP's generic FlexCAN documentation describes up
to 8 Mbit/s; the higher accepted internal settings must not be advertised as
qualified CAN operation. A source-clock change, MCXN236-specific controller
limits and transmitter-delay compensation must be reviewed before concluding
whether the MCU could meet a 12 Mbit/s product target with another PHY.

## Qualification still needed before selecting product hardware

1. Confirm the MCXN236-specific maximum FlexCAN clock, data timing and TDC
   limits from NXP's reference manual or support, including both controllers
   active and the intended payload/message-buffer configuration.
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
