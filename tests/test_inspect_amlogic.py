"""Offline synthetic tests for Amlogic package metadata inspection.

Requirements: trust neither item count nor data offset; no ROM execution.
Unknowns: full 2024 firmware item table until real Actions analysis finishes.
Risks: offset overflow, duplicate entries, invalid names, incomplete file.
Verification: v1/v2 fixtures with deliberate rejected malformed images.
"""
import importlib.util
import struct
import tempfile
import unittest
from pathlib import Path

FILE = Path(__file__).resolve().parents[1] / "scripts" / "inspect_amlogic.py"
SPEC = importlib.util.spec_from_file_location("inspect_amlogic", FILE)
aml = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(aml)


def build_fixture(path: Path, version=2, duplicate=False, overlap=False, alias=False, bad_name=False):
    rec = aml.ITEM_FORMATS[version]
    header_size = 64 + 2 * rec.size
    data_a = b"ANDROID!" + bytes(4096 - 8)
    data_b = b"\xd0\x0d\xfe\xed" + bytes(4096 - 4)
    length = header_size + len(data_a) + len(data_b)
    header = aml.HEADER.pack(0, version, aml.MAGIC, length, 4096, 2, bytes(36))
    def name(v, width):
        return v.encode().ljust(width, b"\0")
    width = 256 if version == 2 else 32
    sub_a = "../boot" if bad_name else "boot"
    sub_b = "boot" if duplicate else "dtb"
    item_a = rec.pack(0, 0, 0, header_size, len(data_a),
                      name("PARTITION", width), name(sub_a, width), bytes(32))
    item_b = rec.pack(1, 0, 0,
                      (header_size + 10 if overlap else header_size if alias else header_size + len(data_a)),
                      len(data_b), name("PARTITION", width), name(sub_b, width),
                      bytes(32))
    path.write_bytes(header + item_a + item_b + data_a + data_b)


class InspectorTest(unittest.TestCase):
    def test_v1_and_v2_extraction(self):
        for version in (1, 2):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                rom = root / "rom.img"
                build_fixture(rom, version=version)
                result = aml.inspect(rom, root / "out")
                self.assertEqual(len(result["items"]), 2)
                self.assertEqual(len(result["extracted"]), 2)
                self.assertEqual((root / "out" / "boot.img").read_bytes()[:8], b"ANDROID!")
                self.assertEqual((root / "out" / "dtb.img").read_bytes()[:4], b"\xd0\x0d\xfe\xed")

    def test_duplicate_item_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            rom = root / "rom.img"
            build_fixture(rom, duplicate=True)
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                aml.inventory(rom)

    def test_overlap_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            rom = root / "rom.img"
            build_fixture(rom, overlap=True)
            with self.assertRaisesRegex(ValueError, "Overlapping"):
                aml.inventory(rom)

    def test_exact_shared_span_is_valid(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            rom = root / "rom.img"
            build_fixture(rom, alias=True)
            rows = aml.inventory(rom)
            self.assertEqual(rows[0]["offset"], rows[1]["offset"])
            self.assertEqual(rows[0]["length"], rows[1]["length"])

    def test_unsafe_item_name(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            rom = root / "rom.img"
            build_fixture(rom, bad_name=True)
            with self.assertRaisesRegex(ValueError, "Unexpected"):
                aml.inventory(rom)


if __name__ == "__main__":
    unittest.main()
