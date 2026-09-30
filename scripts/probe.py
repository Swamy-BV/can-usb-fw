"""Probe both MCXN236 gs_usb channels through libusb and exercise internal loopback.

The Linux kernel gs_usb driver defines this host contract. This tool never
binds a kernel driver or changes another USB device. --loopback changes CAN
controller state only for the selected authorized lab adapter.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import time

import usb.backend.libusb1
import usb.core
import usb.util
import libusb_package

VID, PID = 0x1FC9, 0x00A2
OUT, IN = 0x41, 0xC1
EP_OUT, EP_IN = 0x01, 0x81


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serial', required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--loopback', action='store_true')
    parser.add_argument('--expect-channels', type=int, default=2)
    parser.add_argument('--load-count', type=int, default=0,
                        help='Host-paced FD64 internal-loopback frames (1..4096)')
    args = parser.parse_args()
    if args.load_count and (not args.loopback or not 1 <= args.load_count <= 4096):
        parser.error('--load-count requires --loopback and 1..4096 frames')
    args.evidence.mkdir(parents=True, exist_ok=False)
    report = {'check': 'MCX-USB-CAN',
              'profile': 'cannectivity',
              'status': 'failed', 'serial': args.serial,
              'loopback_requested': args.loopback, 'electrical_can_qualified': False,
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'checks': []}
    device = None
    try:
        backend = usb.backend.libusb1.get_backend(find_library=libusb_package.find_library)
        matches = [item for item in usb.core.find(find_all=True, idVendor=VID,
                   idProduct=PID, backend=backend) if item.serial_number == args.serial]
        if len(matches) != 1:
            raise RuntimeError(f'Expected one authorized lab adapter, found {len(matches)}')
        device = matches[0]
        interface = device.get_active_configuration()[(0, 0)]
        endpoints = sorted(int(ep.bEndpointAddress) for ep in interface)
        expected_endpoints = [EP_OUT, 0x02, EP_IN]
        if (interface.bInterfaceClass, endpoints) != (0xFF, expected_endpoints):
            raise AssertionError(f'Unexpected interface/endpoints: {interface.bInterfaceClass}, {endpoints}')
        usb.util.claim_interface(device, 0)
        report['checks'].append('vendor-interface-and-three-bulk-endpoints')

        def command(request, channel, data):
            return device.ctrl_transfer(OUT, request, channel, 0, data, timeout=2000)

        def query(request, channel, size):
            value = bytes(device.ctrl_transfer(IN, request, channel, 0, size, timeout=2000))
            if len(value) != size:
                raise AssertionError(f'Request {request} returned {len(value)} bytes, expected {size}')
            return value

        command(0, 1, struct.pack('<I', 0x0000BEEF))
        config = query(5, 1, 12)
        channels = config[3] + 1
        report['channels'] = channels
        report['software_version'], report['hardware_version'] = struct.unpack_from('<II', config, 4)
        report['checks'].append('host-format-and-device-config')
        if channels != args.expect_channels:
            raise AssertionError(f'Expected {args.expect_channels} channels, found {channels}')
        timing = []
        for channel in range(channels):
            base = struct.unpack('<10I', query(4, channel, 40))
            features = base[0]
            entry = {'channel': channel, 'features': features, 'clock_hz': base[1],
                     'nominal_limits': base[2:]}
            if features & (1 << 10):
                extended = struct.unpack('<18I', query(11, channel, 72))
                if extended[:10] != base:
                    raise AssertionError('Extended timing differs from base timing')
                entry['data_limits'] = extended[10:]
            if features & (1 << 13):
                entry['state'] = struct.unpack('<3I', query(14, channel, 12))
            timing.append(entry)
        report['timing'] = timing
        report['checks'].append('per-channel-timing-and-capabilities')

        if args.loopback:
            started = []
            try:
                for channel_index, entry in enumerate(timing):
                    if (entry['features'] & 0x102) != 0x102:
                        raise AssertionError(f'Channel {channel_index} lacks FD loopback')
                    clock = entry['clock_hz']
                    if clock == 50_000_000:
                        nominal, data = (39, 40, 20, 4, 1), (9, 10, 5, 4, 1)
                    elif clock == 48_000_000:
                        nominal, data = (19, 48, 28, 4, 1), (3, 12, 8, 4, 1)
                    else:
                        raise AssertionError(f'Unexpected channel {channel_index} clock {clock}')
                    command(1, channel_index, struct.pack('<5I', *nominal))
                    command(10, channel_index, struct.pack('<5I', *data))
                    command(2, channel_index, struct.pack('<2I', 1, 0x102))
                    started.append(channel_index)
                out_endpoint = 0x02
                for channel_index in range(channels):
                    samples = [(0x123 + channel_index, 8, 0, bytes(range(8))),
                               (0x123 + channel_index, 9, 6, bytes(range(12))),
                               (0x80012345 + channel_index, 15, 6, bytes(range(64)))]
                    for can_id, dlc, frame_flags, payload in samples:
                        frame = struct.pack('<IIBBBB', 0, can_id, dlc, channel_index,
                                            frame_flags, 0)
                        frame += payload + bytes(64 - len(payload))
                        if device.write(out_endpoint, frame, timeout=2000) != 76:
                            raise AssertionError('Short bulk OUT')
                        seen = set()
                        deadline = time.monotonic() + 3
                        while time.monotonic() < deadline and seen != {0, 0xFFFFFFFF}:
                            try:
                                raw = bytes(device.read(EP_IN, 76, timeout=300))
                            except usb.core.USBTimeoutError:
                                continue
                            if len(raw) < 12:
                                raise AssertionError(f'Short RX/echo frame: {len(raw)}')
                            echo, actual_id, actual_dlc, actual_channel, flags, reserved = \
                                struct.unpack_from('<IIBBBB', raw)
                            if echo == 0:
                                # CANnectivity confirms the echo ID without repeating the payload.
                                if (actual_id, actual_dlc, actual_channel, flags & 6, reserved) != \
                                   (0, 0, channel_index, frame_flags, 0):
                                    raise AssertionError(f'Echo mismatch: {raw.hex()}')
                            elif (actual_id, actual_dlc, actual_channel, flags & 6, reserved,
                                  raw[12:12 + len(payload)]) != \
                                 (can_id, dlc, channel_index, frame_flags, 0, payload):
                                raise AssertionError(f'Frame mismatch: {raw.hex()}')
                            seen.add(echo)
                        if seen != {0, 0xFFFFFFFF}:
                            raise AssertionError(f'Expected RX and TX echo on {channel_index}, got {seen}')
                report['checks'].append('per-channel-classical-fd-extended-64-byte-loopback-and-echo')
                if args.load_count:
                    report['load'] = []
                    for channel_index in range(channels):
                        start_time = time.perf_counter()
                        can_id = 0x300 + channel_index
                        for start in range(0, args.load_count, 8):
                            stop = min(start + 8, args.load_count)
                            for sequence in range(start, stop):
                                payload = sequence.to_bytes(4, 'little') + bytes([sequence & 255]) * 60
                                packet = struct.pack('<IIBBBB', sequence + 1, can_id, 15,
                                                     channel_index, 6, 0) + payload
                                if device.write(out_endpoint, packet, timeout=2000) != 76:
                                    raise AssertionError(f'Short load OUT at {channel_index}:{sequence}')
                            seen_rx, seen_echo = set(), set()
                            for _ in range(2 * (stop - start)):
                                raw = bytes(device.read(EP_IN, 80, timeout=2000))
                                if len(raw) < 12:
                                    raise AssertionError(f'Short load IN: {len(raw)}')
                                echo, actual_id, dlc, actual_channel, flags, reserved = \
                                    struct.unpack_from('<IIBBBB', raw)
                                if actual_channel != channel_index or reserved != 0:
                                    raise AssertionError(f'Load channel isolation failed: {raw.hex()}')
                                if echo == 0xFFFFFFFF:
                                    if len(raw) < 76 or (actual_id, dlc, flags & 6) != (can_id, 15, 6):
                                        raise AssertionError(f'Load RX header mismatch: {raw.hex()}')
                                    sequence = int.from_bytes(raw[12:16], 'little')
                                    if not start <= sequence < stop or raw[16:76] != bytes([sequence & 255]) * 60:
                                        raise AssertionError(f'Load RX payload mismatch: {sequence}')
                                    if sequence in seen_rx:
                                        raise AssertionError(f'Duplicate load RX {sequence}')
                                    seen_rx.add(sequence)
                                else:
                                    sequence = echo - 1
                                    if not start <= sequence < stop or sequence in seen_echo:
                                        raise AssertionError(f'Unexpected load echo {echo}')
                                    if (actual_id, dlc, flags & 6) != (0, 0, 6):
                                        raise AssertionError(f'Load echo header mismatch: {raw.hex()}')
                                    seen_echo.add(sequence)
                            if seen_rx != set(range(start, stop)) or seen_echo != set(range(start, stop)):
                                raise AssertionError(f'Load window incomplete {channel_index}:{start}:{stop}')
                        elapsed = time.perf_counter() - start_time
                        report['load'].append({'channel': channel_index, 'requested': args.load_count,
                                               'rx_frames': args.load_count,
                                               'tx_echoes': args.load_count, 'seconds': elapsed,
                                               'host_paced_frames_per_second': args.load_count / elapsed})
                    report['checks'].append('per-channel-bounded-fd64-load-rx-and-echo-reconciled')
            finally:
                for channel_index in reversed(started):
                    command(2, channel_index, struct.pack('<2I', 0, 0))
        report['status'] = 'passed'
    except Exception as error:
        report['error'] = repr(error)
        raise
    finally:
        if device is not None:
            usb.util.dispose_resources(device)
        (args.evidence / 'result.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
