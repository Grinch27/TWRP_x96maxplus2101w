"""Tests for recovery-only exclusion of unrelated phone HAL graph references.

Requirements: exactly three vendor references in the known Omni Android 9
non-recovery service; no stub modules, no global dependency-bypass flags.
Ambiguities: the upstream services.core file can change across branches.
Risks: unsafe edits to unrelated Android framework build definitions.
Verification: byte-preserving diff on other lines; strict duplicate/unknown fail.
"""
import importlib.util
import tempfile
import unittest
from pathlib import Path

FILE = Path(__file__).resolve().parents[1] / "scripts" / "prune_nonrecovery_hal.py"
SPEC = importlib.util.spec_from_file_location("prune_nonrecovery_hal", FILE)
tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tool)


def source():
    return (
        'java_library_static {\n'
        '    name: "services.core.unboosted",\n'
        '    static_libs: [\n'
        '        "android.hardware.health-V1.0-java",\n'
        '        "vendor.oneplus.fingerprint.extension-V1.0-java",\n'
        '        "vendor.oneplus.hardware.display-V1.0-java",\n'
        '        "motorola.hardware.health-V1.0-java",\n'
        '    ],\n'
        '}\n'
        'java_library { name: "recovery-unrelated", }\n'
    )


class SelectionTests(unittest.TestCase):
    def test_remove_only_nonrecovery_vendor_imports(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "Android.bp"
            f.write_text(source())
            self.assertEqual(tool.prune(f), 3)
            result = f.read_text()
            self.assertIn('"android.hardware.health-V1.0-java"', result)
            self.assertIn('recovery-unrelated', result)
            self.assertNotIn('vendor.oneplus', result)
            self.assertNotIn('"motorola.hardware.health', result)

    def test_duplicate_vendor_reference_fails(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "Android.bp"
            f.write_text(source().replace(
                '        "motorola.hardware.health-V1.0-java",\n',
                '        "motorola.hardware.health-V1.0-java",\n'
                '        "motorola.hardware.health-V1.0-java",\n',
            ))
            with self.assertRaisesRegex(ValueError, "Unexpected Android.bp"):
                tool.prune(f)
            self.assertIn('"motorola.hardware.health', f.read_text())

    def test_wrong_module_fails_without_edit(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "Android.bp"
            v = source().replace(
                'name: "services.core.unboosted"', 'name: "services.core.updated"')
            f.write_text(v)
            with self.assertRaisesRegex(ValueError, "Expected one"):
                tool.prune(f)
            self.assertEqual(f.read_text(), v)


if __name__ == "__main__":
    unittest.main()
