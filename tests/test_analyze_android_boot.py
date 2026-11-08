"""Synthetic recovery boot analysis tests (no hardware or vendor files).

Requirements: faithfully read selected stock boot image components and cpio.
Ambiguities: real kernel DTB and FBE require a separate stock image audit.
Risks: malformed page sizes, truncated firmware, unsafe cpio entry names.
Verification: deterministic gzip/newc, DTBO and boundary cases; Actions runs real ROM.
"""
import gzip
import importlib.util
import struct
import tempfile
import unittest
from pathlib import Path

FILE = Path(__file__).resolve().parents[1] / "scripts" / "analyze_android_boot.py"
SPEC = importlib.util.spec_from_file_location("analyze_android_boot", FILE)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def cpio_item(name, content):
    values = [0, 0o100644, 0, 0, 1, 0, len(content), 0, 0, 0, 0,
              len(name.encode()) + 1, 0]
    block = b"070701" + b"".join(f"{value:08x}".encode() for value in values)
    block += name.encode() + b"\0"
    block += bytes((-len(block)) % 4)
    block += content
    block += bytes((-len(block)) % 4)
    return block


def make_cpio(name="etc/recovery.fstab"):
    return (cpio_item(name, b"/data ext4 /dev/block/by-name/data\n") +
            cpio_item("TRAILER!!!", b""))


class BootAnalysisTests(unittest.TestCase):
    def test_valid_recovery_with_gzip_ramdisk(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            rom = root / "recovery.img"
            kernel = b"KERNEL" * 2
            ramdisk = gzip.compress(make_cpio())
            second = b"SECOND-DTB"
            header = bytearray(2048)
            header[:8] = b"ANDROID!"
            struct.pack_into("<10I", header, 8, len(kernel), 0x1080000,
                             len(ramdisk), 0x1000000, len(second), 0,
                             0x100, 2048, 1, 0)
            hdr = bytes(header)
            rom.write_bytes(hdr + kernel.ljust(2048, b"\0") +
                            ramdisk.ljust(2048, b"\0") +
                            second.ljust(2048, b"\0"))
            report = mod.probe_android_boot(rom, root / "out")
            self.assertEqual(report["page_size"], 2048)
            self.assertEqual(report["header_version"], 1)
            self.assertEqual(report["ramdisk_tree"]["compression"], "gzip-newc")
            self.assertEqual(
                (root / "out/ramdisk-files/etc/recovery.fstab").read_bytes(),
                b"/data ext4 /dev/block/by-name/data\n"
            )

    def test_reject_cpio_path_traversal(self):
        with self.assertRaisesRegex(ValueError, "Invalid cpio entry name"):
            mod.safe_ramdisk_names(make_cpio("../../escape"))

    def test_android_dtbo_header(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            fdt = b"\xd0\x0d\xfe\xed" + bytes(12)
            data = struct.pack(">8I", 0xd7b7ab1e, 80, 32, 32, 1, 32, 2048, 0)
            data += struct.pack(">8I", 16, 64, 0, 0, 0, 0, 0, 0)
            image = root / "dtbo.img"
            image.write_bytes(data + fdt)
            report = mod.probe_dtbo(image, root / "out")
            self.assertEqual(report["entries"][0]["file"], "dtbo-0.dtb")
            self.assertEqual((root / "out/dtbo-0.dtb").read_bytes(), fdt)


if __name__ == "__main__":
    unittest.main()
