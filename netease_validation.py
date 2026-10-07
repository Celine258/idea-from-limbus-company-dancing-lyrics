"""Collect real client evidence. Requires the plugin and actual NetEase actions."""
import ctypes
import json
from pathlib import Path
import time
from PySide6.QtCore import QTimer
from process_audio import netease_pid
from PySide6.QtGui import QFontInfo
from fonts import FontLibrary, PRESET_FONTS, lyric_font


class NeteaseSmokeCheck:
    def __init__(self, app, panel, directory, require_settings=False, font_fixture=None, require_effects=False,
                 require_animations=False, require_singing=False):
        self.app, self.panel, self.player = app, panel, panel.player
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.started = time.monotonic()
        self.samples = []
        self.saved = False
        self.require_settings = require_settings
        self.settings_opened = False
        self.font_fixture = font_fixture
        self.font_checks = {}
        self.font_evidence = {}
        self.require_effects = require_effects
        self.effect_checks = {}
        self.effect_evidence = {}
        self.require_animations = require_animations
        self.animation_checks = {}
        self.animation_evidence = {}
        self.original_animation = panel.prefs.animation_style
        self.require_singing = require_singing
        self.singing_checks = {}
        self.original_singing = panel.prefs.singing_sync
        self.jumps = 0
        self.player.discontinuity.connect(self._jump)
        self.timer = QTimer(panel)
        self.timer.setInterval(200)
        self.timer.timeout.connect(self._sample)
        self.timer.start()

    def _jump(self):
        self.jumps += 1

    def _sample(self):
        panel, player = self.panel, self.player
        pid = netease_pid()
        minimized = False
        if pid:
            from ctypes import wintypes
            callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            user = ctypes.windll.user32
            user.IsIconic.argtypes = [wintypes.HWND]
            user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
            @callback_type
            def visit(hwnd, _):
                nonlocal minimized
                found = wintypes.DWORD()
                user.GetWindowThreadProcessId(hwnd, ctypes.byref(found))
                if found.value == pid and user.IsIconic(hwnd):
                    minimized = True
                return True
            user.EnumWindows(visit, 0)
        overlay = panel.overlay
        settings_visible = False
        if panel.pages.currentIndex() == 1 and panel.isVisible():
            from ctypes import wintypes
            user = ctypes.windll.user32
            user.IsWindowVisible.argtypes = [wintypes.HWND]
            settings_visible = bool(user.IsWindowVisible(int(panel.winId())))
            if settings_visible and not self.settings_opened:
                panel.grab().save(str(self.directory / "netease-settings.png"))
                self.settings_opened = True
        document = overlay.document
        active = overlay.timeline.visible(player.position(), player.duration) if overlay.timeline else []
        if self.font_fixture and not self.font_checks and settings_visible and player.playing and active:
            self._check_fonts()
        if self.require_effects and not self.effect_checks and settings_visible and player.playing and active:
            self._check_effects()
        if self.require_animations and not self.animation_checks and settings_visible and player.playing and active:
            self._check_animations()
        if self.require_singing and not self.singing_checks and settings_visible and player.playing and active:
            self._check_singing()
        sample = {"seconds": round(time.monotonic()-self.started, 2), "connected": player.connected,
                  "song": player.song_id, "playing": player.playing, "position": round(player.position(), 1),
                  "lyricCount": len(document.lines) if document else 0, "activeCount": len(active),
                  "energy": round(player.energy_at(player.position()), 4), "minimized": minimized,
                  "overlayVisible": overlay.isVisible(), "overlayTimer": overlay.timer.isActive(), "settingsVisible": settings_visible,
                  "overlayHash": overlay.grab().toImage().cacheKey() if not player.playing else 0}
        if self.require_singing:
            from glyph_motion import glyph_states
            sample["timedLines"] = sum(bool(line.words) for line in document.lines) if document else 0
            sample["wordStatus"] = panel.word_status.text()
            sample["singingEnabled"] = panel.prefs.singing_sync
            sample["emphasis"] = max((state.emphasis for item in active for layout in [overlay.layouts.get(item.index)]
                if layout for state in glyph_states(layout.glyphs, panel.prefs, item, player.position(), 0, layout.font_size)), default=0)
            if sample["emphasis"] > 0 and not (self.directory / "netease-singing-overlay.png").exists():
                overlay.grab().save(str(self.directory / "netease-singing-overlay.png"))
        # cacheKey changes per grab; compare pixel bytes for pause verification instead.
        if not player.playing and player.connected:
            picture = overlay.grab().toImage()
            import hashlib
            sample["overlayHash"] = hashlib.sha256(bytes(picture.constBits())).hexdigest()
        self.samples.append(sample)
        if player.connected and document and active and not self.saved:
            if not self.require_settings:
                panel.show()
            panel.grab().save(str(self.directory / "netease-panel.png"))
            overlay.grab().save(str(self.directory / "netease-overlay.png"))
            self.saved = True
        if sample["seconds"] >= (75 if self.require_singing else 45):
            self.finish()

    def _check_fonts(self):
        panel, player = self.panel, self.player
        original, position = panel.prefs.font_family, player.position()
        transport = (player._anchor, player._at, player.song_id, player.playing, self.jumps)
        started = time.monotonic()
        matches = []
        for _, family in PRESET_FONTS:
            panel.font_combo.setCurrentIndex(panel.font_combo.findData(family))
            matches.append(QFontInfo(lyric_font(panel.prefs.font_family, 32)).family() == family)
            panel.grab().save(str(self.directory / f"netease-font-{family.replace(' ', '-')}.png"))
        imported = panel.import_font(self.font_fixture)
        selected = panel.prefs.font_family
        restored = FontLibrary(panel.font_library.directory)
        try:
            persistent = imported and panel.store.load().font_family == selected and restored.restore_family(selected)[0] == selected
        finally:
            restored.close()
        panel.font_combo.setCurrentIndex(panel.font_combo.findData(original))
        unchanged = transport == (player._anchor, player._at, player.song_id, player.playing, self.jumps)
        self.font_evidence = {"elapsedMs": round((time.monotonic() - started) * 1000, 1),
                              "positionDeltaMs": round(player.position() - position, 1), "transportUnchanged": unchanged}
        self.font_checks = {"fontPresetsResolve": all(matches), "fontImportPersists": persistent,
                            "fontSwitchKeepsPlayback": player.playing and unchanged}

    def _check_effects(self):
        from effect_validation import validate_effects
        panel, player = self.panel, self.player
        original = (panel.prefs.text_style, panel.prefs.glow_strength, panel.preview_background.currentIndex())
        transport = (player._anchor, player._at, player.song_id, player.playing, self.jumps)
        for style in ("solid", "glow"):
            panel.text_style.setCurrentIndex(panel.text_style.findData(style))
            panel.glow_slider.setValue(80)
            panel.font_preview.grab().save(str(self.directory / f"netease-effect-{style}.png"))
        saved = panel.store.load()
        self.effect_checks["effectSettingsPersist"] = saved.text_style == "glow" and saved.glow_strength == 80
        for index, name in enumerate(("dark", "light")):
            panel.preview_background.setCurrentIndex(index)
            panel.font_preview.grab().save(str(self.directory / f"netease-preview-{name}.png"))
        result = validate_effects(self.directory, panel.prefs, panel.devicePixelRatioF())
        self.effect_evidence = result.pop("effect_benchmark")
        self.effect_checks.update(result)
        panel.text_style.setCurrentIndex(panel.text_style.findData(original[0]))
        panel.glow_slider.setValue(original[1])
        panel.preview_background.setCurrentIndex(original[2])
        self.effect_checks["effectChangesKeepTransport"] = transport == (player._anchor, player._at, player.song_id, player.playing, self.jumps)

    def finish(self):
        self.timer.stop()
        samples = self.samples
        paused = any(all(not x["playing"] and x["connected"] for x in samples[i:i+5]) and
                     len({x["position"] for x in samples[i:i+5]}) == 1 and
                     len({x["overlayHash"] for x in samples[i:i+5]}) == 1
                     for i in range(max(0,len(samples)-4)))
        minimized = any(a["minimized"] and b["minimized"] and a["playing"] and b["playing"] and
                        a["song"] == b["song"] and b["position"]-a["position"] > 800
                        for a,b in zip(samples,samples[5:]))
        connected = [x for x in samples if x["connected"]]
        checks = {"realSong": any(x["song"] for x in connected),
                  "lyricsReceived": any(x["lyricCount"] > 0 for x in connected),
                  "visibleLyricFrame": self.saved, "pauseFreezesPositionAndImage": paused,
                  "seekObserved": self.jumps > 1, "minimizedPlaybackAdvances": minimized,
                  "processAudioEnergy": max((x["energy"] for x in connected), default=0) > .03,
                  "disconnectClearsLyrics": any(not x["connected"] and x["lyricCount"]==0 for x in samples[len(samples)//2:]),
                  "noSecondAudioPlayer": not hasattr(self.player,"media")}
        if self.require_settings:
            checks["nativeEffectsSettingsOpened"] = self.settings_opened
        if self.font_fixture:
            checks.update(self.font_checks or {"fontPresetsResolve": False, "fontImportPersists": False,
                                              "fontSwitchKeepsPlayback": False})
        if self.require_effects:
            checks.update(self.effect_checks or {"effectSettingsPersist": False, "effectChangesKeepTransport": False})
        if self.require_animations:
            checks.update(self.animation_checks or {"animationSettingsPersist": False, "animationChangesKeepTransport": False})
        if self.require_singing:
            checks.update(self.singing_checks or {"singingSwitchKeepsTransport": False})
            checks["realWordTimesReceived"] = any(sample.get("timedLines", 0) > 0 for sample in connected)
            checks["realSingingEmphasisObserved"] = any(sample.get("emphasis", 0) > 0 for sample in connected)
            checks["missingWordTimesKeepOrdinaryLyrics"] = any(sample.get("timedLines", 0) == 0 and sample["lyricCount"] > 0
                                                             and sample["activeCount"] > 0 for sample in connected)
        report = {"passed": all(checks.values()), "checks": checks, "jumps": self.jumps,
                  "sampleCount": len(samples), "samples": samples}
        if self.font_fixture:
            report["fontVerification"] = self.font_evidence
        if self.require_effects:
            report["effectVerification"] = self.effect_evidence
        if self.require_animations:
            report["animationVerification"] = self.animation_evidence
            self.panel.animation_combo.setCurrentIndex(self.panel.animation_combo.findData(self.original_animation))
        if self.require_singing:
            self.panel.singing_checkbox.setChecked(self.original_singing)
        (self.directory / "netease-report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
        self.app.exit(0 if report["passed"] else 1)

    def _check_animations(self):
        from animation_validation import validate_animations
        from settings import ANIMATION_STYLES
        panel, player = self.panel, self.player
        transport = (player._anchor, player._at, player.song_id, player.playing, self.jumps)
        saved = True
        for style in ANIMATION_STYLES:
            if style == "classic":
                continue
            panel.animation_combo.setCurrentIndex(panel.animation_combo.findData(style))
            saved &= panel.store.load().animation_style == style
            panel.overlay.grab().save(str(self.directory / f"netease-animation-{style}.png"))
        result = validate_animations(self.directory, panel.prefs, panel.devicePixelRatioF(), include_singing=self.require_singing)
        self.animation_evidence = result.pop("animation_benchmarks")
        self.animation_checks.update(result)
        self.animation_checks["animationSettingsPersist"] = bool(saved)
        self.animation_checks["animationChangesKeepTransport"] = transport == (
            player._anchor, player._at, player.song_id, player.playing, self.jumps)
        # Keep fall_shake active through the subsequent real pause/seek/song actions.

    def _check_singing(self):
        from dataclasses import replace
        panel, player = self.panel, self.player
        original = replace(panel.prefs)
        transport = (player._anchor, player._at, player.song_id, player.playing, self.jumps)
        for key, value in (("entry_speed", 150), ("exit_speed", 75), ("shake_frequency", 10), ("fall_distance", 96)):
            panel.spins[key].setValue(value)
        for identifier in ("builtin:quiet", "builtin:lively"):
            panel.apply_preset(identifier)
        for key, value in vars(original).items():
            setattr(panel.prefs, key, value)
        panel._sync_effect_widgets()
        panel.singing_checkbox.setChecked(True)
        # It may already be checked in a reused isolated validation configuration.
        panel.store.save(panel.prefs)
        self.singing_checks = {
            "singingSwitchPersists": panel.store.load().singing_sync is True,
            "singingSwitchKeepsTransport": transport == (player._anchor, player._at, player.song_id, player.playing, self.jumps),
            "parametersAndPresetsKeepPlayback": player.playing and transport == (player._anchor, player._at, player.song_id, player.playing, self.jumps)}
        panel.overlay.refresh_preferences()
