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
    parser.add_argument("--netease", action="store_true", help="接收网易云插件的播放和歌词数据")
    parser.add_argument("--background", action="store_true", help="联动模式启动到托盘")
    parser.add_argument("--netease-smoke", action="store_true", help="采集 45 秒真实网易云联动验证并退出")
    parser.add_argument("--settings-smoke", action="store_true", help="联动验证同时要求实际打开歌词效果窗口")
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
    store = SettingsStore(state_dir / ("smoke-settings.ini" if args.smoke or args.netease_smoke else "settings.ini"))
    prefs = store.load()
    if args.netease:
        from netease import NeteasePlayer, NeteaseBridge, read_bridge_config
        from process_audio import ProcessAudio
        try:
            config = read_bridge_config(state_dir / "netease-bridge.json")
            player = NeteasePlayer()
            bridge = NeteaseBridge(player, config["token"])
            bridge.start()
        except (ValueError, RuntimeError, OSError) as error:
            QMessageBox.critical(None, "网易云联动", str(error))
            return 1
        audio = ProcessAudio(player)
        app.aboutToQuit.connect(audio.close)
        app.aboutToQuit.connect(bridge.close)
    else:
        player = MusicPlayer()
    overlay = LyricsOverlay(player, prefs)
    panel = ControlPanel(player, overlay, prefs, store)
    app.aboutToQuit.connect(lambda: store.save(prefs))
    app.aboutToQuit.connect(player.stop if args.netease else player.media.stop)
    app.aboutToQuit.connect(panel.tray.hide)
    panel.fit_to_screen(app.primaryScreen().availableGeometry())
    overlay.show()
    if args.netease:
        bridge.show_panel.connect(panel.show_effects)
        bridge.enabled_changed.connect(lambda enabled: panel.set_overlay_visible(enabled))
    if not (args.netease and args.background and panel.tray_available):
        panel.show()
    logging.info("Control panel initialized; Qt visible=%s", panel.isVisible())
    if args.netease_smoke and args.netease:
        from netease_validation import NeteaseSmokeCheck
        check = NeteaseSmokeCheck(app, panel, args.report_dir, require_settings=args.settings_smoke)
    elif args.smoke and not args.netease:
        from validation import SmokeCheck
        check = SmokeCheck(app, panel, args.report_dir)
        QTimer.singleShot(200, check.start)
    elif args.demo and not args.netease:
        QTimer.singleShot(200, panel.play_demo)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
