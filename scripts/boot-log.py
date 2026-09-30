"""Capture boot UART after resetting the selected MCX lab probe."""
import argparse
from pathlib import Path
import subprocess
import sys
import time

import serial


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--linkserver', type=Path, required=True)
    parser.add_argument('--port', required=True)
    parser.add_argument('--probe', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seconds', type=float, default=3)
    args = parser.parse_args()
    with serial.Serial(args.port, 115200, timeout=.2) as port:
        port.reset_input_buffer()
        subprocess.run([str(args.linkserver), 'probe', args.probe,
                        'wiretimedreset', '100'], check=True)
        deadline = time.monotonic() + args.seconds
        data = bytearray()
        while time.monotonic() < deadline:
            data.extend(port.read(4096))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    decoded = data.decode(errors='replace')
    start = decoded.rfind('*** Booting MCUboot')
    visible = decoded[start:] if start >= 0 else decoded
    encoding = sys.stdout.encoding or 'utf-8'
    print(visible.encode(encoding, errors='backslashreplace').decode(encoding))


if __name__ == '__main__':
    main()
