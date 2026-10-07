"""Warmed full-canvas two-sentence benchmarks for all four animation modes."""
from dataclasses import replace
from pathlib import Path
import time
import numpy as np
from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QApplication
from animation import build_layout, display_regions
from glyph_motion import glyph_states
from lrc import ActiveLine
from settings import ANIMATION_STYLES
from text_effects import TextEffects, transparent_image


def validate_animations(directory, prefs, dpr):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    area = QApplication.primaryScreen().availableGeometry()
    regions = display_regions(area.width(), area.height(), "edges")
    metrics, cache_ok, reuse_ok = {}, True, True
    for style in ANIMATION_STYLES:
        if style == "classic":
            continue
        renderer = TextEffects()
        benchmark = replace(prefs, animation_style=style, font_size=32, jump=10, angle=12,
                            region="edges", text_style="glow")
        started = time.perf_counter()
        layouts = []
        for index, text in enumerate(("给今天一点节奏，让文字随音乐跳动", "from the elevator you · Hello music")):
            layout = build_layout(text, 730 + index, regions, [line.bounds for line in layouts], benchmark)
            if layout is None:
                return {"animation_p95_under_33ms": False, "animation_benchmarks": {"error": style}}
            layout.surface = renderer.prepare(layout.glyphs, layout.font_size, benchmark, dpr, benchmark.jump, layout.angle)
            layouts.append(layout)
        cold_ms = (time.perf_counter() - started) * 1000
        canvas = transparent_image(QRectF(0, 0, area.width(), area.height()), dpr)
        item = ActiveLine(0, "", 0, 3800, 1, 700, 3200)

        def paint(position):
            canvas.fill(0)
            painter = QPainter(canvas)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            for index, layout in enumerate(layouts):
                states = glyph_states(layout.glyphs, benchmark, item, position, .6, layout.font_size, 730 + index, layout.angle)
                image = renderer.render(layout.surface, benchmark, states=states)
                painter.save()
                painter.setOpacity(benchmark.opacity / 100)
                painter.translate(layout.center)
                painter.rotate(layout.angle)
                painter.drawImage(layout.surface.origin, image)
                painter.restore()
            painter.end()

        for index in range(5):
            paint(1000 + index * 33)
        misses = renderer.misses
        samples = []
        for index in range(90):
            started = time.perf_counter()
            paint(800 + index * 33)
            samples.append((time.perf_counter() - started) * 1000)
        p95 = float(np.percentile(samples, 95))
        metrics[style] = {"samples": 90, "glyphs": sum(len(line.glyphs) for line in layouts),
                          "devicePixelRatio": dpr, "physicalCanvas": [canvas.width(), canvas.height()],
                          "coldPrepareMs": round(cold_ms, 3), "warmMedianMs": round(float(np.median(samples)), 3),
                          "warmP95Ms": round(p95, 3), "cacheBytes": renderer.cache_bytes}
        reuse_ok &= renderer.misses == misses
        cache_ok &= renderer.cache_bytes <= renderer.limit_bytes
        paint(3450)
        canvas.save(str(directory / f"animation-{style}-transparent.png"))
    return {"animation_p95_under_33ms": all(metric["warmP95Ms"] <= 33 for metric in metrics.values()),
            "animation_warm_frames_reuse_blur": bool(reuse_ok), "animation_glow_cache_within_64mib": bool(cache_ok),
            "animation_benchmarks": metrics}
