#!/usr/bin/env python3
"""Inspect stock Android boot/recovery images for an offline TWRP device tree.

Requirements: extract kernel, ramdisk, second-stage and safe fstab/init evidence;
never run the ROM, load kernel modules, flash partitions, or assume ABI support.
Ambiguities: boot image field 40, platform ABI, DTB variant and filesystem layout
must be checked against the stock image and the eventual device hardware.
Research: decode Amlogic multi-DTB, fstab, init/hw and recovery patch level.
Optimization: 128 MiB extraction caps and a small targeted cpio allowlist.
Risks: malformed gzip/newc input, symlinks, path traversal, memory exhaustion,
secret-bearing vendor files and unsupported boot header variants.
Verification: bounded boot image tests, real 2024 Stock recovery evidence and
independent Android build/USB Burning Tool import before any boot testing.
"""
from __future__ import annotations

import argparse
import json
import re
import struct
import sys
import zlib
from pathlib import Path

MAX_DECOMPRESSED = 128 * 1024 * 1024
MAX_COMPONENT = 128 * 1024 * 1024
FILE_LIMIT = 256 * 1024


def align(value: int, page: int) -> int:
    return (value + page - 1) // page * page


def extract_bytes(source, offset: int, size: int, destination: Path, length: int) -> bytes:
    if size < 0 or size > MAX_COMPONENT or offset < 0 or offset + size > length:
        raise ValueError("Boot image component is out of bounds")
    destination.parent.mkdir(parents=True, exist_ok=True)
    source.seek(offset)
    with destination.open("wb") as target:
        first = b""
        remaining = size
        while remaining:
            part = source.read(min(4 * 1024 * 1024, remaining))
            if not part:
                raise ValueError("Truncated boot component")
            if not first:
                first = part[:128]
            target.write(part)
            remaining -= len(part)
    return first


def safe_ramdisk_names(data: bytes) -> list[dict]:
    cursor = 0
    records = []
    while cursor + 110 <= len(data):
        header = data[cursor:cursor + 110]
        if header[:6] not in (b"070701", b"070702"):
            raise ValueError("Ramdisk is not a valid newc cpio stream")
        fields = [
            int(header[6 + i * 8:14 + i * 8], 16)
            for i in range(13)
        ]
        mode, payload_len, name_len = fields[1], fields[6], fields[11]
        if name_len < 2 or name_len > 4096 or payload_len > MAX_DECOMPRESSED:
            raise ValueError("Unsafe cpio header lengths")
        name_start = cursor + 110
        name_end = name_start + name_len
        if name_end > len(data) or data[name_end - 1] != 0:
            raise ValueError("Truncated cpio filename")
        name = data[name_start:name_end - 1].decode("utf-8", errors="strict")
        if name == "TRAILER!!!":
            return records
        if (name.startswith("/") or name.startswith("../") or
            any(x in ("", "..") for x in name.split("/")) or "\0" in name):
            raise ValueError("Invalid cpio entry name")
        content_start = align(name_end, 4)
        content_end = content_start + payload_len
        if content_end > len(data):
            raise ValueError("Truncated cpio payload")
        regular = (mode & 0o170000) == 0o100000
        records.append({
            "name": name,
            "mode": f"{mode:07o}",
            "size": payload_len,
            "regular": regular,
            "_content_start": content_start,
        })
        if len(records) > 100000:
            raise ValueError("Too many ramdisk records")
        cursor = align(content_end, 4)
    raise ValueError("Missing cpio trailer")


def read_ramdisk(input_path: Path, destination: Path) -> dict:
    data = input_path.read_bytes()
    if data.startswith(b"\x1f\x8b"):
        dec = zlib.decompressobj(16 + zlib.MAX_WBITS)
        body = dec.decompress(data, MAX_DECOMPRESSED + 1)
        if len(body) > MAX_DECOMPRESSED or not dec.eof or dec.unconsumed_tail:
            raise ValueError("gzip ramdisk exceeds budget or is incomplete")
        kind = "gzip-newc"
    elif data.startswith((b"070701", b"070702")):
        body, kind = data, "newc"
    else:
        return {"compression": "unknown", "magic": data[:8].hex(), "files": []}
    entries = safe_ramdisk_names(body)
    selected = []
    for row in entries:
        n = row["name"]
        basename = n.rsplit("/", 1)[-1]
        keep = (
            basename.startswith("fstab.") or basename in (
                "recovery.fstab", "twrp.fstab", "default.prop", "prop.default"
            ) or (
                n.startswith(("init", "first_stage_ramdisk/"))
                and basename.endswith(".rc")
            )
        )
        if not keep or not row["regular"] or row["size"] > FILE_LIMIT:
            continue
        # Avoid untrusted directory traversal and keep evidence under one subdir.
        dest = destination / n
        dest.parent.mkdir(parents=True, exist_ok=True)
        content = body[row["_content_start"]:row["_content_start"] + row["size"]]
        dest.write_bytes(content)
        selected.append({"name": n, "bytes": len(content)})
    manifest = [
        {"name": x["name"], "mode": x["mode"], "size": x["size"],
         "regular": x["regular"]}
        for x in entries
    ]
    return {
        "compression": kind, "file_count": len(entries),
        "evidence": selected, "manifest": manifest,
    }


