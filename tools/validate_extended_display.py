"""Native extended-display checks with explicitly synthetic lyric timing."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def validate(output, scale):
    os.environ.pop("QT_QPA_PLATFORM", None)
    native_scale = ctypes.windll.shcore.GetScaleFactorForDevice(0) / 100
    os.environ["QT_SCALE_FACTOR"] = str(scale / native_scale)
    os.environ["QT_SCALE_FACTOR_ROUNDING_POLICY"] = "PassThrough"
    os.environ.pop("QT_SCREEN_SCALE_FACTORS", None)
    import numpy as np
    from PySide6.QtCore import QObject, Signal, QPoint, QRect, Qt
    from PySide6.QtWidgets import QApplication
    from PySide6.QtTest import QTest
    from PySide6.QtGui import QPainter
    from overlay import LyricsOverlay
    from controls import ControlPanel
    from player import MusicPlayer
    from fonts import FontLibrary
    from settings import Preferences, SettingsStore, ANIMATION_STYLES
    from lrc import LyricDocument, LyricLine, LyricTimeline, display_document
    from animation import build_layout, display_regions
    from text_effects import TextEffects, pixels_view
    from glyph_motion import glyph_states

    output.mkdir(parents=True, exist_ok=False)
    app = QApplication.instance() or QApplication([])
    prefs = Preferences(theme="special", extended_display=True, extended_display_seconds=10)
    player = MusicPlayer()
    overlay = LyricsOverlay(player, prefs)
    store = SettingsStore(output / "settings.ini")
    panel = ControlPanel(player, overlay, prefs, store, FontLibrary(output / "fonts"))
    panel.refresh_timer.stop()
    panel.show()
    panel.nav_buttons[1].click()
    QTest.qWait(100)
    checks = {"windows_platform": app.platformName() == "windows",
              "actual_dpr": abs(panel.devicePixelRatioF() - scale) < .01}
    for name, size in (("default", (1100, 760)), ("minimum", (900, 560))):
        panel.resize(*size)
        app.processEvents()
        for key, control in (("extended", panel.extended_checkbox), ("seconds", panel.spins["extended_display_seconds"]),
                             ("limit", panel.extended_limit_combo)):
            panel.effects_scroll.ensureWidgetVisible(control, 0, 24)
            app.processEvents()
            rectangle = QRect(control.mapTo(panel.effects_scroll.viewport(), QPoint()), control.size())
            checks[name + "_" + key + "_reachable"] = panel.effects_scroll.viewport().rect().contains(rectangle)
        checks[name + "_footer_visible"] = panel.rect().contains(QRect(panel.player_bar.mapTo(panel, QPoint()), panel.player_bar.size()))
        panel.grab().save(str(output / (name + ".png")))
    panel.spins["extended_display_seconds"].setValue(12)
    checks["saved_immediately"] = store.load().extended_display_seconds == 12 and store.load().extended_display
    panel.apply_preset("builtin:lively")
    checks["preset_preserves_duration"] = prefs.extended_display and prefs.extended_display_seconds == 12
    for limit in (2, 3, 4):
        panel.extended_limit_combo.setCurrentIndex(panel.extended_limit_combo.findData(limit))
        checks[f"limit_{limit}_saved"] = store.load().extended_display_limit == limit
        panel.apply_preset("builtin:quiet")
        checks[f"limit_{limit}_preset_independent"] = prefs.extended_display_limit == limit
    panel.extended_checkbox.setChecked(False)
    checks["limit_disabled_when_not_extended"] = not panel.extended_limit_combo.isEnabled()
    panel.extended_checkbox.setChecked(True)
    checks["limit_enabled_and_retained"] = panel.extended_limit_combo.isEnabled() and panel.extended_limit_combo.currentData() == 4

    class Clock(QObject):
        changed, discontinuity = Signal(), Signal()
        playing, ended, duration, clock = False, False, 30000, 0
        def position(self): return self.clock
        def energy_at(self, _): return .5

    document = LyricDocument([LyricLine(i * 1000, text, translation=translation) for i, (text, translation) in enumerate((
        ("In the city, every echo carries a story.", "每一声回响都承载着故事。"),
        ("We follow the light through the night.", "我们循着微光穿过长夜。"),
        ("Let the rhythm stay a little longer.", "让这份节奏再停留片刻。"),
        ("Face the sin. Save the E.G.O.", "直面原罪，拯救自我。")))], [])
    display = display_document(document, mode="bilingual_original")
    measurements = []
    for style in ANIMATION_STYLES:
        options = Preferences(animation_style=style, scramble_exit=True, glow_variant="gradient", region="full",
                              angle=0, extended_display=True, lyric_display_mode="bilingual_original")
        timeline = LyricTimeline(display, animation_style=style, scramble_exit=True, extended_display_ms=10000)
        renderer = TextEffects()
        layouts, occupied = [], []
        for index, line in enumerate(display.lines):
            layout = build_layout(line.text, index * 7919, display_regions(1280, 800, "full"), occupied, options, line.secondary_start)
            occupied.append(layout.bounds)
            layout.surface = renderer.prepare(layout.glyphs, layout.font_size, options, scale, options.jump, layout.angle)
            layouts.append(layout)
        visible_bounds = []
        for bounds in reversed(occupied):
            if not any(bounds.intersects(other) for other in visible_bounds):
                visible_bounds.append(bounds)
        checks[style + "_visible_blocks_do_not_overlap"] = len(visible_bounds) >= 2 and all(
            not a.intersects(b) for i, a in enumerate(visible_bounds) for b in visible_bounds[i+1:])
        checks[style + "_layout_within_screen"] = all(
            0 <= bounds.left() <= bounds.right() <= 1280 and 0 <= bounds.top() <= bounds.bottom() <= 800 for bounds in occupied)
        samples = []
        for position in range(9450, 9991, 9):
            started = time.perf_counter()
            for item in timeline.visible(position, 30000):
                layout = layouts[item.index]
                states = glyph_states(layout.glyphs, options, item, position, .5, layout.font_size, 730 + item.index, layout.angle)
                renderer.render(layout.surface, options, states=states)
            samples.append((time.perf_counter() - started) * 1000)
        p95 = float(np.percentile(samples[5:], 95))
        checks[style + "_warm_four_bilingual_p95_under_33ms"] = p95 <= 33
        checks[style + "_glow_and_fall_not_clipped"] = all(not (np.any((alpha := pixels_view(layout.surface.image)[:, :, 3])[0])
            or np.any(alpha[-1]) or np.any(alpha[:, 0]) or np.any(alpha[:, -1])) for layout in layouts)
        measurements.append(dict(style=style, simultaneous_blocks=4, bilingual=True, scramble_exit=True,
                                 visible_without_collisions=len(visible_bounds),
                                 warm_render_p95_ms=round(p95, 3), synthetic_lyric_times=True))

    clock = Clock()
    actual = LyricsOverlay(clock, Preferences(region="full", angle=0, extended_display=True,
        animation_style="ripple_wave", scramble_exit=True, glow_variant="gradient", lyric_display_mode="bilingual_original"))
    actual.set_document(document)
    clock.clock = 6500
    actual.show()
    actual.grab()
    deadline = time.monotonic() + 8
    while actual._warm_jobs and time.monotonic() < deadline:
        QTest.qWait(10)
    blocks = actual.timeline.visible(clock.clock, clock.duration)
    checks["actual_four_surfaces_ready"] = len(blocks) == 4 and all(actual.layouts.get(i.index) and actual.layouts[i.index].surface for i in blocks)
    for limit in (2, 3, 4):
        actual.prefs.extended_display_limit = limit
        actual.refresh_preferences()
        actual.grab()
        deadline = time.monotonic() + 8
        while actual._warm_jobs and time.monotonic() < deadline:
            QTest.qWait(10)
        visible = actual.timeline.visible(clock.clock, clock.duration)
        checks[f"actual_limit_{limit}_active"] = len(visible) == limit
        checks[f"actual_limit_{limit}_surfaces_ready"] = all(actual.layouts.get(item.index) and actual.layouts[item.index].surface for item in visible)
        checks[f"actual_limit_{limit}_cache_bounded"] = len(actual.layouts) + len(actual._warm_jobs) <= limit + 1
        frame = actual.grab().toImage()
        checks[f"actual_limit_{limit}_has_pixels"] = bool(pixels_view(frame)[:, :, 3].any())
        frame.save(str(output / f"limit-{limit}.png"))
    before = actual.grab()
    before.save(str(output / "four-blocks.png"))
    QTest.qWait(120)
    checks["pause_freezes_frame"] = before.toImage() == actual.grab().toImage() and not actual.timer.isActive()
    clock.clock = 10000
    clock.discontinuity.emit()
    checks["seek_rebuilds_from_song_position"] = [i.index for i in actual.timeline.visible(clock.clock, clock.duration)] == [1, 2, 3]
    clock.ended = True
    ended_image = actual.grab().toImage()
    checks["song_end_clears_alpha"] = not bool(pixels_view(ended_image)[:, :, 3].any())
    actual.set_document(LyricDocument([LyricLine(0, "测试"), LyricLine(7000, "")], []))
    clock.clock, clock.ended = 7000, False
    blank_image = actual.grab().toImage()
    checks["blank_cue_clears_alpha"] = not bool(pixels_view(blank_image)[:, :, 3].any())
    actual.hide()
    panel.tray.hide()
    panel.hide()
    overlay.hide()
    from app_info import APP_VERSION, KUGOU_VERSION
    result = dict(passed=all(checks.values()), checks=checks, dpr=panel.devicePixelRatioF(), measurements=measurements,
                  app_version=APP_VERSION, kugou_version=KUGOU_VERSION, packaged=bool(getattr(sys, "frozen", False)),
                  music_client_commands=0, real_playback=False, synthetic_lyric_times=True, user_settings_modified=False)
    (output / "report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return 0 if result["passed"] else 1


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scale", type=float, default=1)
    args = parser.parse_args(argv)
    return validate(args.output, args.scale)


if __name__ == "__main__":
    raise SystemExit(main())
