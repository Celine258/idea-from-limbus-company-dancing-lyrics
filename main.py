import argparse
import logging
import os
from pathlib import Path
import sys

if __name__ == "__main__" and sys.argv[1:2] == ["--scramble-smoke"]:
    from tools.validate_scramble_transitions import main as validate_scramble
    raise SystemExit(validate_scramble(sys.argv[2:]))

if __name__ == "__main__" and sys.argv[1:2] == ["--kugou-diagnose"]:
    from kugou_diagnostics import run
    raise SystemExit(run(sys.argv[2:]))

if __name__ == "__main__" and sys.argv[1:2] == ["--kugou-reader"]:
    from kugou_reader import run
    raise SystemExit(run("--once" in sys.argv))

if __name__ == "__main__" and sys.argv[1:] == ["--watch-kugou"]:
    from kugou_startup import run_watcher
    raise SystemExit(run_watcher())

# Login monitoring has no Qt/audio imports and never controls the music client.
if __name__ == "__main__" and sys.argv[1:] == ["--watch-qqmusic"]:
    from qqmusic_startup import run_watcher
    raise SystemExit(run_watcher())

# QAudioBufferOutput requires the FFmpeg backend. Set before importing Qt Multimedia.
os.environ["QT_MEDIA_BACKEND"] = "ffmpeg"
from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QMessageBox
from controls import ControlPanel, app_icon
from overlay import LyricsOverlay
from player import MusicPlayer
from settings import SettingsStore, app_directory, DEFAULT_FONT_FAMILY
from fonts import FontLibrary
from app_info import APP_NAME, APP_VERSION, KUGOU_VERSION, kugou_default_mode, set_taskbar_identity


