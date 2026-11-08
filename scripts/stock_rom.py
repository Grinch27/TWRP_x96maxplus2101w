#!/usr/bin/env python3
"""Acquire and validate archived Amlogic USB Burning Tool firmware images.

Requirements: preserve exact upstream archive bytes; fail closed on unknown source
or missing full .img; publish only after structural validation.
Ambiguities: the 2022 2101W image lacks a verified direct public download; board
compatibility and original-vendor redistribution permission remain unverified.
Research: confirm PCB/eMMC, original bootloader and full USB Burning Tool import.
Optimization: signed Yandex links are renewed per retry; Range-resume is bounded.
Risks: unknown upstream archive, interrupted download, unsafe archive names,
large Release assets, non-flashable or wrong-board image.
Verification: run unittest fixtures, provider metadata, archive integrity test,
image header/item count and byte-length checks; no real-device flash is performed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

PUBLIC_API = "https://cloud-api.yandex.net/v1/disk/public/resources"
MAX_ASSET_BYTES = 1_900_000_000
MIN_IMAGE_BYTES = 4 * 1024 * 1024
MAX_UPSTREAM_BYTES = 10 * 1024 * 1024 * 1024
MAGICS = {0x27B51956: "Amlogic legacy", 0x6CF66ED9: "Amlogic v2"}
SOURCE_POST = "https://slimboxtv.ru/x96max-plus/"

# Never silently infer a URL or equivalence from the similarly named 2101.
CATALOG = {
    "2101w-stock-20240508": {
        "filename": "X96Max_Plus_2101W_20240508-1103.7z",
        "share": "https://disk.yandex.ru/d/EiPGAs73ml2wLQ",
        "device": "X96 MAX+ 2101W",
        "class": "stock_candidate",
        "source_post": SOURCE_POST,
        "version": "20240508-1103",
    },
    "2101w-stock-20220525": {
        "filename": "X96max_plus_2101w_20220525-1404",
        "share": None,
        "device": "X96 MAX+ 2101W",
        "class": "stock_candidate",
        "source_post": "https://4pda.to/forum/index.php?showtopic=1013103&st=13260",
        "version": "20220525-1404",
    },
    "2101-stock-20220525": {
        "filename": "X96MaxPlus_2101_20220525-1725",
        "share": None,
        "device": "X96 MAX+ 2101 (NOT 2101W)",
        "class": "other_board_stock",
        "source_post": "https://4pda.to/forum/index.php?showtopic=1013103&st=10120",
        "version": "20220525-1725",
    },
    "2101w-slimbox-aosp": {
        "filename": "sbx_x96max_plus_2101w_aosp_9_20.zip",
        "share": "https://disk.yandex.ru/d/hGbDgwMQjO8BDQ",
        "device": "X96 MAX+ 2101W",
        "class": "third_party_slimbox",
        "source_post": SOURCE_POST,
        "version": "slimBOXtv-9.20-aosp",
    },
    "2101w-slimbox-atv": {
        "filename": "sbx_x96max_plus_2101w_atv_9_20.zip",
        "share": "https://disk.yandex.ru/d/hGbDgwMQjO8BDQ",
        "device": "X96 MAX+ 2101W",
        "class": "third_party_slimbox",
        "source_post": SOURCE_POST,
        "version": "slimBOXtv-9.20-atv",
    },
}


def request_json(url: str, params: dict[str, str]) -> dict:
    target = url + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(
        target, headers={"User-Agent": "X96-2101W-stock-archiver/1.0"}
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError("Provider API did not return a JSON object")
    return payload


def resolve_yandex(item: dict) -> tuple[str, int, str]:
    share = item["share"]
    if share is None:
        raise ValueError(
            "No verified public download URL for this entry. "
            "Do not substitute a different board or custom firmware."
        )
    meta = request_json(PUBLIC_API, {"public_key": share, "limit": "1000"})
    expected_name = item["filename"]
    if meta.get("type") == "file":
        if meta.get("name") != expected_name:
            raise ValueError("Upstream filename does not match the selected firmware")
        selected = meta
        subpath = None
    elif meta.get("type") == "dir":
        entries = meta.get("_embedded", {}).get("items", [])
        matches = [
            value for value in entries
            if value.get("type") == "file" and value.get("name") == expected_name
        ]
        if len(matches) != 1:
            raise ValueError(
                "The public folder does not have exactly one matching firmware file"
            )
        selected = matches[0]
        subpath = selected.get("path")
        if not isinstance(subpath, str) or not subpath:
            raise ValueError("Yandex did not provide a resource path")
    else:
        raise ValueError("Unsupported or inaccessible public resource")
    length = selected.get("size")
    if type(length) is not int or not 100_000_000 <= length <= MAX_UPSTREAM_BYTES:
        raise ValueError("Unreasonable or missing provider size")
    return share, length, subpath or ""


def signed_download_url(share: str, path: str) -> str:
    params = {"public_key": share}
    if path:
        params["path"] = path
    result = request_json(PUBLIC_API + "/download", params)
    href = result.get("href")
    if not isinstance(href, str) or not href.startswith("https://"):
        raise ValueError("No HTTPS download link from provider")
    return href


def fetch_with_resume(share: str, path: str, length: int, destination: Path) -> None:
    partial = destination.with_name(destination.name + ".part")
    for attempt in range(12):
        current = partial.stat().st_size if partial.exists() else 0
        if current == length:
            partial.replace(destination)
            return
        if current > length:
            raise ValueError("Partial file exceeds provider-declared file size")
        headers = {"User-Agent": "X96-2101W-stock-archiver/1.0"}
        if current:
            headers["Range"] = f"bytes={current}-"
        try:
            href = signed_download_url(share, path)
            with urllib.request.urlopen(
                urllib.request.Request(href, headers=headers), timeout=120
            ) as response:
                status = response.status
                if current and status != 206:
                    raise ValueError("Provider ignored Range on interrupted download")
                if current:
                    header = response.headers.get("Content-Range", "")
                    if not header.startswith(f"bytes {current}-"):
                        raise ValueError("Provider returned an unexpected byte range")
                if status not in (200, 206):
                    raise ValueError(f"Unexpected HTTP status {status}")
                with partial.open("ab" if current else "wb") as output:
                    while True:
                        chunk = response.read(4 * 1024 * 1024)
                        if not chunk:
                            break
                        output.write(chunk)
                        if output.tell() > length:
                            raise ValueError("Download exceeds provider length")
            if partial.stat().st_size == length:
                partial.replace(destination)
                return
        except urllib.error.HTTPError as exc:
            # Numeric status only: signed URLs and server bodies may contain secrets.
            print(f"Download attempt {attempt + 1} rejected with HTTP {exc.code}", flush=True)
            if exc.code in (400, 401, 403, 404, 410, 416):
                raise ValueError(
                    f"Upstream denied the download with HTTP {exc.code}; "
                    "do not publish or retry without a new verified source"
                ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            print(f"Download attempt {attempt + 1} interrupted: {type(exc).__name__}", flush=True)
        if attempt != 11:
            time.sleep(min(2 ** attempt, 30))
    raise ValueError("Upstream transfer incomplete after bounded retries")


def check_archive_member(name: str) -> None:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    if (not normalized or normalized.startswith("/") or
            re.match(r"^[A-Za-z]:", normalized) or
            any(part in (".", "..") for part in normalized.split("/")) or
            "\x00" in normalized):
        raise ValueError(f"Unsafe archive member name: {name!r}")


def list_7z_images(archive: Path) -> list[tuple[str, int]]:
    result = subprocess.run(
        ["7z", "l", "-slt", str(archive)], text=True,
        capture_output=True, check=True, timeout=300
    )
    if "----------" not in result.stdout:
        raise ValueError("Malformed 7z file listing")
    records = result.stdout.split("----------", 1)[1].split("\n\n")
    found = []
    for rec in records:
        fields = {}
        for line in rec.splitlines():
            if " = " in line:
                key, value = line.split(" = ", 1)
                fields[key] = value
        name = fields.get("Path")
        if not name:
            continue
        check_archive_member(name)
        if name.lower().endswith(".img"):
            if not fields.get("Size", "").isdigit():
                raise ValueError("Missing image size in 7z")
            found.append((name, int(fields["Size"])))
    return found


def image_members(archive: Path) -> list[tuple[str, int]]:
    if archive.name.lower().endswith(".7z"):
        return list_7z_images(archive)
    if archive.name.lower().endswith(".zip"):
        with zipfile.ZipFile(archive) as source:
            found = []
            for info in source.infolist():
                check_archive_member(info.filename)
                if info.is_dir():
                    continue
                if (info.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError("Archive contains a symbolic link")
                if info.filename.lower().endswith(".img"):
                    found.append((info.filename, info.file_size))
            return found
    if archive.name.lower().endswith(".img"):
        return [(archive.name, archive.stat().st_size)]
    raise ValueError("Unsupported upstream file format")


def extract_image(archive: Path, output: Path) -> None:
    members = image_members(archive)
    if len(members) != 1:
        raise ValueError(f"Expected exactly one flash-image file, found {len(members)}")
    image_name, expected_size = members[0]
    if expected_size < MIN_IMAGE_BYTES:
        raise ValueError("Firmware image is unexpectedly small")
    if archive.suffix.lower() == ".img":
        shutil.copyfile(archive, output)
    elif archive.suffix.lower() == ".zip":
        with zipfile.ZipFile(archive) as source:
            if source.testzip() is not None:
                raise ValueError("ZIP CRC check failed")
            with source.open(image_name) as inp, output.open("wb") as dst:
                shutil.copyfileobj(inp, dst, length=4 * 1024 * 1024)
    else:
        subprocess.run(
            ["7z", "t", str(archive)],
            stdout=subprocess.DEVNULL, check=True, timeout=1800
        )
        with output.open("wb") as dst:
            subprocess.run(
                ["7z", "x", "-so", str(archive), image_name],
                stdout=dst, stderr=subprocess.PIPE, check=True, timeout=1800
            )
    if output.stat().st_size != expected_size:
        raise ValueError("Extracted image does not match archived image length")


def validate_image_header(file: Path) -> dict:
    with file.open("rb") as f:
        raw = f.read(28)
    if len(raw) != 28:
        raise ValueError("Truncated firmware image header")
    checksum, version, magic, image_size, alignment, item_count = struct.unpack(
        "<IIIQII", raw
    )
    actual_size = file.stat().st_size
    if magic not in MAGICS:
        raise ValueError("Not an Amlogic USB Burning Tool package (unknown magic)")
    if version not in (1, 2):
        raise ValueError("Unexpected Amlogic package version")
    if image_size != actual_size:
        raise ValueError("Firmware header image length does not match file length")
    if not 1 <= item_count <= 1024:
        raise ValueError("Implausible Amlogic package item count")
    return {
        "format": MAGICS[magic],
        "magic": f"0x{magic:08x}",
        "version": version,
        "image_size": image_size,
        "item_count": item_count,
        "alignment": alignment,
        "header_crc32_field": f"0x{checksum:08x}",
        "note": "Static package-header check only; USB Burning Tool import and board boot not tested",
    }


def stage_assets(source: Path, image: Path, destination: Path) -> dict:
    destination.mkdir(parents=True, exist_ok=True)
    manifest = {"assets": {}, "reassembly": "Concatenate .partNNNN files in numeric order."}
    for role, original in (("original_archive", source), ("flashable_image", image)):
        size = original.stat().st_size
        names = []
        if size <= MAX_ASSET_BYTES:
            filename = original.name
            dest = destination / filename
            if dest.exists():
                raise ValueError("Archive/image asset filename collision")
            os.link(original, dest)
            names.append({"name": filename, "bytes": size})
        else:
            with original.open("rb") as inp:
                ordinal = 0
                while True:
                    block = inp.read(MAX_ASSET_BYTES)
                    if not block:
                        break
                    ordinal += 1
                    filename = f"{original.name}.part{ordinal:04d}"
                    dest = destination / filename
                    if dest.exists():
                        raise ValueError("Asset name collision")
                    dest.write_bytes(block)
                    names.append({"name": filename, "bytes": len(block)})
        if len(names) > 1000:
            raise ValueError("Too many release assets")
        manifest["assets"][role] = {
            "original_name": original.name, "original_bytes": size, "files": names
        }
    if sum(len(x["files"]) for x in manifest["assets"].values()) > 990:
        raise ValueError("GitHub Release asset count would exceed budget")
    return manifest


def prepare(entry: str, work_dir: Path, required_class: str | None = None) -> None:
    item = CATALOG[entry]
    if required_class is not None and item["class"] != required_class:
        raise ValueError(
            "This workflow cannot publish another classification of firmware"
        )
    if item["share"] is None:
        raise ValueError("Unverified 2022 source: no release will be published")
    if item["class"] == "other_board_stock":
        raise ValueError("The 2101 board is not approved as 2101W stock")
    work_dir.mkdir(parents=True, exist_ok=True)
    share, length, subpath = resolve_yandex(item)
    # Reserve enough for raw archive, extracted image, and GitHub staging segments.
    free = shutil.disk_usage(work_dir).free
    if free < max(5 * 1024**3, length * 5):
        raise ValueError("Insufficient temporary space for safe staging")
    source = work_dir / item["filename"]
    if source.exists():
        if source.stat().st_size != length:
            raise ValueError("Existing archive has a different size")
    else:
        fetch_with_resume(share, subpath, length, source)
    image = work_dir / "amlogic-factory-package.img"
    extract_image(source, image)
    package = validate_image_header(image)
    assets = stage_assets(source, image, work_dir / "assets")
    manifest = {
        "entry": entry, "device": item["device"], "classification": item["class"],
        "version": item["version"], "upstream": item["source_post"],
        "public_share": share, "upstream_file": source.name,
        "provider_size": length, "package": package, **assets,
    }
    (work_dir / "assets" / "original-rom-manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    category = (
        "Original manufacturer stock firmware candidate"
        if item["class"] == "stock_candidate"
        else "Third-party slimBOXtv modification — NOT STOCK"
    )
    (work_dir / "release-notes.md").write_text(
        f"# {item['device']} — {item['version']}\n\n"
        f"**Classification:** {category}.\n\n"
        f"**Upstream attribution:** {item['source_post']}\n\n"
        f"**Public source:** {share}\n\n"
        "The Release includes the untouched upstream archive, the extracted Amlogic "
        "package image, and an original-rom-manifest.json file. Files over 1.9 GB "
        "are contiguous numbered parts; concatenate them in numeric order to "
        "recover the exact original file bytes.\n\n"
        "This only validates archive integrity, image size and Amlogic package "
        "header. It does not establish compatibility with an actual 4GB+64GB "
        "board, vendor signature, USB Burning Tool import, or successful boot. "
        "Review the board and bootloader before any flashing.\n\n"
        "Source-site redistribution condition: retain this original source "
        "post link, and respect all applicable upstream firmware rights.\n",
        encoding="utf-8",
    )
    with (work_dir / "entry.json").open("w", encoding="utf-8") as f:
        json.dump(
            {"classification": item["class"], "version": item["version"], "entry": entry},
            f,
        )
    print(f"Validated {entry}: one complete Amlogic package ({image.stat().st_size} bytes)")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("entry", choices=sorted(CATALOG))
    parser.add_argument("workdir", type=Path)
    parser.add_argument(
        "--require-class", choices=("stock_candidate", "third_party_slimbox")
    )
    args = parser.parse_args()
    try:
        prepare(args.entry, args.workdir.resolve(), args.require_class)
    except (ValueError, OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired,
            urllib.error.URLError, zipfile.BadZipFile) as exc:
        print(f"Firmware archive not publishable: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
