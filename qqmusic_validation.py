"""Capture actual QQ snapshots and windows; never substitute demonstration lyrics."""
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import time

from PySide6.QtCore import QTimer
from process_audio import qqmusic_pid


class QQMusicSmokeCheck:
    def __init__(self, app, panel, directory):
        self.app, self.panel, self.player = app, panel, panel.player
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.started = time.monotonic()
        self.samples = []
        self.effect_check = None
        self.captured = False
        self.timer = QTimer(panel)
        self.timer.setInterval(200)
        self.timer.timeout.connect(self._sample)
        self.timer.start()

    def _sample(self):
        p, panel = self.player, self.panel
        doc = panel.overlay.document
        sample = dict(seconds=round(time.monotonic()-self.started,2),connected=p.connected,
                      song=p.song_id,playing=p.playing,position=round(p.position(),2),
                      lyricCount=len(doc.lines) if doc else 0,energy=p.has_audio_data)
        self.samples.append(sample)
        if doc and self.effect_check is None:
            before = (p.song_id, p._anchor, p.playing, p.duration)
            original = panel.prefs.animation_style
            for style in ("ripple_wave","ripple_shake","fall_wave","fall_shake",original):
                panel.animation_combo.setCurrentIndex(panel.animation_combo.findData(style))
            old = panel.translation_checkbox.isChecked()
            panel.translation_checkbox.setChecked(not old)
            panel.translation_checkbox.setChecked(old)
            self.effect_check = before == (p.song_id, p._anchor, p.playing, p.duration)
            panel.grab().save(str(self.directory/"qqmusic-panel.png"))
            panel.show_effects()
            panel.grab().save(str(self.directory/"qqmusic-effects.png"))
            self.captured = True
        if time.monotonic() - self.started >= 45:
            self.finish()

    def finish(self):
        self.timer.stop()
        user = ctypes.windll.user32
        user.IsWindowVisible.argtypes = [wintypes.HWND]
        native_visible = bool(user.IsWindowVisible(int(self.panel.winId())))
        # A seek while paused is legitimate; require a stable >=1s paused segment,
        # rather than treating every paused position correction as animation drift.
        pauses = [self.samples[i:i+6] for i in range(len(self.samples)-5)]
        pause_frozen = any(all(s['connected'] and not s['playing'] and s['song']==group[0]['song'] for s in group)
                           and group[-1]['seconds']-group[0]['seconds'] >= .9
                           and max(s['position'] for s in group)-min(s['position'] for s in group)<3
                           for group in pauses)
        advances = [(a,b) for a,b in zip(self.samples,self.samples[1:])
                    if a['playing'] and b['playing'] and a['song']==b['song'] and 50 < b['position']-a['position'] < 600]
        checks = dict(nativeWindowVisible=native_visible,qqProcessFound=bool(qqmusic_pid()),
                      connected=any(s['connected'] for s in self.samples),
                      realLyricsReceived=any(s['lyricCount'] for s in self.samples),
                      effectsKeepTransport=self.effect_check is True,
                      pausedPositionFrozen=pause_frozen)
        report = dict(passed=all(checks.values()),checks=checks,samples=self.samples,
                      playbackAdvanceObserved=bool(advances),
                      note="Only actual QQ data. Playback/seek/switch actions are recorded separately.")
        (self.directory/'qqmusic-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        self.app.exit(0 if report['passed'] else 1)