def main():
    parser = argparse.ArgumentParser(description=f"{APP_NAME} · Windows 桌面音乐伴侣")
    installer = parser.add_mutually_exclusive_group()
    installer.add_argument("--install-kugou", action="store_true", help="为酷狗版创建个人快捷方式")
    installer.add_argument("--uninstall-kugou", action="store_true", help="移除酷狗版快捷方式与自动启动")
    installer.add_argument("--install-netease", action="store_true", help="打开网易云联动安装窗口")
    installer.add_argument("--uninstall-netease", action="store_true", help="打开网易云联动卸载窗口")
    installer.add_argument("--restore-netease", action="store_true", help="恢复本目录上次网易云联动安装")
    parser.add_argument("--experimental-netease", action="store_true", help="允许本次尝试安装未验证的网易云版本，仍保留安全检查")
    parser.add_argument("--client-directory", type=Path, help="网易云安装目录")
    parser.add_argument("--profile-directory", type=Path, help="BetterNCM 数据目录")
    parser.add_argument("--framework-dll", type=Path, help="离线安装的官方 BetterNCM 1.3.4 DLL")
    parser.add_argument("--installer-elevated", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--installer-report", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--demo", action="store_true", help="启动并播放内置合成演示")
    parser.add_argument("--smoke", action="store_true", help="静音执行集成检查并退出")
    sources = parser.add_mutually_exclusive_group()
    sources.add_argument("--netease", action="store_true", help="接收网易云插件的播放和歌词数据")
    sources.add_argument("--qqmusic", action="store_true", help="只读跟随 Windows QQ 音乐播放和歌词")
    sources.add_argument("--kugou", action="store_true", help="酷狗音乐独立联动，无需修改客户端")
    parser.add_argument("--kugou-smoke", action="store_true", help="采集 45 秒真实酷狗联动验证并退出")
    parser.add_argument("--qqmusic-smoke", action="store_true", help="采集真实 QQ 音乐联动验证并退出")
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
    if args.qqmusic_smoke and not args.qqmusic:
        parser.error("--qqmusic-smoke 需要 --qqmusic")
    if args.install_kugou or args.uninstall_kugou:
        from kugou_install import run_installer
        return run_installer(app_directory(), args.uninstall_kugou)
    if args.kugou_smoke and not args.kugou:
        parser.error("--kugou-smoke 需要 --kugou")
    if kugou_default_mode(sys.executable, getattr(sys, "frozen", False), sys.argv[1:]):
        args.kugou = True
    external = args.netease or args.qqmusic or args.kugou
    checking = args.smoke or args.netease_smoke or args.qqmusic_smoke or args.kugou_smoke
    if args.install_netease or args.uninstall_netease or args.restore_netease:
        from installer_ui import run_installer
        from settings import resource_path
        return run_installer(args, app_directory(), resource_path("plugins/netease"))
    state_dir = (Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "DancingLyrics-Kugou" / ".state"
                 if args.kugou else app_directory() / ".state")
    state_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=state_dir / "app.log", level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s", encoding="utf-8")
    logging.info("Starting desktop app; pid=%s; frozen=%s; smoke=%s", os.getpid(),
                 getattr(sys, "frozen", False), args.smoke)
    if not set_taskbar_identity():
        logging.warning("Windows taskbar identity could not be assigned")
    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(KUGOU_VERSION if args.kugou else APP_VERSION)
    app.setOrganizationName("FloatingLyrics")
    app.setWindowIcon(app_icon())
    app.setStyle("Fusion")
    app.setFont(QFont(DEFAULT_FONT_FAMILY, 10))
    app.setQuitOnLastWindowClosed(False)

    qq_mutex = show_event = None
    if args.kugou and not checking and sys.platform == "win32":
        from kugou_startup import NamedMutex, PanelSignal, object_name
        show_event = PanelSignal()
        qq_mutex = NamedMutex(object_name("app"))
        if not qq_mutex.acquired:
            if not args.background:
                show_event.signal()
            show_event.close()
            qq_mutex.close()
            return 0
        app.aboutToQuit.connect(qq_mutex.close)
        app.aboutToQuit.connect(show_event.close)
    if args.qqmusic and not checking and sys.platform == "win32":
        from qqmusic_startup import NamedMutex, ShowPanelEvent, object_name
        show_event = ShowPanelEvent()
        qq_mutex = NamedMutex(object_name("app"))
        if not qq_mutex.acquired:
            if not args.background:
                show_event.signal()
            show_event.close()
            qq_mutex.close()
            return 0
        app.aboutToQuit.connect(qq_mutex.close)
        app.aboutToQuit.connect(show_event.close)

    def exception_hook(error_type, error, traceback):
        logging.error("Unhandled exception", exc_info=(error_type, error, traceback))
        if not args.smoke:
            QMessageBox.critical(None, "运行出现问题", f"{error}\n\n详细信息已保存到：{state_dir / 'app.log'}")
        app.exit(1)

    sys.excepthook = exception_hook
    store = SettingsStore(state_dir / ("smoke-settings.ini" if checking else "settings.ini"))
    prefs = store.load(kugou=args.kugou)
    app.setWindowIcon(app_icon(prefs.theme))
    if args.kugou:
        from kugou import KugouPlayer
        from process_audio import ProcessAudio, window_process_pid
        player = KugouPlayer(cache_directory=prefs.kugou_cache_directory, replace_native=prefs.kugou_replace_native)
        audio = ProcessAudio(player, pid_finder=lambda: window_process_pid("kugou.exe"))
        app.aboutToQuit.connect(audio.close)
    elif args.qqmusic:
        from qqmusic import QQMusicPlayer
        from process_audio import ProcessAudio, qqmusic_pid
        player = QQMusicPlayer(cache_directory=prefs.qq_cache_directory)
        audio = ProcessAudio(player, pid_finder=qqmusic_pid)
        app.aboutToQuit.connect(audio.close)
    elif args.netease:
        from netease import NeteasePlayer, NeteaseBridge, read_bridge_config
        from process_audio import ProcessAudio
        try:
            config = read_bridge_config(state_dir / "netease-bridge.json")
            player = NeteasePlayer()
            from compatibility import bridge_client
            bridge = NeteaseBridge(player, config["token"], allowed_client=bridge_client(config))
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
    fonts = FontLibrary(state_dir / ("smoke-fonts" if checking else "fonts"))
    panel = ControlPanel(player, overlay, prefs, store, font_library=fonts)
    if qq_mutex is not None:
        if args.qqmusic:
            from qqmusic_startup import mark_panel
            mark_panel(int(panel.winId()))
        show_timer = QTimer(panel)
        show_timer.setInterval(100)
        show_timer.timeout.connect(lambda: panel.show_panel() if show_event.consume() else None)
        show_timer.start()
    app.aboutToQuit.connect(lambda: store.save(prefs))
    app.aboutToQuit.connect(player.stop if external else player.media.stop)
    app.aboutToQuit.connect(panel.tray.hide)
    panel.fit_to_screen(app.primaryScreen().availableGeometry())
    overlay.show()
    if args.netease:
        bridge.show_panel.connect(panel.show_effects)
        bridge.enabled_changed.connect(lambda enabled: panel.set_overlay_visible(enabled))
    if not (external and args.background and panel.tray_available):
        panel.show()
    logging.info("Control panel initialized; Qt visible=%s", panel.isVisible())
    if args.kugou_smoke or (args.kugou and args.smoke):
        from kugou_validation import KugouSmokeCheck
        check = KugouSmokeCheck(app, panel, args.report_dir)
    elif args.qqmusic_smoke or (args.qqmusic and args.smoke):
        from qqmusic_validation import QQMusicSmokeCheck
        check = QQMusicSmokeCheck(app, panel, args.report_dir)
    elif args.netease_smoke and args.netease:
        from netease_validation import NeteaseSmokeCheck
        check = NeteaseSmokeCheck(app, panel, args.report_dir, require_settings=args.settings_smoke,
                                 font_fixture=args.font_smoke_file, require_effects=args.effects_smoke,
                                 require_animations=args.animations_smoke, require_singing=args.singing_smoke,
                                 require_translation=args.translation_smoke)
    elif args.smoke and not external:
        from validation import SmokeCheck
        check = SmokeCheck(app, panel, args.report_dir, font_fixture=args.font_smoke_file)
        QTimer.singleShot(200, check.start)
    elif args.demo and not external:
        QTimer.singleShot(200, panel.play_demo)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
