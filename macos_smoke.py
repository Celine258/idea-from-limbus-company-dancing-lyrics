"""Frozen macOS startup probe; isolated simulated media, never controls NetEase."""
import json
from pathlib import Path
import sys
import traceback
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from app_info import APP_VERSION, EFFECT_PREVIEW_TEXT
from lrc import LyricDocument, LyricLine
from macos_netease import NowPlaying
from settings import resource_path


def schedule_smoke(app, panel, overlay, player, store, report_dir):
    report_dir = Path(report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    player.apply(NowPlaying("paused", "打包启动验证（模拟）", "都市回响", 60000, 1000))
    player.lyrics_received = True
    player.document_changed.emit(LyricDocument([LyricLine(0, EFFECT_PREVIEW_TEXT), LyricLine(5000, "")], []))
    panel.show_effects()

    def finish():
        report = {"passed": False, "version": APP_VERSION, "frozen": bool(getattr(sys, "frozen", False)),
                  "qt_platform": QApplication.platformName(), "live_playback_verified": False,
                  "state_dir": str(Path(store.store.fileName()).parent)}
        try:
            report["panel_visible"] = panel.isVisible() and panel.windowHandle().isExposed()
            report["overlay_visible"] = overlay.isVisible()
            report["assets_present"] = all(resource_path("assets/" + name).is_file()
                for name in ("dante-clock.svg", "special-blueprint.svg", "check-white.svg"))
            panel.theme_combo.setCurrentIndex(panel.theme_combo.findData("dark"))
            report["dark_theme"] = panel.prefs.theme == "dark"
            report["pause_frozen"] = not player.playing and player.position() == 1000
            store.save(panel.prefs)
            report["settings_saved"] = store.load().theme == "dark"
            report["screenshot"] = panel.grab().save(str(report_dir / "macos-panel.png"))
            report["passed"] = all(report[key] for key in ("panel_visible", "overlay_visible", "assets_present",
                "dark_theme", "pause_frozen", "settings_saved", "screenshot"))
        except Exception:
            report["error"] = traceback.format_exc()
        (report_dir / "smoke-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        app.exit(0 if report["passed"] else 1)

    QTimer.singleShot(1500, finish)
