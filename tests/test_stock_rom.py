"""Tests for the offline stock ROM archiver.

Requirements: only supported Amlogic burning images may pass; no network/test device.
Ambiguity: actual provider directory layout and hardware compatibility are untested.
Research: test against a real, approved original .7z after download.
Optimization: synthetic sparse files avoid large test data.
Risks: archive entry traversal, wrong-board aliases, invalid package header.
Verification: unittest discovery; functional network/Release path remains Actions-only.
"""

import importlib.util
import json
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "stock_rom.py"
SPEC = importlib.util.spec_from_file_location("stock_rom", SCRIPT)
stock = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stock)


class SourceTests(unittest.TestCase):
    def test_2024_known_source_only(self):
        self.assertEqual(
            stock.CATALOG["2101w-stock-20240508"]["class"], "stock_candidate"
        )
        self.assertIsNone(stock.CATALOG["2101w-stock-20220525"]["share"])
        self.assertIsNone(stock.CATALOG["2101-stock-20220525"]["share"])

    def test_slimbox_not_stock(self):
        self.assertTrue(all(
            value["class"] == "third_party_slimbox"
            for key, value in stock.CATALOG.items()
            if "slimbox" in key
        ))

    def test_yandex_exact_match_and_size(self):
        selected = stock.CATALOG["2101w-stock-20240508"]
        with mock.patch.object(stock, "request_json", return_value={
            "type": "dir", "_embedded": {"items": [
                {"name": selected["filename"], "type": "file",
                 "size": 778500000, "path": "/X96Max_Plus_2101W_20240508-1103.7z"},
                {"name": "other.7z", "type": "file", "size": 500000000, "path": "/other"},
            ]}
        }):
            self.assertEqual(
                stock.resolve_yandex(selected)[1:], (
                    778500000, "/X96Max_Plus_2101W_20240508-1103.7z"
                )
            )

    def test_no_verifiable_2022_url(self):
        with self.assertRaisesRegex(ValueError, "No verified"):
            stock.resolve_yandex(stock.CATALOG["2101w-stock-20220525"])


class FileTests(unittest.TestCase):
    def test_traversal_rejected(self):
        for path in ("../../boot.img", "/tmp/boot.img", "C:\\boot.img", "x/../boot.img"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                stock.check_archive_member(path)

    def test_aml_image_header(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "firmware.img"
            size = stock.MIN_IMAGE_BYTES
            with image.open("wb") as out:
                out.write(struct.pack("<IIIQII", 0, 2, 0x27B51956, size, 4096, 3))
                out.seek(size - 1)
                out.write(b"\x00")
            data = stock.validate_image_header(image)
            self.assertEqual(data["image_size"], size)
            self.assertEqual(data["item_count"], 3)
            with image.open("r+b") as out:
                out.seek(8)
                out.write(struct.pack("<I", 0x12345678))
            with self.assertRaisesRegex(ValueError, "unknown magic"):
                stock.validate_image_header(image)

    def test_zip_selection_rejects_ota(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "update.zip"
            with zipfile.ZipFile(archive, "w") as out:
                out.writestr("META-INF/com/google/android/updater-script", "none")
            self.assertEqual(stock.image_members(archive), [])

    def test_zip_slip_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "wrong.zip"
            with zipfile.ZipFile(archive, "w") as out:
                out.writestr("../../escape.img", "x")
            with self.assertRaisesRegex(ValueError, "Unsafe"):
                stock.image_members(archive)

    def test_staging_part_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "source.7z"
            image = root / "image.img"
            archive.write_bytes(b"x" * 43)
            image.write_bytes(b"z" * 69)
            with mock.patch.object(stock, "MAX_ASSET_BYTES", 20):
                manifest = stock.stage_assets(archive, image, root / "assets")
            chunks = manifest["assets"]["flashable_image"]["files"]
            self.assertEqual(len(chunks), 4)
            reconstructed = b"".join(
                (root / "assets" / x["name"]).read_bytes() for x in chunks
            )
            self.assertEqual(reconstructed, image.read_bytes())


if __name__ == "__main__":
    unittest.main()
