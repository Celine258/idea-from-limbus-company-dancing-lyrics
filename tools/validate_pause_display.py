"""Native pause/resume pixel checks using explicitly synthetic source packets.

Never connects to or controls a user's music client. The same dispatch can run
from each public EXE with the developer interpreter removed from PATH.
"""
import argparse
from concurrent.futures import Future
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
    from PySide6.QtCore import QPoint, QRect
    from PySide6.QtGui import QImage
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from controls import ControlPanel
    from fonts import FontLibrary
    from kugou import KugouPlayer, KugouSnapshot
    from netease import NeteasePlayer
    from overlay import LyricsOverlay
    from player import MusicPlayer
    from qqmusic import QQMusicPlayer, QQSnapshot
    from settings import Preferences, SettingsStore
    from lrc import LyricDocument, LyricLine
    from text_effects import pixels_view
    from app_info import APP_VERSION, KUGOU_VERSION

    output.mkdir(parents=True, exist_ok=False)
    app = QApplication.instance() or QApplication([])
    checks = {"windows_platform": app.platformName() == "windows"}
    prefs = Preferences(theme="special")
    local = MusicPlayer()
    overlay = LyricsOverlay(local, prefs)
    store = SettingsStore(output / "settings.ini")
    fonts = FontLibrary(output / "fonts")
    panel = ControlPanel(local, overlay, prefs, store, fonts)
    panel.refresh_timer.stop()
    panel.show()
    panel.nav_buttons[1].click()
    QTest.qWait(50)
    checks["actual_dpr"] = abs(panel.devicePixelRatioF() - scale) < .01
    checks["default_off"] = not panel.pause_checkbox.isChecked()
    for name, size in (("default", (1100, 760)), ("minimum", (900, 560))):
        panel.resize(*size)
        panel.effects_scroll.ensureWidgetVisible(panel.pause_checkbox, 0, 24)
        app.processEvents()
        viewport = panel.effects_scroll.viewport()
        rectangle = QRect(panel.pause_checkbox.mapTo(viewport, QPoint()), panel.pause_checkbox.size())
        checks[name + "_option_reachable"] = viewport.rect().contains(rectangle)
        checks[name + "_footer_visible"] = panel.rect().contains(
            QRect(panel.player_bar.mapTo(panel, QPoint()), panel.player_bar.size()))
        panel.grab().save(str(output / (name + ".png")))
    panel.pause_checkbox.setChecked(True)
    checks["saved_immediately"] = store.load().hide_on_pause
    panel.apply_preset("builtin:quiet")
    checks["preset_preserves_option"] = panel.pause_checkbox.isChecked() and store.load().hide_on_pause
    checks["local_transport_untouched"] = not local.playing and local.path is None

    class PendingExecutor:
        def submit(self, *_args, **_kwargs):
            return Future()  # No threads, cache reads, requests or network traffic.

    document = LyricDocument([
        LyricLine(0, "Every echo has a story.", translation="每一声回响都有一个故事。"),
        LyricLine(2000, "Pause the music, clear the scene.", translation="音乐暂停，歌词隐去。"),
        LyricLine(8000, "Resume at the current position.", translation="继续播放，回到当前进度。"),
    ], [])
    def image(widget):
        return widget.grab().toImage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    def has_pixels(widget):
        frame = image(widget)
        return bool(pixels_view(frame)[:, :, 3].any())
    def ready(widget):
        image(widget)
        deadline = time.monotonic() + 6
        while widget._warm_jobs and time.monotonic() < deadline:
            QTest.qWait(10)

    for source in ("netease", "qqmusic", "kugou"):
        clock = lambda: 100.0
        executor = PendingExecutor()
        if source == "netease":
            player = NeteasePlayer(clock=clock)
            def feed(playing, position):
                player.apply(dict(song=dict(id="demo", title="Pause demo", artist="Demo"),
                    duration_ms=30000, position_ms=position, playing=playing, enabled=True, client="3.1.41"))
        elif source == "qqmusic":
            player = QQMusicPlayer(clock=clock, autostart=False, executor=executor, loader=lambda *_: None)
            def feed(playing, position):
                player.apply_snapshot(QQSnapshot("Pause demo", "Demo", "", 30000, position, playing))
        else:
            player = KugouPlayer(clock=clock, autostart=False, executor=executor, loader=lambda *_: None,
                                 replace_native=False)
            def feed(playing, position):
                player.apply_snapshot(KugouSnapshot("Pause demo", "Demo", "", 30000, position, playing, mode="native"))
        options = Preferences(hide_on_pause=True, extended_display=True, region="full", angle=0,
                              jump=0, motion="wave", lyric_display_mode="bilingual_original",
                              animation_style="ripple_wave", scramble_exit=True, glow_variant="gradient")
        layer = LyricsOverlay(player, options)
        player.document_changed.connect(layer.set_document)
        feed(True, 3500)
        layer.set_document(document)
        layer.show()
        try:
            ready(layer)
            frame = image(layer)
            frame.save(str(output / (source + "-playing.png")))
            checks[source + "_playing_has_pixels"] = bool(pixels_view(frame)[:, :, 3].any())
            surfaces = {key: value.surface for key, value in layer.layouts.items()}
            feed(False, 3500)
            app.processEvents()
            checks[source + "_pause_clears_alpha"] = not has_pixels(layer)
            checks[source + "_pause_stops_work"] = not layer.timer.isActive() and not layer._warm_timer.isActive()
            checks[source + "_window_choice_preserved"] = layer.isVisible()
            QTest.qWait(60)
            checks[source + "_pause_stays_blank"] = not has_pixels(layer) and player.position() == 3500
            feed(True, 3500)
            checks[source + "_resume_same_frame"] = frame == image(layer)
            checks[source + "_resume_reuses_cache"] = all(layer.layouts[key].surface is value for key, value in surfaces.items())
            feed(False, 3500)
            options.hide_on_pause = False
            layer.update()
            checks[source + "_disabled_freezes_frame"] = frame == image(layer)
            options.hide_on_pause = True
            feed(False, 9500)
            layer.set_document(document)
            checks[source + "_paused_seek_and_late_data_blank"] = not has_pixels(layer)
            feed(True, 9500)
            ready(layer)
            checks[source + "_resume_current_progress"] = has_pixels(layer) and player.position() == 9500
            layer.hide()
            feed(False, 9500)
            feed(True, 9500)
            app.processEvents()
            checks[source + "_manual_hide_stays_hidden"] = not layer.isVisible() and not layer.timer.isActive()
        finally:
            layer.hide()
            player.stop()
            layer.deleteLater()
            player.deleteLater()
    panel.tray.hide()
    panel.hide()
    overlay.hide()
    fonts.close()
    result = dict(passed=all(checks.values()), checks=checks, dpr=panel.devicePixelRatioF(),
        app_version=APP_VERSION, kugou_version=KUGOU_VERSION, packaged=bool(getattr(sys, "frozen", False)),
        synthetic_source_packets=True, real_client_pause_verified=False, music_client_commands=0,
        user_settings_modified=False)
    (output / "report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return 0 if result["passed"] else 1


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scale", type=float, choices=(1, 1.25, 1.5), default=1)
    args = parser.parse_args(argv)
    return validate(args.output, args.scale)


if __name__ == "__main__":
    raise SystemExit(main())
