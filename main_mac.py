"""macOS entry, adapted from qingyin-alice-zhong's mac-version (MIT)."""
import argparse
import json
import logging
import os
from pathlib import Path
import sys


def default_state_directory():
    # A signed app bundle must remain immutable; updates must not erase user data.
    if getattr(sys, "frozen", False):
        return Path.home() / "Library" / "Application Support" / "CityEchoes"
    return Path(__file__).parent / ".state"


def main(argv=None):
    parser = argparse.ArgumentParser(description="都市回响 · macOS 实验版")
    parser.add_argument("--local", action="store_true", help="本地音乐与 LRC 模式")
    parser.add_argument("--check", action="store_true", help="检查系统与 nowplaying-cli，不启动窗口")
    parser.add_argument("--state-dir", type=Path, help="自定义设置目录；默认项目目录中的 .state")
    parser.add_argument("--smoke", action="store_true", help="隔离的静音打包验证（模拟播放信息）")
    parser.add_argument("--report-dir", type=Path, help="静音验证报告目录")
    args = parser.parse_args(argv)
    if args.smoke and (args.local or not args.state_dir or not args.report_dir):
        parser.error("--smoke 需要独立的 --state-dir 和 --report-dir，且不能与 --local 同用")
    if sys.platform != "darwin":
        print("main_mac.py 仅用于 macOS；Windows 请使用启动.bat。", file=sys.stderr)
        return 2
    os.environ["QT_MEDIA_BACKEND"] = "ffmpeg"
    from macos_netease import MacNeteasePlayer, OffsetStore, find_nowplaying_cli
    if args.check:
        cli = find_nowplaying_cli()
        print(json.dumps({"platform": sys.platform, "nowplaying_cli": cli,
                          "ready": bool(cli), "live_playback_verified": False}, ensure_ascii=False))
        return 0 if cli else 1
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont, QKeySequence, QShortcut
    from PySide6.QtWidgets import QApplication, QMessageBox
    from app_info import APP_NAME, APP_VERSION
    from controls import ControlPanel, app_icon
    from fonts import FontLibrary
    from overlay import LyricsOverlay
    from settings import DEFAULT_FONT_FAMILY, SettingsStore, app_directory

    state_dir = args.state_dir or default_state_directory()
    state_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=state_dir / "app.log", level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s", encoding="utf-8")
    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("FloatingLyrics")
    app.setStyle("Fusion")
    app.setFont(QFont(DEFAULT_FONT_FAMILY, 10))
    app.setQuitOnLastWindowClosed(False)

    def exception_hook(kind, error, traceback):
        logging.error("Unhandled exception", exc_info=(kind, error, traceback))
        QMessageBox.critical(None, "运行出现问题", f"{error}\n\n日志：{state_dir / 'app.log'}")
        app.exit(1)
    sys.excepthook = exception_hook
    store = SettingsStore(state_dir / "settings.ini")
    prefs = store.load()
    if not store.store.contains("motion"):
        prefs.motion = "wave"  # No real process audio capture on macOS yet.
    app.setWindowIcon(app_icon(prefs.theme))
    if args.local:
        from player import MusicPlayer
        player = MusicPlayer()
    else:
        player = MacNeteasePlayer(autostart=not args.smoke)
        player.set_offset_store(OffsetStore(state_dir / "offsets.json"))
    overlay = LyricsOverlay(player, prefs)
    library = FontLibrary(state_dir / "fonts")
    panel = ControlPanel(player, overlay, prefs, store, font_library=library)
    shortcuts = []
    if not args.local:
        player.offset_changed.connect(overlay.refresh_preferences)
        for sequence, delta in (("Ctrl+Alt+Up", 200), ("Ctrl+Alt+Down", -200)):
            shortcut = QShortcut(QKeySequence(sequence), panel)
            shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
            shortcut.activated.connect(lambda step=delta: player.adjust_offset(step))
            shortcuts.append(shortcut)
        panel.source_label.setText("请打开网易云 Mac 版；⌘⌥↑ / ⌘⌥↓ 微调歌词偏移。")
        if player._offset_store.error:
            panel.show_notice(player._offset_store.error)
    app.aboutToQuit.connect(lambda: store.save(prefs))
    app.aboutToQuit.connect(player.media.stop if args.local else player.stop)
    app.aboutToQuit.connect(panel.tray.hide)
    app.aboutToQuit.connect(library.close)
    panel.fit_to_screen(app.primaryScreen().availableGeometry())
    overlay.show()
    panel.show()
    if args.smoke:
        from macos_smoke import schedule_smoke
        schedule_smoke(app, panel, overlay, player, store, args.report_dir)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
