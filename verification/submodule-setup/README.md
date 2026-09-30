# Fork submodule setup — 2026-09-30

The parent `can-usb-fw` repository uses local branch `development`. Its remote
was not pushed in this change. The following public fork branches were checked
with `git ls-remote`; the original upstream repositories were not changed.

| Submodule path | Fork `development` revision |
| --- | --- |
| `.deps/zephyr/zephyr` | `684c9e8f32e4373a21098559f748f06915f950c9` |
| `.deps/cannectivity` | `61be4896de6cf96daed5dd3dd8a46de53ef43641` |

`git submodule status` showed both exact revisions. The local submodule
checkouts tracked the forks' `development` branches and had clean worktrees.
The manifest and Git links agreed. This checkout ran
`west update cmsis cmsis_6 hal_nxp mcuboot mbedtls` successfully, then
`python scripts/fw.py check` reported `Pinned clean dependency revisions
verified`. Both FRDM-MCXN236 application and MCUboot builds passed. Their
machine-readable results are retained in `app-build.json` and
`bootloader-build.json`; full logs are in the ignored `evidence/` directory on
the build host. This run did not flash or probe hardware and did not test a
fresh network clone.
