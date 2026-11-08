"""Synthetic validations of non-Release TWRP 9.0 output.

Requirements: independently reject absent/malformed or mismatched stock kernel
and DTBO; a valid Android header is never device boot proof.
Ambiguities: actual partition capacity and USB runtime remain unverified.
Risks: false acceptance of an otherwise Android-format but wrong-board image.
Verification: construct exact-size synthetic v1 images and mutate one source byte.
"""
import importlib.util
import struct
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location(
    "validate_native_recovery", SCRIPTS / "validate_native_recovery.py"
)
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class NativeValidationTests(unittest.TestCase):
    def build_fake(self, root: Path):
        prebuilt = root / "original"
        prebuilt.mkdir()
        image = root / "recovery.img"
        kernel = b"\x01" * validator.EXPECT["kernel_bytes"]
        second = b"\x02" * validator.EXPECT["second_bytes"]
        dtbo = b"\x03" * validator.EXPECT["recovery_dtbo_bytes"]
        (prebuilt / "kernel").write_bytes(kernel)
        (prebuilt / "second").write_bytes(second)
        (prebuilt / "dtbo.img").write_bytes(dtbo)
        ramdisk = b"\x04" * 2048
        page = 2048
        pad = lambda x: x + bytes((-len(x)) % page)
        offset = page + len(pad(kernel)) + len(pad(ramdisk)) + len(pad(second))
        header = bytearray(page)
        header[:8] = b"ANDROID!"
        struct.pack_into("<10I", header, 8,
                         len(kernel), 0x01080000, len(ramdisk), 0x01000000,
                         len(second), 0x00F00000, 0x100, page, 1, 0)
        struct.pack_into("<IQI", header, 1632, len(dtbo), offset, 1648)
        image.write_bytes(
            bytes(header) + pad(kernel) + pad(ramdisk) + pad(second) + pad(dtbo)
        )
        return image, prebuilt

    def test_stock_equivalent_header_accepted_only_statically(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            image, prebuilts = self.build_fake(root)
            result = validator.validate(image, prebuilts, root / "result")
            self.assertEqual(result["result"], "static_candidate_only")
            self.assertEqual(result["release"], "disabled")

    def test_corrupt_second_stage_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            image, prebuilts = self.build_fake(root)
            (prebuilts / "second").write_bytes(b"0" * validator.EXPECT["second_bytes"])
            with self.assertRaisesRegex(ValueError, "Built second differs"):
                validator.validate(image, prebuilts, root / "result")

    def test_absent_image_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with self.assertRaisesRegex(ValueError, "No genuine built recovery image"):
                validator.validate(root / "missing.img", root, root / "out")


if __name__ == "__main__":
    unittest.main()
