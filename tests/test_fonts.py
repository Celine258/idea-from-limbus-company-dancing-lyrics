"""Exercise font loading and ink-aware layout with our owned TTF/TTC."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtCore import QRectF
from PySide6.QtWidgets import QApplication
from animation import _glyph_layout, build_layout, display_regions
from fonts import FontLibrary
from settings import Preferences

APP = QApplication.instance() or QApplication([])
FIXTURE = Path(__file__).parent / "fixtures/lyrics-test.ttf"
FAMILY = "Floating Lyrics Test"


class FontLibraryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.library = FontLibrary(self.root / "fonts")

    def tearDown(self):
        self.library.close()
        self.temporary.cleanup()

    def test_real_font_copied_and_reload_does_not_need_source(self):
        source = self.root / "自定义 字体.TTF"
        source.write_bytes(FIXTURE.read_bytes())
        families, added = self.library.import_font(source)
        self.assertTrue(added)
        self.assertIn(FAMILY, families)
        owned = list(self.library.directory.glob("*.ttf"))
        self.assertEqual(len(owned), 1)
        self.assertEqual(owned[0].read_bytes(), source.read_bytes())
        source.unlink()
        self.library.close()
        self.library = FontLibrary(self.root / "fonts")
        self.assertEqual(self.library.restore_family(FAMILY), (FAMILY, ""))

    def test_duplicate_content_does_not_duplicate_files_or_families(self):
        self.library.import_font(FIXTURE)
        renamed = self.root / "another-name.ttf"
        renamed.write_bytes(FIXTURE.read_bytes())
        self.assertFalse(self.library.import_font(renamed)[1])
        self.assertEqual(len(list(self.library.directory.iterdir())), 1)
        self.assertEqual(sum(choice.family == FAMILY for choice in self.library.choices()), 1)

    def test_invalid_missing_and_wrong_extension_fonts_leave_no_import(self):
        invalid = self.root / "invalid.ttf"
        invalid.write_bytes(b"invalid font data")
        wrong = self.root / "font.txt"
        wrong.write_bytes(FIXTURE.read_bytes())
        for path in (self.root / "missing.ttf", invalid, wrong):
            with self.subTest(path=path.name), self.assertRaises(ValueError):
                self.library.import_font(path)
        self.assertFalse(self.library.directory.exists())
        self.assertEqual(len(self.library.choices()), 3)

    def test_failed_copy_does_not_leave_font_registered_or_partial_file(self):
        with patch("fonts.Path.replace", side_effect=PermissionError("cannot save")), self.assertRaises(OSError):
            self.library.import_font(FIXTURE)
        self.assertEqual(list(self.library.directory.iterdir()), [])
        self.assertNotIn(FAMILY, [choice.family for choice in self.library.choices()])

    def test_corrupt_saved_font_is_skipped_and_missing_choice_explained(self):
        self.library.directory.mkdir()
        (self.library.directory / "corrupt.ttf").write_bytes(b"broken")
        self.library.close()
        with self.assertLogs(level="WARNING"):
            self.library = FontLibrary(self.root / "fonts")
        self.assertEqual(self.library.errors, ["corrupt.ttf"])
        family, message = self.library.restore_family(FAMILY)
        self.assertEqual(family, "Microsoft YaHei UI")
        self.assertIn("不可用", message)

    def test_collection_loads_all_families_without_duplicate_choices(self):
        families, added = self.library.import_font(FIXTURE.with_suffix(".ttc"))
        self.assertTrue(added)
        self.assertEqual(set(families), {FAMILY, "Floating Lyrics Second"})
        self.assertEqual(self.library.restore_family("Floating Lyrics Second"), ("Floating Lyrics Second", ""))
        self.assertEqual(len(self.library.choices()), 5)

    def test_opentype_cff_import_persists_and_reloads(self):
        family = "Floating Lyrics OpenType"
        self.assertEqual(self.library.import_font(FIXTURE.with_suffix(".otf"))[0], [family])
        self.assertEqual(len(list(self.library.directory.glob("*.otf"))), 1)
        self.library.close()
        self.library = FontLibrary(self.root / "fonts")
        self.assertEqual(self.library.restore_family(family), (family, ""))

    def test_imported_overhang_is_included_in_layout_bounds(self):
        self.library.import_font(FIXTURE)
        glyphs, width, height = _glyph_layout("AAA\n中", 32, 300, FAMILY)
        bounds = QRectF(-width / 2, -height / 2, width, height)
        for glyph in glyphs:
            self.assertTrue(bounds.contains(glyph.path.boundingRect().translated(glyph.x, glyph.baseline)))
        self.assertGreater(width, 3 * 600 / 1000 * 32, "测试字体的实际字形超出逻辑字宽")
        regions = display_regions(1024, 720, "edges")
        layout = build_layout("AAA中" * 8, 19, regions, [], Preferences(font_family=FAMILY, font_size=64, angle=25, jump=30))
        self.assertIsNotNone(layout)
        self.assertTrue(any(region.contains(layout.bounds) for region in regions))


if __name__ == "__main__":
    unittest.main()
