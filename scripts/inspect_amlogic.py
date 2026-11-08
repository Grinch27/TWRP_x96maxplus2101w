#!/usr/bin/env python3
"""Inspect an Amlogic USB Burning Tool ROM without running firmware code.

Requirements: parse all bounded package records; extract only recognized, small
Android boot/recovery/DTB partition items for the 2101W offline device tree.
Ambiguities: product identity, Amlogic header variants, DTB overlays, dynamic
partitions, encryption/FBE and real mount layout require independent inspection.
Research: cross-check against Amlogic amlImage_if.h, full stock recovery ramdisk,
DTB and board flash layout before constructing a flashable TWRP image.
Optimization: read only header/item table, stream a small allowlist of partitions.
Risks: malicious offsets/names, incomplete upstream package, proprietary data,
hardware incompatibility and an incomplete boot image header interpretation.
Verification: synthetic v1/v2 header fixtures, range/name checks, real stock
inventory, extracted boot/recovery magic and Android build tests; no flash.
"""
from __future__ import annotations

import argparse
import json
import re
import struct
import sys
from pathlib import Path

MAGIC = 0x27B51956
HEADER = struct.Struct("<IIIQII36s")
ITEM_FORMATS = {
    1: struct.Struct("<IIQQQ32s32s32s"),
    2: struct.Struct("<IIQQQ256s256s32s"),
}
ALLOW_EXTRACT = {"boot", "recovery", "dtb", "dtbo", "vendor_boot", "vbmeta"}
MAX_SELECTED = 128 * 1024 * 1024
MAX_ITEMS = 1024


def text_field(value: bytes) -> str:
    raw = value.split(b"\0", 1)[0]
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValueError("Non-ASCII item name in firmware") from exc
    if not text or not re.fullmatch(r"[a-zA-Z0-9_.+-]{1,128}", text):
        raise ValueError("Unexpected item name in firmware package")
    return text


def inventory(image: Path) -> list[dict]:
    length = image.stat().st_size
    with image.open("rb") as inp:
        hdr = inp.read(HEADER.size)
        if len(hdr) != HEADER.size:
            raise ValueError("Truncated image header")
        _, version, magic, declared, align, count, _ = HEADER.unpack(hdr)
        if magic != MAGIC or version not in ITEM_FORMATS or declared != length:
            raise ValueError("Amlogic package header invalid")
        if not 1 <= count <= MAX_ITEMS or not 1 <= align <= 65536:
            raise ValueError("Invalid item count or alignment")
        rec = ITEM_FORMATS[version]
        data_start = HEADER.size + rec.size * count
        if data_start >= length:
            raise ValueError("Package has no space for items")
        rows = []
        spans = []
        for position in range(count):
            data = inp.read(rec.size)
            if len(data) != rec.size:
                raise ValueError("Truncated item table")
            item_id, file_type, cursor, offset, size, main, sub, _ = rec.unpack(data)
            major, minor = text_field(main), text_field(sub)
            if (size == 0 or offset < data_start or offset + size > length
                    or cursor > size):
                raise ValueError(f"Invalid item span at table index {position}")
            if file_type not in (0, 0xFE):
                raise ValueError(f"Unsupported item type at table index {position}")
            spans.append((offset, offset + size))
            rows.append({
                "index": position,
                "item_id": item_id,
                "type": "sparse" if file_type == 0xFE else "normal",
                "main": major,
                "sub": minor,
                "offset": offset,
                "length": size,
            })
        ordered = sorted(rows, key=lambda item: item["offset"])
        for previous, current in zip(ordered, ordered[1:]):
            if previous["offset"] + previous["length"] > current["offset"]:
                raise ValueError(
                    "Overlapping firmware payload items: "
                    f"{previous['main']}/{previous['sub']} "
                    f"[{previous['offset']}, {previous['offset'] + previous['length']}) "
                    f"and {current['main']}/{current['sub']} "
                    f"[{current['offset']}, {current['offset'] + current['length']})"
                )
        if len(set((x["main"], x["sub"]) for x in rows)) != len(rows):
            raise ValueError("Duplicate firmware item main/subtype")
    return rows


def android_boot_probe(header: bytes) -> dict:
    if header.startswith(b"ANDROID!") and len(header) >= 48:
        return {
            "format": "android_boot_image",
            "kernel_bytes": struct.unpack_from("<I", header, 8)[0],
            "ramdisk_bytes": struct.unpack_from("<I", header, 16)[0],
            "second_bytes": struct.unpack_from("<I", header, 24)[0],
            "page_bytes": struct.unpack_from("<I", header, 36)[0],
            "field40_raw": struct.unpack_from("<I", header, 40)[0],
            "note": "Header field 40 is ambiguous between legacy dt_size and header_version",
        }
    if header.startswith(bytes.fromhex("d7b7ab1e")):
        return {"format": "android_sparse_ext4_candidate"}
    if header.startswith(b"\xd0\x0d\xfe\xed"):
        return {"format": "flattened_device_tree"}
    return {"format": "unclassified", "first_eight_bytes_hex": header[:8].hex()}


def inspect(image: Path, output: Path) -> dict:
    records = inventory(image)
    output.mkdir(parents=True, exist_ok=True)
    extracted = []
    allowed = {name: None for name in ALLOW_EXTRACT}
    with image.open("rb") as source:
        for item in records:
            name = item["sub"].lower()
            if name not in allowed or item["main"].upper() not in ("PARTITION", "IMAGE"):
                continue
            if allowed[name] is not None:
                raise ValueError(f"Multiple candidate {name} images")
            if item["length"] > MAX_SELECTED:
                raise ValueError(f"Refusing to extract oversized {name} item")
            target = output / f"{name}.img"
            source.seek(item["offset"])
            first = source.read(min(4096, item["length"]))
            if len(first) < min(4096, item["length"]):
                raise ValueError("Truncated image section")
            source.seek(item["offset"])
            remaining = item["length"]
            with target.open("wb") as dest:
                while remaining:
                    data = source.read(min(4 * 1024 * 1024, remaining))
                    if not data:
                        raise ValueError("Truncated image section")
                    dest.write(data)
                    remaining -= len(data)
            allowed[name] = item["index"]
            extracted.append({
                "partition": name, "length": item["length"],
                "filename": target.name, "item_index": item["index"],
                **android_boot_probe(first),
            })
    result = {
        "source": "2024 2101W stock candidate (archived upstream ROM)",
        "caveat": (
            "Static extraction only; do not flash or infer FBE/partition topology "
            "without direct recovery ramdisk/fstab/DTB checks."
        ),
        "package_bytes": image.stat().st_size,
        "items": records,
        "extracted": extracted,
        "missing": sorted(k for k, v in allowed.items() if v is None),
    }
    (output / "rom-inventory.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return result


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("image", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    try:
        report = inspect(a.image, a.output)
    except (ValueError, OSError) as exc:
        print(f"Inspection rejected: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(
        {"items": len(report["items"]), "extracted": report["extracted"],
         "missing": report["missing"]}, ensure_ascii=False
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