def probe_android_boot(path: Path, output: Path) -> dict:
    size = path.stat().st_size
    with path.open("rb") as source:
        header = source.read(2048)
        if header[:8] != b"ANDROID!" or len(header) < 1660:
            raise ValueError("Not an Android legacy boot/recovery image")
        kernel, kernel_addr, ramdisk, ramdisk_addr, second, second_addr, tags_addr, \
            page, version, os_version = struct.unpack_from("<10I", header, 8)
        if page < 512 or page > 65536 or page & (page - 1):
            raise ValueError("Unsupported boot page size")
        if version not in (0, 1, 2):
            raise ValueError("Unsupported legacy boot image version")
        board = header[48:64].split(b"\0", 1)[0].decode("utf-8", errors="replace")
        command = (header[64:576].split(b"\0", 1)[0] +
                   header[608:1632].split(b"\0", 1)[0])
        cmdline = command.decode("utf-8", errors="replace")
        cursor = page
        kernel_head = extract_bytes(source, cursor, kernel, output / "kernel", size)
        cursor += align(kernel, page)
        ramdisk_head = b""
        if ramdisk:
            ramdisk_head = extract_bytes(source, cursor, ramdisk, output / "ramdisk", size)
        cursor += align(ramdisk, page)
        second_head = b""
        if second:
            second_head = extract_bytes(source, cursor, second, output / "second", size)
    report = {
        "boot_size": size,
        "page_size": page,
        "header_version": version,
        "os_version_field": os_version,
        "board_name": board,
        "cmdline": cmdline,
        "kernel_bytes": kernel,
        "kernel_load_addr": kernel_addr,
        "kernel_magic": kernel_head[:16].hex(),
        "ramdisk_bytes": ramdisk,
        "ramdisk_load_addr": ramdisk_addr,
        "ramdisk_magic": ramdisk_head[:16].hex(),
        "second_bytes": second,
        "second_load_addr": second_addr,
        "second_magic": second_head[:16].hex(),
        "tags_addr": tags_addr,
    }
    if ramdisk:
        report["ramdisk_tree"] = read_ramdisk(
            output / "ramdisk", output / "ramdisk-files"
        )
    return report


def probe_dtbo(path: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    data = path.read_bytes()
    if len(data) < 32:
        raise ValueError("DTBO header too small")
    magic, size, hdrsize, entrysz, count, offset, page, version = struct.unpack(
        ">8I", data[:32]
    )
    if magic != 0xd7b7ab1e or size > len(data) or hdrsize < 32:
        raise ValueError("Malformed Android DTBO table")
    if count > 128 or entrysz < 32 or offset + count * entrysz > size:
        raise ValueError("Invalid DTBO entry metadata")
    entries = []
    for i in range(count):
        start = offset + i * entrysz
        dt_size, dt_offset, board_id, rev, *_ = struct.unpack(
            ">8I", data[start:start + 32]
        )
        if dt_offset + dt_size > size:
            raise ValueError("DTBO item out of bounds")
        entry = {"index": i, "bytes": dt_size, "id": board_id, "rev": rev}
        if dt_size <= MAX_COMPONENT and data[dt_offset:dt_offset + 4] == b"\xd0\x0d\xfe\xed":
            name = f"dtbo-{i}.dtb"
            (output / name).write_bytes(data[dt_offset:dt_offset + dt_size])
            entry["file"] = name
        entries.append(entry)
    return {"dtbo_table": True, "total_size": size, "page": page,
            "version": version, "entries": entries}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("directory", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    try:
        a.output.mkdir(parents=True, exist_ok=True)
        report = {}
        for name in ("boot", "recovery"):
            file = a.directory / f"{name}.img"
            if file.exists():
                report[name] = probe_android_boot(file, a.output / name)
        dtbo = a.directory / "dtbo.img"
        if dtbo.exists():
            report["dtbo"] = probe_dtbo(dtbo, a.output / "dtbo")
        (a.output / "boot-analysis.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        overview = {name: {
            "page_size": x.get("page_size"),
            "header_version": x.get("header_version"),
            "board_name": x.get("board_name"),
            "ramdisk_bytes": x.get("ramdisk_bytes"),
            "ramdisk_compression": x.get("ramdisk_tree", {}).get("compression"),
            "ramdisk_file_count": x.get("ramdisk_tree", {}).get("file_count"),
            "fstab": [a["name"] for a in x.get("ramdisk_tree", {}).get("evidence", [])
                      if "fstab" in a["name"]],
        } for name, x in report.items()}
        print(json.dumps(overview, ensure_ascii=False))
    except (ValueError, OSError, UnicodeError) as exc:
        print(f"Android boot inspection failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
