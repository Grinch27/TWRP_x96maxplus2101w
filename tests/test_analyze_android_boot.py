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
            struct.pack_into("<IQI", header, 1632, 0, 0, 1648)
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

    def test_stock_elf_architecture_probe(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            elf = bytearray(20)
            elf[:4] = b"\x7fELF"
            elf[4] = 1
            elf[5] = 1
            struct.pack_into("<H", elf, 18, 40)
            blob = cpio_item("sbin/recovery", bytes(elf)) + cpio_item("TRAILER!!!", b"")
            source = root / "ramdisk.gz"
            source.write_bytes(gzip.compress(blob))
            data = mod.read_ramdisk(source, root / "out")
            self.assertEqual(data["elf_binaries"], [
                {"name": "sbin/recovery", "elf_class": "ELF32", "machine": "ARM"}
            ])

    def test_reject_cpio_path_traversal(self):
        with self.assertRaisesRegex(ValueError, "Invalid cpio entry name"):
            mod.safe_ramdisk_names(make_cpio("../../escape"))

    def test_amlogic_multi_dtb_extract(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            fdt = b"\xd0\x0d\xfe\xed" + struct.pack(">I", 40) + bytes(32)
            def coded(token):
                raw = token.encode().ljust(16, b" ")
                return b"".join(raw[i:i + 4][::-1] for i in range(0, 16, 4))
            tokens = coded("sm1") + coded("ac213") + coded("4g")
            record = tokens + struct.pack("<II", 68, 40)
            image = root / "source.img"
            image.write_bytes(b"AML_" + struct.pack("<II", 2, 1) + record + fdt)
            report = mod.parse_amlogic_dtb(image, root / "out")
            self.assertEqual(report["kind"], "amlogic-multi")
            self.assertEqual(report["entries"][0]["tokens"], ["sm1", "ac213", "4g"])
            self.assertEqual((root / "out/board-0.dtb").read_bytes(), fdt)

    def test_android_v1_recovery_dtbo_section(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            recovery = root / "recovery.img"
            kernel = b"K" * 3
            ramdisk = b"R" * 3
            second = b"S" * 3
            overlay = b"DTBO"
            page = 2048
            dtbo_offset = page * 4
            header = bytearray(page)
            header[:8] = b"ANDROID!"
            struct.pack_into("<10I", header, 8, len(kernel), 0x1080000,
                             len(ramdisk), 0x1000000, len(second), 0xf00000,
                             0x100, page, 1, 0)
            struct.pack_into("<IQI", header, 1632, len(overlay), dtbo_offset, 1648)
            recovery.write_bytes(
                bytes(header) + kernel.ljust(page, b"\0") +
                ramdisk.ljust(page, b"\0") +
                second.ljust(page, b"\0") +
                overlay.ljust(page, b"\0")
            )
            result = mod.probe_android_boot(recovery, root / "out")
            self.assertEqual(result["recovery_dtbo_bytes"], len(overlay))
            self.assertEqual(result["recovery_dtbo_offset"], dtbo_offset)
            self.assertEqual((root / "out/recovery_dtbo.img").read_bytes(), overlay)

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
