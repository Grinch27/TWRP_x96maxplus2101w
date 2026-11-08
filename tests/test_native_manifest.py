"""Verify exact source closure for the legacy Android 9 TWRP Manifest.

Requirements: only genuine AOSP 9 source providers, no dummy modules or
ALLOW_MISSING_DEPENDENCIES, one path per project.
Unknowns: transitive dependencies beyond reported Soong errors.
Research: compare missing modules with actual output from Soong bootstrap.
Risks: removed upstream project or mismatched Android release tag.
Verification: XML parsing, path uniqueness, identity and project inventory.
"""
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "build/manifests/twrp9-required.xml"
REQUIRED = {
    "external/skia", "external/libphonenumber", "external/nist-sip",
    "external/tagsoup", "external/sonivox", "external/jsmn",
    "external/curl", "tools/apksig", "external/libmpeg2",
    "external/aac", "external/okhttp", "external/junit",
    "external/libtextclassifier", "external/libgsm", "external/guava",
    "external/jsoncpp", "external/tremolo", "prebuilts/tools",
    "external/hamcrest",
    "external/libvpx", "external/jacoco", "external/libopus",
    "external/libhevc", "external/jsr305", "external/giflib",
    "external/sqlite", "external/libjpeg-turbo", "external/harfbuzz_ng",
    "external/pdfium", "frameworks/minikin", "prebuilts/gradle-plugin",
    "development",
    "external/libyuv", "external/libavc", "external/jsilver",
    "external/zopfli",
    "external/jsr330", "external/doclava", "external/libexif",
    "external/piex", "test/vts",
    "external/antlr", "external/webp", "system/bt",
    "frameworks/ml",
    "external/libdivsufsort",
    "external/fonttools",
}


class RequiredSourcesTests(unittest.TestCase):
    def test_manifest_is_bounded_and_valid(self):
        tree = ET.parse(MANIFEST)
        self.assertEqual(tree.getroot().tag, "manifest")
        projects = tree.findall("project")
        self.assertEqual(len(projects), len(REQUIRED))
        paths = [p.get("path") for p in projects]
        self.assertEqual(set(paths), REQUIRED)
        self.assertEqual(len(paths), len(set(paths)))
        for project in projects:
            with self.subTest(project=project.get("path")):
                self.assertEqual(project.get("name"), "platform/" + project.get("path"))
                self.assertEqual(project.get("remote"), "aosp")
                self.assertEqual(project.get("revision"), "refs/tags/android-9.0.0_r47")
                self.assertEqual(project.get("groups"), "default")

    def test_no_fake_dependency_bypass(self):
        script = (ROOT / "scripts/build_twrp_native.sh").read_text()
        self.assertIn("build/manifests/twrp9-required.xml", script)
        self.assertNotIn("export ALLOW_MISSING_DEPENDENCIES", script)
        self.assertNotIn("touch external/skia/Android.bp", script)


if __name__ == "__main__":
    unittest.main()
