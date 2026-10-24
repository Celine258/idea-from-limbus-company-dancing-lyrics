"""Measure native frame pacing through cold, overlapping lyric transitions.

Uses a labelled monotonic demo clock; never opens or controls a music client,
loads personal settings, or substitutes steady warm rendering for cold work.
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
    native_scale = ctypes.windll.shcore.GetScaleFactorForDevice(0) / 100
    os.environ["QT_SCALE_FACTOR"] = str(scale / native_scale)
    os.environ["QT_SCALE_FACTOR_ROUNDING_POLICY"] = "PassThrough"
    os.environ.pop("QT_SCREEN_SCALE_FACTORS", None)
    import numpy as np
    from PySide6.QtCore import QObject, Signal, QTimer, QEventLoop
    from PySide6.QtWidgets import QApplication
    from overlay import LyricsOverlay
    from settings import Preferences, ANIMATION_STYLES
    from lrc import LyricDocument, LyricLine
    from text_effects import TEXT_EFFECTS

    output.mkdir(parents=True, exist_ok=False)
    app = QApplication([])

    class Clock(QObject):
        changed, discontinuity = Signal(), Signal()
        playing, ended, duration, epoch = True, False, 5000, 0
        def position(self):
            return (time.perf_counter() - self.epoch) * 1000 if self.epoch else 0
        def energy_at(self, _):
            return .5

    class Probe(LyricsOverlay):
        def __init__(self, *args):
            self.paints, self.warm_steps, self.exit_frames = [], [], []
            super().__init__(*args)
        def paintEvent(self, event):
            began = time.perf_counter()
            position = self.player.position()
            active = self.timeline.visible(position, self.player.duration) if self.timeline else []
            super().paintEvent(event)
            self.paints.append((time.perf_counter() - began) * 1000)
            if any(item.exit_start_ms < position < item.end_ms for item in active):
                self.exit_frames.append(position)
        def _warm_step(self):
            began = time.perf_counter()
            super()._warm_step()
            self.warm_steps.append((time.perf_counter() - began) * 1000)

    text = "In the quiet city we follow every echo through the night and find another morning."
    translation = "在寂静的都市里，我们循着回响穿过长夜，迎接下一个清晨。"
    results, checks = [], {"native_windows": app.platformName() == "windows"}
    for index, style in enumerate(ANIMATION_STYLES):
        bilingual = style.endswith("shake")
        prefs = Preferences(animation_style=style, scramble_exit=True, glow_variant="gradient",
                            font_size=64 if index % 2 == 0 else 32,
                            region="edges" if bilingual else "full",
                            lyric_display_mode="bilingual_original" if bilingual else "original")
        player = Clock()
        overlay = Probe(player, prefs)
        document = LyricDocument([LyricLine(start, phrase, translation=translation if bilingual else "")
                                  for start, phrase in ((100, text), (1500, "Again: " + text),
                                                        (2900, "Tonight: " + text), (4300, ""))], [])
        TEXT_EFFECTS.clear()
        overlay.set_document(document)
        heartbeats = []
        heartbeat = QTimer()
        heartbeat.setInterval(10)
        heartbeat.timeout.connect(lambda: heartbeats.append(time.perf_counter()))
        loop = QEventLoop()
        player.epoch = time.perf_counter()
        overlay.show()
        heartbeat.start()
        QTimer.singleShot(4450, loop.quit)
        loop.exec()
        heartbeat.stop()
        final_position = player.position()
        overlay.timer.stop()
        overlay.grab().save(str(output / (style + "-cleared.png")))
        active_exit_counts = [sum(start <= position < start + 600 for position in overlay.exit_frames)
                              for start in (1500, 2900)]
        gaps = np.diff(heartbeats) * 1000
        metrics = dict(style=style, font_size=prefs.font_size, bilingual=bilingual,
                       dpr=overlay.devicePixelRatioF(), frames=len(overlay.paints),
                       paint_p95_ms=round(float(np.percentile(overlay.paints, 95)), 3),
                       paint_max_ms=round(max(overlay.paints), 3),
                       preparation_max_ms=round(max(overlay.warm_steps, default=0), 3),
                       heartbeat_p95_ms=round(float(np.percentile(gaps, 95)), 3),
                       heartbeat_max_ms=round(float(max(gaps)), 3),
                       transition_exit_frames=active_exit_counts,
                       final_position=round(final_position), pending_jobs=len(overlay._warm_jobs))
        checks[style + "_native_visible"] = bool(ctypes.windll.user32.IsWindowVisible(int(overlay.winId())))
        checks[style + "_requested_dpr"] = abs(metrics["dpr"] - scale) < .01
        checks[style + "_paint_p95_under_33ms"] = metrics["paint_p95_ms"] <= 33
        checks[style + "_preparation_step_under_33ms"] = metrics["preparation_max_ms"] <= 33
        checks[style + "_no_100ms_event_loop_stall"] = metrics["heartbeat_max_ms"] < 100
        checks[style + "_both_exits_have_multiple_frames"] = min(active_exit_counts) >= 5
        checks[style + "_blank_boundary_clears"] = not overlay.timeline.visible(final_position, player.duration)
        results.append(metrics)
        overlay.hide()
        overlay.deleteLater()
        app.processEvents()
        print(json.dumps(metrics), flush=True)
    report = dict(passed=all(checks.values()), checks=checks, measurements=results,
                  synthetic_clock=True, real_music_playback_verified=False,
                  music_client_commands=0, user_settings_modified=False)
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "checks": checks}), flush=True)
    return 0 if report["passed"] else 1


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scale", type=float, default=1.5)
    args = parser.parse_args(argv)
    return validate(args.output, args.scale)


if __name__ == "__main__":
    raise SystemExit(main())
