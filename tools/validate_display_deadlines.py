"""Native UI and long-sentence render measurements with labelled synthetic cues.

Run in a separate process per scale. Never opens or controls a music client,
and stores settings/fonts only in the supplied output directory.
"""
import argparse
import ctypes
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def validate(output, scale):
    os.environ.pop("QT_QPA_PLATFORM", None)
    # QT_SCALE_FACTOR multiplies Windows' native scale; request an absolute DPR.
    system_scale = ctypes.windll.shcore.GetScaleFactorForDevice(0) / 100
    if system_scale <= 0:
        raise RuntimeError("Cannot read the primary monitor's scale")
    os.environ["QT_SCALE_FACTOR"] = str(scale / system_scale)
    os.environ.pop("QT_SCREEN_SCALE_FACTORS", None)
    os.environ["QT_SCALE_FACTOR_ROUNDING_POLICY"] = "PassThrough"
    from PySide6.QtCore import QObject, Signal, QRect, QPoint, QRectF, Qt
    from PySide6.QtGui import QPainter, QColor
    from PySide6.QtWidgets import QApplication
    from PySide6.QtTest import QTest
    import numpy as np
    from controls import ControlPanel
    from player import MusicPlayer
    from overlay import LyricsOverlay
    from settings import Preferences, SettingsStore
    from fonts import FontLibrary
    from lrc import LyricTimeline, parse_lrc
    from animation import _glyph_layout
    from glyph_motion import glyph_states
    from text_effects import TextEffects, pixels_view, transparent_image

    output.mkdir(parents=True, exist_ok=False)
    app = QApplication([])
    prefs = Preferences(theme="special", animation_style="ripple_wave", hide_instrumental=True)
    player = MusicPlayer()
    overlay = LyricsOverlay(player, prefs)
    store = SettingsStore(output / "settings.ini")
    panel = ControlPanel(player, overlay, prefs, store, FontLibrary(output / "fonts"))
    panel.refresh_timer.stop()
    panel.show()
    QTest.qWait(100)
    checks = {"windows_platform": app.platformName() == "windows",
              "native_window_visible": bool(ctypes.windll.user32.IsWindowVisible(int(panel.winId()))),
              "actual_dpr": abs(panel.devicePixelRatioF() - scale) < .01}
    panel.nav_buttons[1].click()
    for name, size in (("default", (1100, 760)), ("minimum", (900, 560))):
        panel.resize(*size)
        app.processEvents()
        control = panel.spins["max_display_seconds"]
        center = control.mapTo(panel.effects_scroll.widget(), control.rect().center())
        panel.effects_scroll.ensureVisible(center.x(), center.y(), 0, control.height() // 2 + 24)
        app.processEvents()
        rectangle = QRect(control.mapTo(panel.effects_scroll.viewport(), QPoint()), control.size())
        checks[name + "_lifetime_reachable"] = panel.effects_scroll.viewport().rect().contains(rectangle)
        checks[name + "_footer_visible"] = panel.rect().contains(
            QRect(panel.player_bar.mapTo(panel, QPoint()), panel.player_bar.size()))
        panel.grab().save(str(output / (name + ".png")))
    panel.spins["max_display_seconds"].setValue(9)
    checks["save_immediately"] = SettingsStore(output / "settings.ini").load().max_display_seconds == 9
    panel.apply_preset("builtin:lively")
    checks["preset_preserves_deadline"] = prefs.max_display_seconds == 9
    panel.spins["max_display_seconds"].setValue(6)
    instrumental = parse_lrc("[00:00]作曲：示例作者\n[00:10]纯音乐，请欣赏")
    overlay.set_document(instrumental)
    checks["instrumental_credits_hidden"] = overlay.timeline is None

    text = "In the quiet city we follow every echo through the night and find another morning."
    document = parse_lrc("[00:01]" + text + "\n[00:30]下一句")
    measurements = []
    for style in ("ripple_wave", "ripple_shake", "fall_wave", "fall_shake"):
        options = Preferences(animation_style=style, scramble_exit=True, glow_variant="gradient", jump=0)
        timeline = LyricTimeline(document, animation_style=style, scramble_exit=True, max_display_ms=6000)
        renderer = TextEffects()
        glyphs, _, _ = _glyph_layout(text, 32, 800)
        started = time.perf_counter()
        steps = renderer.prepare_steps(glyphs, 32, options, scale)
        surface = next(ready for ready in steps if ready is not None)
        entrance_ready_ms = (time.perf_counter() - started) * 1000
        checks[style + "_entrance_ready_before_exit_symbols"] = surface.replacements is None
        for _ in steps:
            pass
        full_ready_ms = (time.perf_counter() - started) * 1000
        samples, exit_samples = [], []
        surfaces = (surface, renderer.prepare(glyphs, 32, options, scale))
        # Include the actual 6400-7000 ms exit, not only entry/hold frames.
        for position in [1100 + frame * 70 for frame in range(60)] + [6401 + frame * 9 for frame in range(60)]:
            item = timeline.visible(position, 40000)[0]
            began = time.perf_counter()
            for prepared in surfaces:
                states = glyph_states(glyphs, options, item, position, .5, 32, 730)
                renderer.render(prepared, options, states=states)
            elapsed = (time.perf_counter() - began) * 1000
            samples.append(elapsed)
            if position >= item.exit_start_ms:
                exit_samples.append(elapsed)
        p95 = float(np.percentile(samples[10:], 95))
        exit_p95 = float(np.percentile(exit_samples, 95))
        checks[style + "_warm_two_long_lines_p95_under_33ms"] = p95 <= 33
        checks[style + "_actual_scramble_exit_p95_under_33ms"] = exit_p95 <= 33
        checks[style + "_no_residue_after_deadline"] = not timeline.visible(7000, 40000)
        measurements.append(dict(style=style, characters=len(text), lines=2, scramble_exit=True,
            material="gradient_outline", entrance_ready_ms=round(entrance_ready_ms, 3),
            full_ready_ms=round(full_ready_ms, 3), warm_render_p95_ms=round(p95, 3),
            exit_samples=len(exit_samples), warm_exit_render_p95_ms=round(exit_p95, 3),
            synthetic_lyric_times=True))
        if style == "ripple_wave":
            picture = transparent_image(QRectF(0, 0, 960, 720), scale)
            picture.fill(QColor("#18232f"))
            painter = QPainter(picture)
            alpha_totals = []
            for row, position in enumerate((1100, 1350, 1700, 6800)):
                item = timeline.visible(position, 40000)[0]
                states = glyph_states(glyphs, options, item, position, 0, 32, 730)
                image = renderer.render(surface, options, states=states)
                alpha_totals.append(int(pixels_view(image)[:, :, 3].sum()))
                painter.setPen(QColor("#d9e4ef"))
                painter.drawText(32, 32 + row * 180, f"{position-1000} ms   /   synthetic animation sample")
                painter.save()
                painter.translate(480, 95 + row * 180)
                painter.drawImage(surface.origin, image)
                painter.restore()
            painter.end()
            checks["long_entrance_progressive_pixels"] = alpha_totals[0] < alpha_totals[1] < alpha_totals[2]
            checks["long_exit_reduces_pixels"] = alpha_totals[3] < alpha_totals[2]
            picture.save(str(output / "long-entrance.png"))

    class PausedPlayer(QObject):
        changed, discontinuity = Signal(), Signal()
        playing, ended, duration, clock = False, False, 40000, 0
        def position(self): return self.clock
        def energy_at(self, _): return .5
    paused = PausedPlayer()
    actual_overlay = LyricsOverlay(paused, Preferences(animation_style="ripple_wave", scramble_exit=True, glow_variant="gradient"))
    actual_overlay.set_document(document)
    actual_overlay.show()
    actual_overlay.grab()
    deadline = time.monotonic() + 5
    while actual_overlay._warm_jobs and time.monotonic() < deadline:
        QTest.qWait(10)
    checks["upcoming_long_sentence_preloaded"] = bool(actual_overlay.layouts.get(0) and actual_overlay.layouts[0].surface)
    paused.clock = 1350
    before = actual_overlay.grab().toImage()
    QTest.qWait(100)
    checks["paused_frame_frozen"] = before == actual_overlay.grab().toImage() and not actual_overlay.timer.isActive()
    paused.clock = 9000
    cleared = actual_overlay.grab().toImage().convertToFormat(surface.image.format())
    checks["overlay_deadline_clears_alpha"] = not bool(pixels_view(cleared)[:, :, 3].any())
    actual_overlay.hide()
    panel.tray.hide()
    panel.hide()
    overlay.hide()
    result = dict(passed=all(checks.values()), checks=checks, dpr=panel.devicePixelRatioF(),
                  measurements=measurements, music_client_commands=0, real_playback=False,
                  synthetic_lyric_times=True, user_settings_modified=False)
    (output / "report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scale", type=float, default=1)
    args = parser.parse_args()
    raise SystemExit(validate(args.output, args.scale))
