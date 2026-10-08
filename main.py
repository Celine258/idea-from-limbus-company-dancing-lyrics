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
from fonts import FontLibrary
from app_info import APP_NAME, APP_VERSION, set_taskbar_identity


def main():
    parser = argparse.ArgumentParser(description=f"{APP_NAME} · Windows 桌面音乐伴侣")
    installer = parser.add_mutually_exclusive_group()
    installer.add_argument("--install-netease", action="store_true", help="打开网易云联动安装窗口")
    installer.add_argument("--uninstall-netease", action="store_true", help="打开网易云联动卸载窗口")
    parser.add_argument("--client-directory", type=Path, help="网易云安装目录")
    parser.add_argument("--profile-directory", type=Path, help="BetterNCM 数据目录")
    parser.add_argument("--framework-dll", type=Path, help="离线安装的官方 BetterNCM 1.3.4 DLL")
    parser.add_argument("--installer-elevated", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--installer-report", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--demo", action="store_true", help="启动并播放内置合成演示")
    parser.add_argument("--smoke", action="store_true", help="静音执行集成检查并退出")
    parser.add_argument("--netease", action="store_true", help="接收网易云插件的播放和歌词数据")
    parser.add_argument("--background", action="store_true", help="联动模式启动到托盘")
    parser.add_argument("--netease-smoke", action="store_true", help="采集 45 秒真实网易云联动验证并退出")
    parser.add_argument("--settings-smoke", action="store_true", help="联动验证同时要求实际打开歌词效果窗口")
    parser.add_argument("--effects-smoke", action="store_true", help="联动验证同时检查发光样式、设置及绘制性能")
    parser.add_argument("--animations-smoke", action="store_true", help="联动验证同时检查四种逐字动画及性能")
    parser.add_argument("--singing-smoke", action="store_true", help="联动验证同时检查逐字时间、演唱强调与预设")
    parser.add_argument("--translation-smoke", action="store_true", help="联动验证要求真实中文译文和语言切换不改变播放")
    parser.add_argument("--font-smoke-file", type=Path, help="本地或网易云验证时用于测试导入的字体文件")
    parser.add_argument("--report-dir", type=Path, default=app_directory() / "artifacts")
    args = parser.parse_args()
    if args.install_netease or args.uninstall_netease:
        from installer_ui import run_installer
        from settings import resource_path
        return run_installer(args, app_directory(), resource_path("plugins/netease"))
    state_dir = app_directory() / ".state"
    state_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=state_dir / "app.log", level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s", encoding="utf-8")
    logging.info("Starting desktop app; pid=%s; frozen=%s; smoke=%s", os.getpid(),
                 getattr(sys, "frozen", False), args.smoke)
    if not set_taskbar_identity():
        logging.warning("Windows taskbar identity could not be assigned")
    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
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
    app.setWindowIcon(app_icon(prefs.theme))
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
    fonts = FontLibrary(state_dir / ("smoke-fonts" if args.smoke or args.netease_smoke else "fonts"))
    panel = ControlPanel(player, overlay, prefs, store, font_library=fonts)
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
        check = NeteaseSmokeCheck(app, panel, args.report_dir, require_settings=args.settings_smoke,
                                 font_fixture=args.font_smoke_file, require_effects=args.effects_smoke,
                                 require_animations=args.animations_smoke, require_singing=args.singing_smoke,
                                 require_translation=args.translation_smoke)
    elif args.smoke and not args.netease:
        from validation import SmokeCheck
        check = SmokeCheck(app, panel, args.report_dir, font_fixture=args.font_smoke_file)
        QTimer.singleShot(200, check.start)
    elif args.demo and not args.netease:
        QTimer.singleShot(200, panel.play_demo)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
