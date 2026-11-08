#!/usr/bin/env python3
"""Validate a non-published native TWRP 9.0 recovery candidate.

Requirements: nonzero actual-built Android v1 recovery image, stock kernel and
second-stage bytes, original 438-byte recovery DTBO, original load addresses,
and strict 16 MiB provisional ceiling. USB HID must be checked at source level.
Ambiguities: true eMMC recovery partition size, SoC DTB runtime selection,
HDMI and USB host behavior, encryption, and boot success remain unverified.
Research: inspect original U-Boot partition table and obtain device logs only
after separately authorized hardware tests.
Risks: a statically valid image can brick a mismatched board if flashed.
Verification: compare source ROM-derived prebuilts bytewise, reject malformed
images and publish no Release. Do not make claims of a successful device boot.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from analyze_android_boot import probe_android_boot

DEVICE = "x96maxplus2101w"
MAX_PROVISIONAL_SIZE = 16 * 1024 * 1024
EXPECT = {
    "header_version": 1,
    "page_size": 2048,
    "kernel_load_addr": 0x01080000,
    "ramdisk_load_addr": 0x01000000,
    "second_load_addr": 0x00F00000,
    "tags_addr": 0x100,
    "kernel_bytes": 9_947_616,
    "second_bytes": 85_773,
    "recovery_dtbo_bytes": 438,
    "header_size": 1648,
}


def validate(image: Path, prebuilts: Path, output: Path) -> dict:
    if not image.is_file() or image.is_symlink():
        raise ValueError("No genuine built recovery image found")
    size = image.stat().st_size
    if not 1_000_000 <= size <= MAX_PROVISIONAL_SIZE:
        raise ValueError(
            f"Image {size} exceeds provisional 16 MiB limit or is implausibly small"
        )
    output.mkdir(parents=True, exist_ok=True)
    report = probe_android_boot(image, output / "unpacked")
    for key, expected in EXPECT.items():
        if report.get(key) != expected:
            raise ValueError(f"{key}: expected {expected!r}, got {report.get(key)!r}")
    if report.get("ramdisk_bytes", 0) == 0:
        raise ValueError("Built TWRP ramdisk is absent")
    required = {
        "kernel": ("kernel", EXPECT["kernel_bytes"]),
        "second": ("second", EXPECT["second_bytes"]),
        "dtbo.img": ("recovery_dtbo.img", EXPECT["recovery_dtbo_bytes"]),
    }
    for expected_name, (built_name, nbytes) in required.items():
        original = prebuilts / expected_name
        extracted = output / "unpacked" / built_name
        if (not original.is_file() or not extracted.is_file()
                or original.is_symlink() or extracted.is_symlink()
                or original.stat().st_size != nbytes
                or extracted.stat().st_size != nbytes
                or original.read_bytes() != extracted.read_bytes()):
            raise ValueError(f"Built {built_name} differs from pinned original ROM")

    result = {
        "device": DEVICE,
        "result": "static_candidate_only",
        "image_bytes": size,
        "partition_capacity": "unknown (16 MiB provisional build ceiling)",
        "kernel_and_dtbo_stock_equivalent": True,
        "header": {
            key: report[key] for key in (*EXPECT, "ramdisk_bytes", "cmdline")
        },
        "usb_keyboard_mouse": "upstream evdev source verified, runtime untested",
        "ir_remote": "not required; no remotecfg dependency added",
        "release": "disabled",
        "device_flash": "not authorized, not performed",
        "limitations": [
            "Actual recovery partition capacity not measured",
            "HDMI/framebuffer and USB HID hardware not tested",
            "FDE/FBE and backup/restore not tested",
            "No Android device has booted this candidate",
        ],
    }
    (output / "static-validation.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate", type=Path)
    parser.add_argument("stock_prebuilts", type=Path)
    parser.add_argument("validation_output", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(validate(
            args.candidate.resolve(),
            args.stock_prebuilts.resolve(),
            args.validation_output.resolve(),
        ), indent=2))
        return 0
    except (ValueError, OSError, KeyError) as exc:
        print(f"Native TWRP candidate rejected: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
