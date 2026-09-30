"""Check channel discovery with a Candle host build that includes the lab VID/PID."""
import argparse
import hashlib
import json
from pathlib import Path
import time

import candle
import candle_api
import can


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serial', required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    args.evidence.mkdir(parents=True, exist_ok=False)
    report = {'check': 'CANDLE-DISCOVERY', 'status': 'failed',
              'serial': args.serial, 'vid': 0x1FC9, 'pid': 0x00A2,
              'candle_version': candle.__version__,
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'extension_sha256': hashlib.sha256(
                  Path(candle_api.bindings.__file__).read_bytes()).hexdigest()}
    try:
        devices = [device for device in candle_api.list_device()
                   if (device.vendor_id, device.product_id, device.serial_number) ==
                   (0x1FC9, 0x00A2, args.serial)]
        if len(devices) != 1:
            raise AssertionError(f'Expected one lab adapter, found {len(devices)}')
        report['channels'] = len(devices[0])
        if report['channels'] != 2:
            raise AssertionError(f'Expected two CAN channels, found {report["channels"]}')
        with can.Bus(interface='candle', channel=(0, 1), vid=0x1FC9, pid=0x00A2,
                     serial_number=args.serial, fd=True, loop_back=True,
                     bitrate=500_000, sample_point=80.0,
                     data_bitrate=2_000_000, data_sample_point=80.0,
                     ignore_config=True) as bus:
            report['opened_channels'] = [0, 1]
            report['received_channels'] = []
            for channel in range(2):
                payload = bytes([channel + 1]) * 12
                bus.send(can.Message(channel=channel, arbitration_id=0x551 + channel,
                                     is_extended_id=False, is_fd=True,
                                     bitrate_switch=True, data=payload))
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline:
                    message = bus.recv(timeout=.2)
                    if message is None or not message.is_rx:
                        continue
                    if (message.channel, message.arbitration_id, bytes(message.data)) != \
                       (channel, 0x551 + channel, payload):
                        raise AssertionError(f'Unexpected RX channel/frame: {message!r}')
                    report['received_channels'].append(channel)
                    break
                else:
                    raise AssertionError(f'No userspace RX for channel {channel}')
        report['status'] = 'passed'
    except Exception as error:
        report['error'] = repr(error)
        raise
    finally:
        (args.evidence / 'result.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
