"""Qualify CAN FD timing through the MCXN236 controllers' internal loopback.

This never selects an external-bus mode. It does not qualify a transceiver,
CAN wiring, physical bit timing, or full-rate USB acquisition.
"""

import argparse
import hashlib
import json
from pathlib import Path
import struct
import time

import libusb_package
import usb.backend.libusb1
import usb.core
import usb.util


VID, PID = 0x1FC9, 0x00A2
SERIAL = '3A1F978456DF8D06D535A9A5BD62C632'
FD_LOOPBACK_MODE = 0x102


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    args.evidence.mkdir(parents=True, exist_ok=False)
    report = {
        'check': 'MCXN236-INTERNAL-TIMING',
        'status': 'failed',
        'usb_identity': f'{VID:04X}:{PID:04X}',
        'serial': SERIAL,
        'scope': 'controller internal loopback, not external CAN bus',
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'cases': [],
    }
    device = None
    try:
        backend = usb.backend.libusb1.get_backend(find_library=libusb_package.find_library)
        matches = [candidate for candidate in usb.core.find(
            find_all=True, idVendor=VID, idProduct=PID, backend=backend
        ) if candidate.serial_number == SERIAL]
        if len(matches) != 1:
            raise RuntimeError(f'Expected one authorized board, found {len(matches)}')
        device = matches[0]
        report['usb_speed'] = {1: 'low', 2: 'full', 3: 'high', 4: 'super',
                               5: 'super-plus'}.get(device.speed, f'unknown-{device.speed}')
        interface = device.get_active_configuration()[(0, 0)]
        if interface.bInterfaceClass != 0xFF:
            raise RuntimeError('Expected gs_usb vendor interface')
        usb.util.claim_interface(device, 0)

        def command(request, channel, words):
            device.ctrl_transfer(0x41, request, channel, 0,
                                 struct.pack(f'<{len(words)}I', *words), timeout=2000)

        def query(request, channel, count):
            raw = bytes(device.ctrl_transfer(0xC1, request, channel, 0,
                                             count * 4, timeout=2000))
            if len(raw) != count * 4:
                raise RuntimeError(f'Short response to request {request}')
            return struct.unpack(f'<{count}I', raw)

        command(0, 1, (0xBEEF,))
        config = query(5, 1, 3)
        channel_count = (config[0] >> 24) + 1
        if channel_count != 2:
            raise RuntimeError(f'Expected two channels, found {channel_count}')

        for channel in range(channel_count):
            limits = query(11, channel, 18)
            clock = limits[1]
            if clock not in (48_000_000, 50_000_000):
                raise RuntimeError(f'Unexpected CAN clock {clock} on channel {channel}')
            data = limits[10:]
            tseg1_min, tseg2_min, prescaler_min = data[0], data[2], data[5]
            minimum_tq = 1 + tseg1_min + tseg2_min
            theoretical_max = clock // (prescaler_min * minimum_tq)
            entry = {
                'channel': channel,
                'clock_hz': clock,
                'data_timing_limits': data,
                'minimum_time_quanta': minimum_tq,
                'max_rate_from_advertised_timing_hz': theoretical_max,
                '12_mbit_exact_at_current_clock': (
                    clock % 12_000_000 == 0 and clock // 12_000_000 >= minimum_tq
                ),
            }
            report.setdefault('controllers', []).append(entry)
            # Each tuple is an integer total time-quanta count at prescaler 1.
            # The first case reproduces the previously tested 2 Mbit/s timing.
            total_tq_cases = (clock // 2_000_000, 10, 6, 5)
            for total_tq in dict.fromkeys(total_tq_cases):
                phase_seg2 = 2
                phase_seg1 = total_tq - 1 - phase_seg2
                if phase_seg1 < tseg1_min or phase_seg1 > data[1]:
                    continue
                case = {
                    'channel': channel,
                    'nominal_rate_hz': 1_000_000,
                    'data_rate_hz': clock / total_tq,
                    'data_total_tq': total_tq,
                    'data_timing': [0, phase_seg1, phase_seg2, 2, 1],
                    'status': 'failed',
                }
                report['cases'].append(case)
                started = False
                try:
                    # Both controllers' nominal clock is an integer multiple of 1 MHz.
                    command(1, channel, (0, clock // 1_000_000 - 11, 10, 4, 1))
                    command(10, channel, (0, phase_seg1, phase_seg2, 2, 1))
                    command(2, channel, (1, FD_LOOPBACK_MODE))
                    started = True
                    payload = bytes(range(64))
                    can_id = 0x600 + channel * 0x10 + total_tq
                    frame = struct.pack('<IIBBBB', 0, can_id, 15, channel, 6, 0) + payload
                    if device.write(0x02, frame, timeout=2000) != len(frame):
                        raise RuntimeError('Short USB frame write')
                    received, echoed = False, False
                    deadline = time.monotonic() + 3.0
                    while time.monotonic() < deadline and not (received and echoed):
                        try:
                            raw = bytes(device.read(0x81, 80, timeout=300))
                        except usb.core.USBTimeoutError:
                            continue
                        if len(raw) < 12:
                            raise RuntimeError('Short frame from device')
                        echo, observed_id, dlc, observed_channel, flags, reserved = \
                            struct.unpack_from('<IIBBBB', raw)
                        if observed_channel != channel or reserved != 0:
                            raise RuntimeError('Channel isolation or frame header mismatch')
                        if echo == 0xFFFFFFFF:
                            if (observed_id, dlc, flags & 6, raw[12:76]) != \
                               (can_id, 15, 6, payload):
                                raise RuntimeError('Loopback RX mismatch')
                            received = True
                        elif echo == 0:
                            if (observed_id, dlc, flags & 6) != (0, 0, 6):
                                raise RuntimeError('TX echo mismatch')
                            echoed = True
                        else:
                            raise RuntimeError(f'Unexpected echo id {echo}')
                    if not (received and echoed):
                        raise RuntimeError(f'RX={received}, echo={echoed}')
                    case['status'] = 'passed'
                    case['rx_frames'] = 1
                    case['tx_echoes'] = 1
                except Exception as error:
                    case['error'] = repr(error)
                finally:
                    if started:
                        command(2, channel, (0, 0))
                # A failed high-rate case is retained; continue with other cases.
        concurrent = {
            'channel_rates_hz': [10_000_000, 9_600_000],
            'requested_per_channel': 256,
            'status': 'failed',
        }
        report['concurrent'] = concurrent
        started = []
        try:
            for channel, entry in enumerate(report['controllers']):
                clock = entry['clock_hz']
                command(1, channel, (0, clock // 1_000_000 - 11, 10, 4, 1))
                command(10, channel, (0, 2, 2, 2, 1))
                command(2, channel, (1, FD_LOOPBACK_MODE))
                started.append(channel)
            received = [set(), set()]
            echoed = [set(), set()]
            start_time = time.perf_counter()
            for start in range(0, concurrent['requested_per_channel'], 8):
                expected = set(range(start, start + 8))
                for channel in range(2):
                    for sequence in range(start, start + 8):
                        payload = sequence.to_bytes(4, 'little') + bytes([channel]) * 60
                        frame = struct.pack('<IIBBBB', sequence + 1, 0x700 + channel,
                                            15, channel, 6, 0) + payload
                        if device.write(0x02, frame, timeout=2000) != 76:
                            raise RuntimeError('Short concurrent USB write')
                for _ in range(32):
                    raw = bytes(device.read(0x81, 80, timeout=2000))
                    if len(raw) < 12:
                        raise RuntimeError('Short concurrent USB read')
                    echo, can_id, dlc, channel, flags, reserved = \
                        struct.unpack_from('<IIBBBB', raw)
                    if channel not in (0, 1) or reserved != 0:
                        raise RuntimeError('Concurrent channel isolation failed')
                    if echo == 0xFFFFFFFF:
                        sequence = int.from_bytes(raw[12:16], 'little')
                        if (can_id, dlc, flags & 6, len(raw), raw[16:76]) != \
                           (0x700 + channel, 15, 6, 76, bytes([channel]) * 60):
                            raise RuntimeError('Concurrent RX frame mismatch')
                        if sequence in received[channel]:
                            raise RuntimeError('Duplicate concurrent RX')
                        received[channel].add(sequence)
                    else:
                        sequence = echo - 1
                        if (can_id, dlc, flags & 6) != (0, 0, 6):
                            raise RuntimeError('Concurrent TX echo mismatch')
                        if sequence in echoed[channel]:
                            raise RuntimeError('Duplicate concurrent TX echo')
                        echoed[channel].add(sequence)
                    if sequence not in expected:
                        raise RuntimeError('Frame outside current concurrent batch')
            elapsed = time.perf_counter() - start_time
            if any(len(frames) != 256 for frames in received + echoed):
                raise RuntimeError('Concurrent frame count mismatch')
            concurrent.update({
                'status': 'passed',
                'rx_frames_per_channel': [len(frames) for frames in received],
                'tx_echoes_per_channel': [len(frames) for frames in echoed],
                'host_paced_seconds': elapsed,
            })
        except Exception as error:
            concurrent['error'] = repr(error)
        finally:
            for channel in reversed(started):
                command(2, channel, (0, 0))
        report['status'] = 'passed' if all(
            case['status'] == 'passed' for case in report['cases']
        ) and concurrent['status'] == 'passed' else 'partial'
    except Exception as error:
        report['error'] = repr(error)
        raise
    finally:
        if device is not None:
            usb.util.dispose_resources(device)
        (args.evidence / 'result.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
