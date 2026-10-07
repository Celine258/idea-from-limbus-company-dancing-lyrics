import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
import unittest
from pathlib import Path
import tempfile
import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath
from PySide6.QtWidgets import QApplication
from animation import Glyph, _glyph_layout, build_layout, display_regions
from settings import Preferences
from text_effects import TextEffects, gaussian_alpha, pixels_view, transparent_image

APP = QApplication.instance() or QApplication([])


def rectangle(width=20):
    path = QPainterPath()
    path.addRect(QRectF(0, 0, width, 20))
    return Glyph(path, 0, 0, 0)


class TextEffectsTests(unittest.TestCase):
    def setUp(self):
        self.effects = TextEffects()
        self.prefs = Preferences(color="#ff4080", opacity=80)
        self.glyph = rectangle()

    def surface(self, glyphs=None, dpr=1, jump=0):
        return self.effects.prepare(glyphs or [self.glyph], 32, self.prefs, dpr, jump)

    @staticmethod
    def sample(surface, x, y):
        dpr = surface.image.devicePixelRatio()
        return surface.image.pixelColor(round((x-surface.origin.x())*dpr), round((y-surface.origin.y())*dpr))

    def test_white_core_colored_outline_and_soft_halo(self):
        surface = self.surface()
        self.effects.render(surface, self.prefs)
        self.assertEqual(self.sample(surface, 10, 10), QColor("#ffffff"))
        outline = self.sample(surface, -1, 10)
        self.assertGreater(outline.red(), outline.green())
        near, far = self.sample(surface, -3, 10), self.sample(surface, -6, 10)
        self.assertGreater(near.alpha(), far.alpha())
        self.assertGreater(far.alpha(), 0)
        self.assertGreater(near.red(), near.green())
        alpha = pixels_view(surface.image)[:, :, 3]
        self.assertFalse(np.any(alpha[0]) or np.any(alpha[-1]) or np.any(alpha[:, 0]) or np.any(alpha[:, -1]))

    def test_strength_zero_keeps_core_outline_and_higher_strength_only_changes_halo(self):
        surface = self.surface()
        alphas = []
        for value in (0, 30, 100):
            self.prefs.glow_strength = value
            self.effects.render(surface, self.prefs)
            self.assertEqual(self.sample(surface, 10, 10), QColor("#ffffff"))
            self.assertGreater(self.sample(surface, -1, 10).alpha(), 100)
            alphas.append(self.sample(surface, -5, 10).alpha())
        self.assertEqual(alphas[0], 0)
        self.assertLess(alphas[1], alphas[2])

    def test_neighbour_halos_do_not_tint_white_cores(self):
        second = rectangle()
        second.x = 21
        surface = self.surface([self.glyph, second])
        self.prefs.glow_strength = 100
        self.effects.render(surface, self.prefs)
        for point in ((19, 10), (22, 10), (30, 10)):
            self.assertEqual(self.sample(surface, *point), QColor("#ffffff"))

    def test_opacity_is_applied_once_to_composited_core_and_halo(self):
        surface = self.surface()
        source = self.effects.render(surface, self.prefs)
        target = QImage(source.size(), source.format())
        target.fill(Qt.GlobalColor.transparent)
        painter = QPainter(target)
        painter.setOpacity(self.prefs.opacity / 100 * .5)
        painter.drawImage(0, 0, source)
        painter.end()
        core = target.pixelColor(round(10-surface.origin.x()), round(10-surface.origin.y()))
        self.assertEqual((core.red(), core.green(), core.blue()), (255, 255, 255))
        self.assertLessEqual(abs(core.alpha() - 102), 2)
        before = self.sample(surface, -5, 10).alpha()
        after = target.pixelColor(round(-5-surface.origin.x()), round(10-surface.origin.y())).alpha()
        self.assertLessEqual(abs(after-before*.4), 2)

    def test_classic_keeps_original_fill_and_dark_outline(self):
        self.prefs.text_style = "solid"
        surface = self.surface()
        self.effects.render(surface, self.prefs)
        self.assertEqual(self.sample(surface, 10, 10), QColor(self.prefs.color))
        self.assertLess(self.sample(surface, -1, 10).red(), 40)
        self.assertEqual(self.sample(surface, -5, 10).alpha(), 0)
        self.assertEqual(self.effects.misses, 0)

    def test_reused_buffer_clears_old_jump_frame(self):
        surface = self.surface(jump=30)
        original_id = id(surface.image)
        self.prefs.jump = 30
        self.effects.render(surface, self.prefs, 1, 1, moving=True)
        self.effects.render(surface, self.prefs, 2, 0, moving=True)
        fresh = self.surface(jump=30)
        self.effects.render(fresh, self.prefs, 2, 0, moving=True)
        self.assertEqual(bytes(surface.image.constBits()), bytes(fresh.image.constBits()))
        self.assertEqual(id(surface.image), original_id)

    def test_cache_uses_actual_shape_color_dpr_and_respects_memory_limit(self):
        first = self.effects.glow(self.glyph, 32, "test", QColor("#ff4080"), 1)
        self.effects.limit_bytes = first[0].sizeInBytes() * 2
        self.assertIs(first, self.effects.glow(rectangle(), 32, "test", QColor("#ff4080"), 1))
        misses = self.effects.misses
        self.prefs.glow_strength = 0
        self.effects.glow(self.glyph, 32, "test", QColor("#ff4080"), 1)
        self.assertEqual(self.effects.misses, misses)
        for width in (2, 10, 22):
            for dpr in (1, 1.25, 1.5):
                self.effects.glow(rectangle(width), 32, "test", QColor("#20a0ff"), dpr)
                self.assertLessEqual(self.effects.cache_bytes, self.effects.limit_bytes)
        self.effects.clear()
        self.assertEqual(self.effects.cache_bytes, 0)

    def test_fractional_dpr_and_thin_strokes_are_not_clipped(self):
        for dpr in (1, 1.25, 1.5):
            surface = self.surface([rectangle(.7)], dpr=dpr)
            self.effects.render(surface, self.prefs)
            self.assertEqual(surface.image.devicePixelRatio(), dpr)
            alpha = pixels_view(surface.image)[:, :, 3]
            self.assertGreater(alpha.max(), 150)
            self.assertFalse(np.any(alpha[0]) or np.any(alpha[-1]) or np.any(alpha[:, 0]) or np.any(alpha[:, -1]))

    def test_gaussian_is_symmetric_and_preserves_empty_mask(self):
        mask = np.zeros((21, 21), dtype=np.float32)
        self.assertFalse(np.any(gaussian_alpha(mask, 2, 6)))
        mask[10, 10] = 1
        result = gaussian_alpha(mask, 2, 6)
        np.testing.assert_allclose(result, np.flip(result, axis=0), atol=1e-7)
        np.testing.assert_allclose(result, np.flip(result, axis=1), atol=1e-7)
        self.assertAlmostEqual(float(result.sum()), 1, places=5)

    def test_imported_font_overhang_renders_with_clear_edges(self):
        from fonts import FontLibrary
        with tempfile.TemporaryDirectory() as directory:
            library = FontLibrary(Path(directory))
            try:
                library.import_font(Path(__file__).parent / "fixtures/lyrics-test.ttf")
                self.prefs.font_family = "Floating Lyrics Test"
                glyphs, _, _ = _glyph_layout("AAA中", 32, 500, self.prefs.font_family)
                surface = self.surface(glyphs, dpr=1.5)
                self.effects.render(surface, self.prefs)
                alpha = pixels_view(surface.image)[:, :, 3]
                self.assertGreater(alpha.max(), 200)
                self.assertFalse(np.any(alpha[0]) or np.any(alpha[-1]) or np.any(alpha[:, 0]) or np.any(alpha[:, -1]))
            finally:
                library.close()

    def test_overlay_dpr_change_invalidates_layouts_and_shared_cache(self):
        from PySide6.QtCore import QEvent
        from netease import NeteasePlayer
        from overlay import LyricsOverlay
        from text_effects import TEXT_EFFECTS
        overlay = LyricsOverlay(NeteasePlayer(), self.prefs)
        try:
            TEXT_EFFECTS.glow(self.glyph, 32, "test", QColor(self.prefs.color), 1)
            overlay.layouts[1] = object()
            APP.sendEvent(overlay, QEvent(QEvent.Type.DevicePixelRatioChange))
            self.assertFalse(overlay.layouts)
            self.assertEqual(TEXT_EFFECTS.cache_bytes, 0)
        finally:
            overlay.hide()
            overlay.deleteLater()

    def test_animated_surface_with_maximum_effects_fits_rotated_layout(self):
        from PySide6.QtGui import QTransform
        self.prefs.font_size, self.prefs.jump, self.prefs.angle = 64, 30, 25
        regions = display_regions(1024, 720, "edges")
        for seed in range(3):
            layout = build_layout("给今天一点节奏 Hello music" * 3, seed, regions, [], self.prefs)
            self.assertIsNotNone(layout)
            surface = self.effects.prepare(layout.glyphs, layout.font_size, self.prefs, 1.5, 30)
            local = QRectF(surface.origin, surface.image.deviceIndependentSize())
            transform = QTransform().translate(layout.center.x(), layout.center.y()).rotate(layout.angle)
            for drift in (-5, 8):
                self.assertTrue(layout.bounds.contains(transform.mapRect(local.translated(0, drift))))


if __name__ == "__main__":
    unittest.main()
