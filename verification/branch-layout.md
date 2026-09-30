# Fork branch layout — 2026-09-30

The public `Swamy-BV/zephyr` and `Swamy-BV/cannectivity` forks now use
`develop` as their GitHub default branch. `develop` was created at each fork's
current `main` tip; the older `development` refs were removed. The original
upstream repositories were not changed.

| Fork | `main` and `develop` commit | Firmware Git link |
| --- | --- | --- |
| Zephyr | `294c03cd64e69e914e943867bbabc703447df8ff` | `684c9e8f32e4373a21098559f748f06915f950c9` (4.4.0) |
| CANnectivity | `93eb616f21e270200846ffc20d128c57fdbe5dab` | `61be4896de6cf96daed5dd3dd8a46de53ef43641` (1.3.0) |

The firmware branch was renamed locally from `development` to `develop`.
It was not pushed. `.gitmodules` now selects fork `develop` for intentional
future updates, while the Git links and `west.yml` keep the tested build on
the older commits. No firmware build was claimed for the newer fork tips.
`git ls-remote --symref` verified the two fork defaults and equal branch tips;
`git submodule status`, `python scripts/fw.py check` and
`west manifest --validate` passed for the unchanged firmware pins.
