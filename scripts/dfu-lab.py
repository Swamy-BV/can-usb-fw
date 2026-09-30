"""Authorized MCX lab DFU transfer. Not a customer updater or bootloader updater."""
import argparse
import hashlib
import gc
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
import time
import usb.core
import usb.util
import usb.backend.libusb1
import libusb_package
spec = importlib.util.spec_from_file_location('package_dfu', Path(__file__).with_name('package-dfu.py'))
package_dfu = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package_dfu)
parse = package_dfu.parse


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--image', type=Path, required=True)
    ap.add_argument('--serial', required=True)
    ap.add_argument('--evidence', type=Path, required=True)
    ap.add_argument('--negative-signature', action='store_true')
    ap.add_argument('--dfu-mode', action='store_true', help='Continue in MCUboot in a fresh libusb process')
    ap.add_argument('--transfer-mode', action='store_true', help='Transfer from DFU download mode in a fresh libusb process')
    args = ap.parse_args()
    args.evidence.mkdir(parents=True, exist_ok=False)
    payload, vid, pid, _ = parse(args.image.read_bytes())
    if (vid, pid) != (0x1fc9, 0xa2):
        raise ValueError('Only the authorized MCX lab identity is supported')
    root = Path(__file__).resolve().parent.parent
    # The original package must verify against the installed development trust
    # key even for the explicit on-device corruption test below.
    subprocess.run([str(root/'.deps/python/Scripts/python.exe'),
                    str(root/'.deps/zephyr/bootloader/mcuboot/scripts/imgtool.py'),
                    'verify', '-k', str(root/'.deps/dfu-development.pem'),
                    str(args.image.with_name('zephyr.signed.bin'))], check=True)
    assert args.image.with_name('zephyr.signed.bin').read_bytes() == payload
    if args.negative_signature:
        payload = bytearray(payload)
        payload[struct.unpack_from('<H', payload, 8)[0]] ^= 1
        payload = bytes(payload)
    backend = usb.backend.libusb1.get_backend(find_library=libusb_package.find_library)
    report = {'check': 'MCX-DFU', 'status': 'failed',
              'serial': args.serial, 'negative_signature': args.negative_signature,
              'payload_sha256': hashlib.sha256(payload).hexdigest(),
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'statuses': [], 'bootloader_self_update': False}
    device = None

    def discover(interface_type, seconds=20):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            for candidate in usb.core.find(find_all=True, idVendor=vid, idProduct=pid, backend=backend):
                try:
                    if candidate.serial_number != args.serial:
                        usb.util.dispose_resources(candidate)
                        continue
                    raw = bytes(candidate.ctrl_transfer(0x80, 6, 0x0200, 0, 4096, timeout=1000))
                    offset = 0
                    while offset+2 <= len(raw):
                        size = raw[offset]
                        if size < 2 or offset+size > len(raw):
                            raise ValueError('Malformed configuration descriptor')
                        desc = raw[offset:offset+size]
                        offset += size
                        if size == 9 and desc[1] == 4 and tuple(desc[5:8]) == interface_type:
                            if candidate.product != 'ELROOT CANFD (2 channel)':
                                raise ValueError('Unexpected product')
                            # libusb may cache the former configuration while
                            # Windows preserves a same-PID recovery device node.
                            return candidate, candidate.get_active_configuration()[(desc[2],0)]
                except (usb.core.USBError, ValueError, NotImplementedError):
                    pass
                usb.util.dispose_resources(candidate)
            time.sleep(.2)
        raise TimeoutError(f'USB interface {interface_type} did not enumerate')

    try:
        if not args.dfu_mode and not args.transfer_mode:
            device, intf = discover((0xff, 0, 0))
            report['runtime_interface'] = intf.bInterfaceNumber
            capability = bytes(device.ctrl_transfer(0xc0, 0x5a, 0, 0, 4, timeout=2000))
            if capability != b'EL\x01\x01':
                raise ValueError(f'Unexpected DFU entry capability: {capability.hex()}')
            report['entry_capability'] = capability.hex()
            usb.util.claim_interface(device, intf.bInterfaceNumber)
            # gs_usb MODE_RESET on both channels. The target independently
            # rejects DFU entry unless both controllers report STOPPED.
            for channel in (0, 1):
                device.ctrl_transfer(0x41, 2, channel, 0,
                                     struct.pack('<2I', 0, 0), timeout=2000)
            device.ctrl_transfer(0x40, 0x5b, 0xd0f1, 0, b'', timeout=2000)
            usb.util.dispose_resources(device)
            device = None
            intf = None
            time.sleep(2)
            child_args = [sys.executable, str(Path(__file__).resolve()), '--image', str(args.image),
                          '--serial', args.serial, '--evidence', str(args.evidence/'transfer'), '--dfu-mode']
            if args.negative_signature:
                child_args.append('--negative-signature')
            subprocess.run(child_args, check=True)
            runtime_interface = report['runtime_interface']
            entry_capability = report['entry_capability']
            report.update(json.loads((args.evidence/'transfer/result.json').read_text()))
            report['runtime_interface'] = runtime_interface
            report['entry_capability'] = entry_capability
            return
        if args.dfu_mode:
            # MCUboot starts with its standard runtime descriptor. A fresh
            # process after DETACH avoids WinUSB/PyUSB's cached alt settings.
            try:
                device, intf = discover((0xfe, 1, 1), seconds=3)
            except TimeoutError:
                pass  # The board may already be in download mode.
            else:
                report['bootloader_runtime_interface'] = intf.bInterfaceNumber
                usb.util.claim_interface(device, intf.bInterfaceNumber)
                device.ctrl_transfer(0x21, 0, 1000, intf.bInterfaceNumber, None, timeout=2000)
                usb.util.dispose_resources(device)
                device = None
                time.sleep(1)
            child_args = [sys.executable, str(Path(__file__).resolve()), '--image', str(args.image),
                          '--serial', args.serial, '--evidence', str(args.evidence/'transfer'),
                          '--transfer-mode']
            if args.negative_signature:
                child_args.append('--negative-signature')
            subprocess.run(child_args, check=True)
            bootloader_runtime_interface = report.get('bootloader_runtime_interface')
            report.update(json.loads((args.evidence/'transfer/result.json').read_text()))
            if bootloader_runtime_interface is not None:
                report['bootloader_runtime_interface'] = bootloader_runtime_interface
            return
        device, intf = discover((0xfe, 1, 2))
        interface = intf.bInterfaceNumber
        usb.util.claim_interface(device, interface)
        device.set_interface_altsetting(interface=interface, alternate_setting=1)
        report['dfu_interface'] = interface
        report['target_alternate'] = 1
        extra = bytes(device.ctrl_transfer(0x80, 6, 0x0200, 0, 4096, timeout=2000))
        transfer = None
        for offset in range(len(extra)):
            if extra[offset:offset+2] == b'\x09\x21' and offset+9 <= len(extra):
                transfer = struct.unpack_from('<H', extra, offset+5)[0]
                assert struct.unpack_from('<H', extra, offset+7)[0] == 0x110
                break
        assert transfer and transfer <= 1024, extra.hex()
        report['transfer_size'] = transfer

        def status(block, final=False):
            deadline = time.monotonic()+15
            while time.monotonic() < deadline:
                value = bytes(device.ctrl_transfer(0xa1, 3, 0, interface, 6, timeout=2000))
                assert len(value) == 6
                delay = int.from_bytes(value[1:4], 'little')
                report['statuses'].append({'block': block, 'status': value[0], 'state': value[4], 'poll_ms': delay})
                assert value[0] == 0, value.hex()
                if value[4] == (8 if final else 5):
                    return
                assert value[4] in ((6, 7) if final else (3, 4)), value.hex()
                time.sleep(max(.001, delay/1000))
            raise TimeoutError('DFU status poll expired')

        started = time.monotonic()
        for block, offset in enumerate(range(0, len(payload), transfer)):
            chunk = payload[offset:offset+transfer]
            assert device.ctrl_transfer(0x21, 1, block, interface, chunk, timeout=3000) == len(chunk)
            status(block)
        final_block = (len(payload)+transfer-1)//transfer
        device.ctrl_transfer(0x21, 1, final_block, interface, b'', timeout=3000)
        status(final_block, final=True)
        usb.util.dispose_resources(device)
        device = None
        intf = None
        gc.collect()
        # A manifestation state is only transfer evidence. Runtime return and
        # independent flash/UART checks establish activation or rejection.
        time.sleep(1)
        device, intf = discover((0xff, 0, 0))
        report.update(status='transfer-and-runtime-return-passed', bytes=len(payload),
                      blocks=final_block, seconds=time.monotonic()-started)
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        if device is not None:
            usb.util.dispose_resources(device)
        (args.evidence/'result.json').write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps({k: v for k, v in report.items() if k != 'statuses'}, indent=2))


if __name__ == '__main__':
    main()
