# West/portable builder migration — 2026-09-30

Historical setup record. The current project uses Zephyr and CANnectivity fork
submodules plus five West-managed repositories; see
`../submodule-setup/README.md` and `../../README.md` for the current workflow.
During the 2026-09-30 cleanup, `west manifest --validate` and
`python scripts/fw.py check` both passed. No firmware source changed or board
was flashed in this cleanup.

`west.yml` now pins the seven Git source dependencies. `west manifest
--validate` and `west list` passed against the existing workspace; `scripts/fw.py
check` verified each checkout commit and the exact CANnectivity patch. West is
the only dependency fetch path. The former PowerShell fetch/build scripts and
duplicate lock file were removed.

The first portable application configure failed because the Windows Python
path reached Zephyr CMake with backslashes, producing `Invalid character escape
'\\d'` in a generated CMake target. The failing full log remains under ignored
`evidence/build-20260930T041440021829Z/configure.log` on the lab host; the
relevant diagnostic is retained in `first-configure-failure.txt`. Passing
forward-slash paths to CMake fixed it.

The portable builder then passed for both profiles using the already installed
Arm GNU 14.2.1 toolchain, CMake 3.31.6, Ninja and Python 3.12.14:

| Profile | Result | Artifact SHA-256 |
| --- | --- | --- |
| FRDM-MCXN236 app 1.2.0 | Signed image and offline DFU packaging passed | `ec5d8fd392bb1b794ac14c6333c3edcb3b48998c746148e99fc828e38398e6c3` (signed image), `d600186d5330af26f95571044f163777b48714d5ac9e1bfa9c70e7862816841d` (DFU) |
| FRDM-MCXN236 MCUboot | Build passed | `d76af6e4c211151eb8b107a29e8f51c08e7b71747c66b1c2d24028e1bb6d8e1d` |

The build-specific logs and machine-readable results remain in ignored
`evidence/build-20260930T042040355891Z` and
`evidence/bootloader-20260930T042101301126Z`. These results record hashes of
local board, patch, platform and build-script sources as well as upstream
commits. No board was flashed in this
setup change. These build checks do not qualify CAN electrical timing, USB
traffic or DFU recovery on hardware. A fresh clone's network `west update`
was not exercised in this run; the manifest was validated and the pinned local
checkouts were verified instead.
