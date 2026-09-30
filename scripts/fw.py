"""Portable firmware preparation and build; dependency fetching belongs to west."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone

import yaml


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "west.yml"
SUBMODULES = {"zephyr", "cannectivity"}
LAB_VID = 0x1FC9
LAB_PID = 0x00A2


def run(*args, cwd=None, env=None, capture=False):
    command = [str(arg) for arg in args]
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=capture,
        check=False,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout or "").strip() if capture else ""
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(command)} {detail}")
    return result.stdout.strip() if capture else ""


def projects():
    manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))["manifest"]
    return {entry["name"]: entry for entry in manifest["projects"]}


def check_revisions(entries):
    for name, entry in entries.items():
        checkout = ROOT / entry["path"]
        if not (checkout / ".git").exists():
            command = "git submodule update --init" if name in SUBMODULES else f"west update {name}"
            raise RuntimeError(f"Missing {name}: run '{command}' from the firmware root")
        actual = run("git", "rev-parse", "HEAD", cwd=checkout, capture=True)
        if actual != entry["revision"]:
            raise RuntimeError(f"{name} is at {actual}; expected {entry['revision']}.")
        dirty = run("git", "status", "--porcelain", cwd=checkout, capture=True)
        if dirty:
            raise RuntimeError(f"Unexpected edits in pinned dependency {name}: {dirty}")
        if name in SUBMODULES:
            gitlink = run("git", "rev-parse", f":{entry['path']}", cwd=ROOT, capture=True)
            if gitlink != entry["revision"]:
                raise RuntimeError(f"{name} submodule pointer {gitlink} differs from west.yml")
            section = f"submodule.{entry['path']}"
            url = run("git", "config", "-f", ROOT / ".gitmodules", "--get", f"{section}.url",
                      cwd=ROOT, capture=True)
            branch = run("git", "config", "-f", ROOT / ".gitmodules", "--get",
                         f"{section}.branch", cwd=ROOT, capture=True)
            if url != entry["url"] or branch != "develop":
                raise RuntimeError(f"{name} submodule must track the develop branch of the fork")


def prepare():
    entries = projects()
    check_revisions(entries)
    return entries


def tool(name, selected=None):
    found = str(Path(selected).expanduser().resolve()) if selected else shutil.which(name)
    if not found or not Path(found).is_file():
        raise RuntimeError(f"{name} is required on PATH")
    return found


def signing_key(value):
    key = Path(value).expanduser().resolve() if value else ROOT / ".deps/dfu-development.pem"
    if not key.is_file():
        raise RuntimeError(f"MCUboot signing key is missing: {key}")
    return key


def compiler_root(value):
    selected = value or os.environ.get("GNUARMEMB_TOOLCHAIN_PATH")
    if not selected:
        raise RuntimeError("Set GNUARMEMB_TOOLCHAIN_PATH or pass --toolchain")
    root = Path(selected).expanduser().resolve()
    compiler = root / "bin" / ("arm-none-eabi-gcc.exe" if os.name == "nt" else "arm-none-eabi-gcc")
    if not compiler.is_file():
        raise RuntimeError(f"Arm GNU compiler is missing: {compiler}")
    return root, compiler


def modules(entries):
    names = ("cmsis", "cmsis_6", "hal_nxp", "mcuboot", "mbedtls", "cannectivity")
    return [ROOT / entries[name]["path"] for name in names] + [ROOT / "platform/mcxn236_control"]


def identity_file(path, key, version, bootloader):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"CONFIG_USB_DEVICE_VID=0x{LAB_VID:04X}",
        f"CONFIG_USB_DEVICE_PID=0x{LAB_PID:04X}",
        f"CONFIG_USB_DEVICE_DFU_PID=0x{LAB_PID:04X}",
    ]
    if bootloader:
        lines.append(f'CONFIG_BOOT_SIGNATURE_KEY_FILE="{key.as_posix()}"')
    else:
        lines += [
            f"CONFIG_CANNECTIVITY_USB_VID=0x{LAB_VID:04X}",
            f"CONFIG_CANNECTIVITY_USB_PID=0x{LAB_PID:04X}",
            f'CONFIG_MCUBOOT_SIGNATURE_KEY_FILE="{key.as_posix()}"',
            f'CONFIG_MCUBOOT_IMGTOOL_SIGN_VERSION="{version}"',
        ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def project_source_hashes():
    files = [ROOT / "west.yml", ROOT / ".gitmodules"]
    for directory in ("board", "platform", "scripts"):
        files.extend(path for path in (ROOT / directory).rglob("*") if path.is_file())
    return {
        path.relative_to(ROOT).as_posix(): sha256(path)
        for path in sorted(files)
        if "__pycache__" not in path.parts and path.suffix != ".pyc"
    }


def build(args):
    if sys.version_info < (3, 12):
        raise RuntimeError("Python 3.12 or newer is required")
    if not re.fullmatch(r"\d+\.\d+\.\d+", args.version):
        raise RuntimeError("--version must be numeric major.minor.patch")
    entries = prepare()
    cmake, ninja = tool("cmake", args.cmake), tool("ninja", args.ninja)
    toolchain, compiler = compiler_root(args.toolchain)
    key = signing_key(args.key)
    bootloader = args.command == "bootloader"
    target = ROOT / "build/standalone" / (
        "mcuboot-frdm_mcxn236" if bootloader else "frdm_mcxn236"
    )
    evidence = ROOT / "evidence" / (
        ("bootloader-" if bootloader else "build-")
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    )
    target.mkdir(parents=True, exist_ok=True)
    evidence.mkdir(parents=True, exist_ok=True)
    identity = ROOT / "build" / ("bootloader-identity.conf" if bootloader else "identity.conf")
    identity_file(identity, key, args.version, bootloader)
    zephyr = ROOT / entries["zephyr"]["path"]
    source = (
        ROOT / entries["mcuboot"]["path"] / "boot/zephyr"
        if bootloader
        else ROOT / entries["cannectivity"]["path"] / "app"
    )
    conf = [ROOT / "board/mcuboot-bootloader.conf", identity] if bootloader else [
        ROOT / "board/frdm_mcxn236.conf", ROOT / "board/mcuboot.conf", identity
    ]
    overlays = [ROOT / "board/partitions.overlay"]
    if not bootloader:
        overlays.append(ROOT / "board/two-channel.overlay")
    environment = os.environ.copy()
    environment.update({
        "ZEPHYR_BASE": zephyr.as_posix(),
        "ZEPHYR_TOOLCHAIN_VARIANT": "gnuarmemb",
        "GNUARMEMB_TOOLCHAIN_PATH": toolchain.as_posix(),
    })
    environment["PATH"] = os.pathsep.join((
        str(Path(sys.executable).parent), str(Path(ninja).parent), environment["PATH"]
    ))
    options = [
        f"-DPython3_EXECUTABLE={Path(sys.executable).as_posix()}",
        f"-DZEPHYR_MODULES={';'.join(item.as_posix() for item in modules(entries))}",
        f"-DEXTRA_CONF_FILE={';'.join(item.as_posix() for item in conf)}",
        f"-DEXTRA_DTC_OVERLAY_FILE={';'.join(item.as_posix() for item in overlays)}",
        "-DBOARD=frdm_mcxn236",
    ]
    if bootloader:
        options.insert(0, "-UCONFIG_BOOT_SIGNATURE_KEY_FILE")
    result = {
        "status": "failed",
        "profile": "mcuboot-frdm-mcxn236" if bootloader else "cannectivity-frdm-mcxn236",
        "version": args.version,
        "board": "frdm_mcxn236",
        "lab_vid_pid": "1FC9:00A2",
        "toolchain": str(compiler),
        "revisions": {name: entry["revision"] for name, entry in entries.items()},
        "source_hashes": project_source_hashes(),
        "physical_can_qualified": False,
    }
    try:
        for label, command in (
            ("configure", [cmake, "-S", source, "-B", target, "-G", "Ninja", *options]),
            ("build", [cmake, "--build", target]),
        ):
            with (evidence / f"{label}.log").open("w", encoding="utf-8") as log:
                completed = subprocess.run(
                    [str(part) for part in command], env=environment,
                    stdout=log, stderr=subprocess.STDOUT, check=False,
                )
            if completed.returncode:
                raise RuntimeError(f"{label} failed; see {evidence / (label + '.log')}")
            if label == "configure":
                cache = (target / "CMakeCache.txt").read_text(encoding="utf-8", errors="replace")
                match = re.search(r"^CMAKE_C_COMPILER:(?:FILEPATH|STRING)=(.+)$", cache, re.MULTILINE)
                if not match or Path(match.group(1).strip()).resolve() != compiler:
                    raise RuntimeError("CMake cache uses a different compiler; use a fresh build directory")
        if bootloader:
            result["bootloader_sha256"] = sha256(target / "zephyr/zephyr.bin")
            result["flashed_to_board"] = False
        else:
            signed = target / "zephyr/zephyr.signed.bin"
            package = target / "zephyr/can-usb.dfu"
            with (evidence / "package.json").open("w", encoding="utf-8") as log:
                completed = subprocess.run(
                    [sys.executable, str(ROOT / "scripts/package-dfu.py"),
                     str(signed), str(key),
                     str(ROOT / entries["mcuboot"]["path"] / "scripts"),
                     str(package), "--vid", str(LAB_VID), "--pid", str(LAB_PID)],
                    stdout=log, stderr=subprocess.STDOUT, check=False,
                )
            if completed.returncode:
                raise RuntimeError(f"DFU packaging failed; see {evidence / 'package.json'}")
            result.update({
                "signed_sha256": sha256(signed),
                "dfu_sha256": sha256(package),
                "actual_channels": 2,
                "qualified_external_channels": 0,
            })
        result["status"] = "build-passed"
    except Exception as error:
        result["error"] = str(error)
        raise
    finally:
        (evidence / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(f"Evidence: {evidence}")
    print(f"Build: {target}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("check", help="verify pinned clean dependency checkouts")
    subcommands.add_parser("prepare", help="verify pinned clean dependency checkouts")
    for name in ("app", "bootloader"):
        command = subcommands.add_parser(name, help=f"build {name} without downloading dependencies")
        command.add_argument("--toolchain", help="Arm GNU toolchain root")
        command.add_argument("--cmake", help="CMake executable when not on PATH")
        command.add_argument("--ninja", help="Ninja executable when not on PATH")
        command.add_argument("--key", help="MCUboot signing key path")
        command.add_argument("--version", default="1.2.0", help="application image version")
    args = parser.parse_args()
    try:
        if args.command in ("check", "prepare"):
            prepare()
            print("Pinned clean dependency revisions verified")
        else:
            build(args)
    except Exception as error:
        parser.exit(1, f"error: {error}\n")


if __name__ == "__main__":
    main()
