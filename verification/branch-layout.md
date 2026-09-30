# Fork branch layout — 2026-09-30

The public `Swamy-BV/zephyr` and `Swamy-BV/cannectivity` forks now use
`develop` as their GitHub default branch. `develop` was created at each fork's
current `main` tip; the older `development` refs were removed. The original
upstream repositories were not changed.

| Fork | `main` and `develop` commit | Firmware Git link |
| --- | --- | --- |
| Zephyr | `fa4f8fb0e470210aee0ae6fb069a281bc6ac887a` | `684c9e8f32e4373a21098559f748f06915f950c9` (4.4.0) |
| CANnectivity | `93eb616f21e270200846ffc20d128c57fdbe5dab` | `878670becbf0a63d8353b2a8516995c560460bca` (Zephyr 4.4 compatible ancestor) |

The firmware branch was renamed locally from `development` to `develop`.
It was not pushed. `.gitmodules` now selects fork `develop` for intentional
future updates, while the Git links and `west.yml` keep the then-tested build on
the older commits. At that point no firmware build was claimed for newer tips.
`git ls-remote --symref` verified the two fork defaults and equal branch tips;
`git submodule status`, `python scripts/fw.py check` and
`west manifest --validate` passed for the unchanged firmware pins.

Later on 2026-09-30, the Zephyr fork was 248 commits behind upstream `main`.
Its `main` and `develop` were fast-forwarded together from `294c03cd64e69e914e943867bbabc703447df8ff`
to `fa4f8fb0e470210aee0ae6fb069a281bc6ac887a` (Zephyr 4.5.0-rc1).
The local `develop` branch now tracks that tip; the checked-out submodule and
firmware Git link remain at the tested 4.4.0 commit. The revision check still
passes. This sync did not rebuild or flash the newer Zephyr revision.

Later on 2026-09-30, the firmware CANnectivity Git link and `west.yml` advanced
to `878670b`, an ancestor of the fork's `develop` branch. This is the last
commit before `c2a4b7f` removed the legacy USB stack. The board config
explicitly selects that stack. The current `develop` tip is 65 commits ahead
and does not build against pinned Zephyr 4.4.0: its app and `gs_usb` callbacks
use newer USB API signatures. Failed build logs are retained in
`evidence/build-20260930T192724498855Z`,
`evidence/build-20260930T193011167658Z`, and
`evidence/build-20260930T193133347642Z`. The compatible app and bootloader
builds passed; see `verification/cannectivity-develop-20260930.json`. No new
image was flashed or physically qualified.
