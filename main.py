import argparse
import logging
import os
from pathlib import Path
import sys

# QAudioBufferOutput requires the FFmpeg backend. Set before importing Qt Multimedia.
os.environ["QT_MEDIA_BACKEND"] = "ffmpeg"
from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QMessageBox
from controls import ControlPanel, app_icon
from overlay import LyricsOverlay
from player import MusicPlayer
from settings import SettingsStore, app_directory


def main():
    parser = argparse.ArgumentParser(description="跳动的歌词 · Windows 桌面音乐伴侣")
    parser.add_argument("--demo", action="store_true", help="启动并播放内置合成演示")
    parser.add_argument("--smoke", action="store_true", help="静音执行集成检查并退出")
    parser.add_argument("--report-dir", type=Path, default=app_directory() / "artifacts")
    args = parser.parse_args()
    state_dir = app_directory() / ".state"
    state_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=state_dir / "app.log", level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s", encoding="utf-8")
    logging.info("Starting desktop app; pid=%s; frozen=%s; smoke=%s", os.getpid(),
                 getattr(sys, "frozen", False), args.smoke)
    app = QApplication(sys.argv[:1])
    app.setApplicationName("跳动的歌词")
    app.setOrganizationName("FloatingLyrics")
    app.setWindowIcon(app_icon())
    app.setStyle("Fusion")
    app.setFont(QFont("Microsoft YaHei UI", 10))
    app.setQuitOnLastWindowClosed(False)

    def exception_hook(error_type, error, traceback):
        logging.error("Unhandled exception", exc_info=(error_type, error, traceback))
        if not args.smoke:
            QMessageBox.critical(None, "运行出现问题", f"{error}\n\n详细信息已保存到：{state_dir / 'app.log'}")
        app.exit(1)

    sys.excepthook = exception_hook
    store = SettingsStore(state_dir / ("smoke-settings.ini" if args.smoke else "settings.ini"))
    prefs = store.load()
    player = MusicPlayer()
    overlay = LyricsOverlay(player, prefs)
    panel = ControlPanel(player, overlay, prefs, store)
    app.aboutToQuit.connect(lambda: store.save(prefs))
    app.aboutToQuit.connect(player.media.stop)
    app.aboutToQuit.connect(panel.tray.hide)
    panel.fit_to_screen(app.primaryScreen().availableGeometry())
    overlay.show()
    panel.show()
    logging.info("Control panel initialized; Qt visible=%s", panel.isVisible())
    if args.smoke:
        from validation import SmokeCheck
        check = SmokeCheck(app, panel, args.report_dir)
        QTimer.singleShot(200, check.start)
    elif args.demo:
        QTimer.singleShot(200, panel.play_demo)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
