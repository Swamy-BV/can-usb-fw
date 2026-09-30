"""Package a signed MCUboot image with a standard DFU 1.1 suffix.

Offline checks only: these do not execute MCUboot or program flash.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import zlib


def suffix(payload, vid, pid):
    tail = struct.pack('<HHHH3sB', 0xffff, pid, vid, 0x0110, b'UFD', 16)
    body = payload + tail
    return body + struct.pack('<I', zlib.crc32(body) ^ 0xffffffff)


def parse(data):
    if len(data) < 16:
        raise ValueError('Short DFU image')
    revision, pid, vid, version, marker, length, crc = struct.unpack('<HHHH3sBI', data[-16:])
    if version != 0x0110 or marker != b'UFD' or length != 16:
        raise ValueError('Invalid DFU suffix')
    # Independent bitwise CRC check for the DFU suffix.
    calculated = 0xffffffff
    for byte in data[:-4]:
        calculated ^= byte
        for _ in range(8):
            calculated = (calculated >> 1) ^ (0xedb88320 if calculated & 1 else 0)
    if calculated != crc:
        raise ValueError('Invalid DFU suffix CRC')
    return data[:-16], vid, pid, revision


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('image', type=Path)
    ap.add_argument('key', type=Path)
    ap.add_argument('imgtool_path', type=Path)
    ap.add_argument('output', type=Path)
    ap.add_argument('--vid', type=int, default=0xffff)
    ap.add_argument('--pid', type=int, default=0xffff)
    args = ap.parse_args()
    sys.path.insert(0, str(args.imgtool_path))
    from imgtool.image import Image, VerifyResult
    from imgtool import keys
    from imgtool.keys.ecdsa import ECDSA256P1
    key = keys.load(str(args.key))
    if Image.verify(str(args.image), key)[0] != VerifyResult.OK:
        raise ValueError('Signed image failed verification')
    if Image.verify(str(args.image), ECDSA256P1.generate())[0] == VerifyResult.OK:
        raise ValueError('Wrong signing key was accepted')
    payload = args.image.read_bytes()
    corrupted = bytearray(payload)
    header_size = struct.unpack_from('<H', payload, 8)[0]
    corrupted[header_size] ^= 1
    with tempfile.TemporaryDirectory() as temp:
        tampered = Path(temp) / 'tampered.bin'
        tampered.write_bytes(corrupted)
        if Image.verify(str(tampered), key)[0] == VerifyResult.OK:
            raise ValueError('Tampered image was accepted')
    packaged = suffix(payload, args.vid, args.pid)
    decoded, vid, pid, _ = parse(packaged)
    if decoded != payload or (vid, pid) != (args.vid, args.pid):
        raise ValueError('DFU suffix round trip failed')
    for broken in (packaged[:15], packaged[:-1], packaged[:-4] + b'\0\0\0\0',
                   bytes([packaged[0] ^ 1]) + packaged[1:]):
        try:
            parse(broken)
        except ValueError:
            continue
        raise ValueError('Corrupt DFU image was accepted')
    args.output.write_bytes(packaged)
    print(json.dumps({'check': 'DFU-PACKAGE', 'status': 'passed',
                      'checks': ['signed-image', 'wrong-key-rejected', 'tampered-image-rejected',
                                 'suffix-round-trip', 'four-corrupt-suffixes-rejected'],
                      'dfu_sha256': hashlib.sha256(packaged).hexdigest(),
                      'payload_bytes': len(payload), 'hardware_qualified': False}))


if __name__ == '__main__':
    main()
