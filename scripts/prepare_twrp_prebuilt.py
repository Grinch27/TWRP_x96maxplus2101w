#!/usr/bin/env python3
"""Create pinned, non-committed recovery prebuilts from the 2024 ROM evidence.

Requirements: derive kernel, Amlogic second-stage, and DTBO only from the
already archived original X96 MAX+ 2101W 2024 stock factory package.
Ambiguities: exact partition capacity, ABI, DTB board chosen at boot remain
unverified. A valid extraction is not a build- or device-boot success.
Research: confirm Android header v1, U-Boot selected dtb, CPU userspace ABI,
screen, USB gadget and FDE/FBE before preparing a flashable release.
Risks: wrong-board assets, missing recovery overlay, large injected files,
confusing original-boot kernel with another vendor source.
Verification: compare both stock boot and recovery kernel, verify identical
multi-DTB second stages, cross-check DTBO bytes and trusted metadata, enforce
source run identity and hard maximum lengths. Never flash or publish TWRP.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

# The inspection run ID is recorded by the workflow, not hard-coded.
SOURCE_RELEASE = "firmware-2101w-stock-20240508-42466511950-1"
MAX_BYTES = {"kernel": 64 * 1024 * 1024, "second": 2 * 1024 * 1024,
             "dtbo.img": 1024 * 1024}
KNOWN_BOARD = ["sm1", "ac213", "4g"]
STOCK_SIZE = {"boot": 10_037_248, "recovery": 16_728_064,
              "dtbo": 438, "_aml_dtb": 85_773}


def require(path: Path, length: int) -> bytes:
    if not path.is_file() or path.is_symlink() or path.stat().st_size != length:
        raise ValueError(f"Missing or different stock evidence: {path.name}")
    return path.read_bytes()


def prepare(source: Path, output: Path, inspection_run: str) -> dict:
    meta_path = source / "boot-metadata" / "boot-analysis.json"
    items_path = source / "rom-inventory.json"
    if not meta_path.is_file() or not items_path.is_file():
        raise ValueError("Missing original stock analysis JSON")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    inventory = json.loads(items_path.read_text(encoding="utf-8"))
    items = {
        (item["main"], item["sub"]): item
        for item in inventory.get("items", [])
    }
    for key, size in STOCK_SIZE.items():
        row = items.get(("PARTITION", key))
        if not row or row["length"] != size:
            raise ValueError(f"Original ROM's {key} record differs")
    for name in ("boot", "recovery"):
        fields = meta.get(name, {})
        if (fields.get("header_version") != 1 or fields.get("page_size") != 2048
                or fields.get("kernel_bytes") != 9_947_616
                or fields.get("kernel_load_addr") != 0x01080000
                or fields.get("ramdisk_load_addr") != 0x01000000
                or fields.get("second_load_addr") != 0x00F00000
                or fields.get("second_bytes") != 85_773
                or fields.get("tags_addr") != 0x100):
            raise ValueError(f"{name} header does not match pinned stock geometry")
    if meta["boot"]["ramdisk_bytes"] != 0:
        raise ValueError("Unexpected stock boot ramdisk")
    if meta["recovery"]["ramdisk_bytes"] != 6_687_486:
        raise ValueError("Unexpected stock recovery ramdisk size")

    boards = meta.get("_aml_dtb", {}).get("entries", [])
    if (len(boards) != 4 or KNOWN_BOARD not in
            [entry.get("tokens") for entry in boards]):
        raise ValueError("Missing original sm1/ac213/4g board in the multi-DTB")
    if meta.get("meson1", {}).get("entries") != boards:
        raise ValueError("The stock DTB references disagree")

    kernel = require(source / "boot-metadata" / "recovery" / "kernel", 9_947_616)
    if kernel != require(source / "boot-metadata" / "boot" / "kernel", 9_947_616):
        raise ValueError("Stock boot and recovery use different kernels")
    second = require(source / "boot-metadata" / "recovery" / "second", 85_773)
    if second != require(source / "_aml_dtb.img", 85_773):
        raise ValueError("Stock recovery second-stage and _aml_dtb disagree")
    dtbo = require(source / "dtbo.img", 438)
    if meta.get("recovery", {}).get("recovery_dtbo_bytes") != len(dtbo):
        raise ValueError("Recovery Header v1 does not embed the expected DTBO")
    overlay = require(
        source / "boot-metadata" / "recovery" / "recovery_dtbo.img", len(dtbo)
    )
    if overlay != dtbo:
        raise ValueError("Recovery DTBO section differs from stock dtbo partition")

    if output.resolve() == source.resolve() or source.resolve() in output.resolve().parents:
        raise ValueError("Refusing to overwrite evidence/source tree")
    output.mkdir(parents=True, exist_ok=True)
    outputs = {"kernel": kernel, "second": second, "dtbo.img": dtbo}
    for name, payload in outputs.items():
        if not 0 < len(payload) <= MAX_BYTES[name]:
            raise ValueError("Invalid prebuilt input size")
        target = output / name
        if target.exists():
            raise ValueError("Refusing to overwrite existing prebuilt file")
        target.write_bytes(payload)
    report = {
        "source_release": SOURCE_RELEASE,
        "source_inspection_run": inspection_run,
        "boot_header_version": 1,
        "board_candidate": "_".join(KNOWN_BOARD),
        "recovery_partition_size": "NOT VERIFIED",
        "userspace_abi": "NOT VERIFIED; provisional 32-bit build config",
        "prebuilts": {name: len(value) for name, value in outputs.items()},
        "status": "offline source preparation only; not boot validated",
    }
    (output / "provenance.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("inspection_artifact_dir", type=Path)
    parser.add_argument("prebuilt_output_dir", type=Path)
    parser.add_argument("--inspection-run", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(prepare(
            args.inspection_artifact_dir.resolve(),
            args.prebuilt_output_dir.resolve(), args.inspection_run
        ), indent=2))
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"Refusing to prepare TWRP prebuilts: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
