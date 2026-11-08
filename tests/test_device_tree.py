"""Offline source-level checks for the X96 MAX+ 2101W TWRP device tree.

Requirements: separate S905X3/SM1 from S905X2/G12A and keep flash safety.
Ambiguities: final target partition capacity, real mounting, remote controls,
original-vendor ABI libraries, and TWRP source branch are unverified.
Research: verify 4GB AC213 DTB and stock ELF32/ELF64 layout before boot.
Risks: incorrect mount/image names, accidental board alias, AVB bypass or wipe.
Verification: compare source files with archived stock metadata, lint this tree,
then perform a full Android build in a separate non-publishing pipeline.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def settings(path: str) -> dict[str, str]:
    source = (ROOT / path).read_text(encoding="utf-8")
    result = {}
    for line in source.splitlines():
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:?=\s*(.*)$", line)
        if m:
            result[m.group(1)] = m.group(2)
    return result


class TreeTests(unittest.TestCase):
    def test_device_and_soc_separate_from_u212(self):
        board = settings("BoardConfig.mk")
        product = settings("omni_x96maxplus2101w.mk")
        self.assertEqual(board["TARGET_SOC"], "s905x3")
        self.assertEqual(board["TARGET_BOARD_PLATFORM"], "sm1")
        self.assertEqual(product["PRODUCT_DEVICE"], "x96maxplus2101w")
        self.assertEqual(product["PRODUCT_NAME"], "omni_x96maxplus2101w")
        self.assertNotIn("u212", product["PRODUCT_DEVICE"])
        self.assertEqual(board["TARGET_ARCH"], "arm")
        self.assertEqual(board["TARGET_COPY_OUT_VENDOR"], "vendor")

    def test_original_recovery_header_geometry(self):
        board = settings("BoardConfig.mk")
        self.assertEqual(board["BOARD_KERNEL_PAGESIZE"], "2048")
        self.assertEqual(board["BOARD_INCLUDE_RECOVERY_DTBO"], "true")
        self.assertEqual(board["BOARD_RECOVERYIMAGE_PARTITION_SIZE"], "16777216")
        args = (ROOT / "BoardConfig.mk").read_text()
        for value in ("0x01080000", "0x01000000", "0x00F00000",
                      "0x00000100", "--header_version 1", "prebuilt/second",
                      "prebuilt/dtbo.img"):
            self.assertIn(value, args)

    def test_twrp_fstab_blocks_unverified_sensitive_wipes(self):
        original = (ROOT / "recovery/root/etc/recovery.fstab").read_text()
        twrp = (ROOT / "recovery/root/etc/twrp.fstab").read_text()
        self.assertIn("encryptable=footer", original)
        self.assertIn("/dev/block/recovery", original)
        self.assertIn("/dev/block/metadata", original)
        self.assertIn("/dev/block/system", twrp)
        self.assertIn("/dev/block/recovery", twrp)
        forbidden = {"/bootloader", "/tee", "/metadata", "/param"}
        for line in twrp.splitlines():
            if line.startswith("#") or not line.strip():
                continue
            self.assertNotIn(line.split()[0], forbidden)
            if line.startswith("/data"):
                self.assertNotIn("wipeingui", line)

    def test_no_source_prebuilt_vendor_images_committed(self):
        for name in ("kernel", "second", "dtbo.img"):
            self.assertFalse((ROOT / "prebuilt" / name).exists())

    def test_all_essential_build_files_present(self):
        for path in ("BoardConfig.mk", "Android.mk", "AndroidProducts.mk",
                     "omni_x96maxplus2101w.mk", "scripts/prepare_twrp_prebuilt.py",
                     "docs/TWRP_PORTING.md", "recovery/root/etc/twrp.fstab"):
            self.assertTrue((ROOT / path).is_file(), path)


if __name__ == "__main__":
    unittest.main()
