"""Check EP0 DFU entry capability and running-channel rejection on the MCX lab board."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

import usb.backend.libusb1
import usb.core
import usb.util
import libusb_package


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serial', required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    args.evidence.mkdir(parents=True, exist_ok=False)
    report = {'check': 'MCX-DFU-ENTRY-INTERLOCK', 'status': 'failed',
              'serial': args.serial,
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    backend = usb.backend.libusb1.get_backend(find_library=libusb_package.find_library)
    device = usb.core.find(idVendor=0x1fc9, idProduct=0xa2, backend=backend)
    started = False
    try:
        if device is None or device.serial_number != args.serial:
            raise ValueError('Authorized MCX lab board was not found')
        usb.util.claim_interface(device, 0)
        capability = bytes(device.ctrl_transfer(0xc0, 0x5a, 0, 0, 4, timeout=2000))
        if capability != b'EL\x01\x01':
            raise ValueError(f'Unexpected entry capability: {capability.hex()}')
        report['capability'] = capability.hex()
        base = struct.unpack('<10I', bytes(device.ctrl_transfer(0xc1, 4, 0, 0, 40)))
        clock = base[1]
        if clock != 50_000_000:
            raise ValueError(f'Unexpected channel 0 clock: {clock}')
        device.ctrl_transfer(0x41, 1, 0, 0, struct.pack('<5I', 39, 40, 20, 4, 1))
        device.ctrl_transfer(0x41, 10, 0, 0, struct.pack('<5I', 9, 10, 5, 4, 1))
        device.ctrl_transfer(0x41, 2, 0, 0, struct.pack('<2I', 1, 0x102))
        started = True
        state = struct.unpack('<3I', bytes(device.ctrl_transfer(0xc1, 14, 0, 0, 12)))
        report['running_state'] = state
        try:
            device.ctrl_transfer(0x40, 0x5b, 0xd0f1, 0, b'', timeout=2000)
        except usb.core.USBError as error:
            report['entry_rejection'] = str(error)
        else:
            raise AssertionError('DFU entry was accepted while channel 0 was running')
        device.ctrl_transfer(0x41, 2, 0, 0, struct.pack('<2I', 0, 0))
        started = False
        report['status'] = 'passed'
    except Exception as error:
        report['error'] = repr(error)
        raise
    finally:
        if device is not None:
            if started:
                try:
                    device.ctrl_transfer(0x41, 2, 0, 0, struct.pack('<2I', 0, 0))
                except usb.core.USBError:
                    pass
            usb.util.dispose_resources(device)
        (args.evidence / 'result.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
