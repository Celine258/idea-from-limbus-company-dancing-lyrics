"""Native topmost recovery against another process; no music-client control."""
import argparse
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def validate(output):
    os.environ.pop('QT_QPA_PLATFORM', None)
    from PySide6.QtCore import QObject, Signal
    from PySide6.QtWidgets import QApplication
    from PySide6.QtTest import QTest
    from overlay import LyricsOverlay
    from settings import Preferences
    app = QApplication([])
    class Player(QObject):
        changed, discontinuity = Signal(), Signal()
        playing, ended, duration = False, False, 10000
        def position(self): return 1000
        def energy_at(self, _): return 0
    output.mkdir(parents=True, exist_ok=False)
    player = Player()
    overlay = LyricsOverlay(player, Preferences())
    backend = overlay._layer.backend
    assert backend is not None
    user = backend.user
    checks = {'native_windows': app.platformName() == 'windows'}
    dummy = output / 'foreign-window.json'
    script = """import json,sys
from PySide6.QtCore import Qt,QTimer
from PySide6.QtWidgets import QApplication,QWidget
from pathlib import Path
app=QApplication([])
window=QWidget(None,Qt.WindowType.WindowStaysOnTopHint|Qt.WindowType.FramelessWindowHint)
window.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
window.setWindowTitle('Lyric layer test window')
window.setGeometry(100,100,900,500)
window.show()
app.processEvents()
Path(sys.argv[1]).write_text(json.dumps({'hwnd':int(window.winId())}))
trigger=Path(sys.argv[1]).with_suffix('.raise')
def raise_requested():
    if trigger.exists():
        trigger.unlink()
        window.raise_()
        Path(sys.argv[1]).with_suffix('.raised').write_text('done')
poll=QTimer();poll.setInterval(20);poll.timeout.connect(raise_requested);poll.start()
QTimer.singleShot(30000,app.quit)
app.exec()
"""
    process = None
    try:
        overlay.show()
        QTest.qWait(100)
        hwnd = int(overlay.winId())
        foreground = user.GetForegroundWindow()
        checks['shown_topmost'] = bool(user.GetWindowLongW(hwnd, -20) & 8)
        checks['shown_noactivate'] = bool(user.GetWindowLongW(hwnd, -20) & 0x08000000)
        process = subprocess.Popen([sys.executable, '-c', script, str(dummy)], creationflags=0x08000000)
        for _ in range(100):
            if dummy.exists(): break
            QTest.qWait(50)
        foreign = json.loads(dummy.read_text())['hwnd']
        QTest.qWait(200)
        # Suppress repair briefly to prove that this foreign topmost window can cover us.
        overlay._layer.stop()
        user.SetWindowPos(foreign, -1, 0, 0, 0, 0, 0x213)
        checks['foreign_cover_reproduced'] = backend.needs_repair(hwnd, foreign)
        overlay._layer.start()
        # Raise from the foreign process itself: SKIPOWNPROCESS correctly skips
        # events caused by this controller, even when they name a foreign HWND.
        dummy.with_suffix('.raise').write_text('raise')
        QTest.qWait(450)
        checks['foreign_process_raised_itself'] = dummy.with_suffix('.raised').exists()
        checks['foreign_reorder_recovered'] = not backend.needs_repair(hwnd, foreign)
        checks['focus_preserved'] = user.GetForegroundWindow() == foreground
        user.SetWindowPos(hwnd, -2, 0, 0, 0, 0, 0x213)
        checks['lost_native_style_reproduced'] = not bool(user.GetWindowLongW(hwnd, -20) & 8)
        QTest.qWait(1250)
        checks['lost_native_style_recovered'] = bool(user.GetWindowLongW(hwnd, -20) & 8)
        checks['paused_render_timer_still_stopped'] = not overlay.timer.isActive()
        overlay.hide()
        checks['hidden_repair_stopped'] = (not overlay._layer.running and
            not overlay._layer.pending.isActive() and not overlay._layer.watchdog.isActive() and not backend.hooks)
        QTest.qWait(100)
        checks['hidden_stays_hidden'] = not user.IsWindowVisible(hwnd)
        overlay.show()
        QTest.qWait(100)
        checks['restored_topmost'] = bool(user.GetWindowLongW(int(overlay.winId()), -20) & 8)
        checks['restore_keeps_focus'] = user.GetForegroundWindow() == foreground
    finally:
        overlay.hide()
        if process:
            process.terminate()
            process.wait(timeout=5)
    report = dict(passed=all(checks.values()), checks=checks, foreign_window_is_fixture=True,
                  actual_exclusive_fullscreen_game_verified=False, music_client_commands=0)
    (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    raise SystemExit(validate(parser.parse_args().output))
