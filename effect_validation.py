"""Actual font effect screenshots and a warmed two-line software paint benchmark."""
from dataclasses import replace
from pathlib import Path
import time
import numpy as np
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QApplication
from animation import _glyph_layout, build_layout, display_regions
from text_effects import TextEffects, transparent_image


def validate_effects(directory, prefs, dpr):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    renderer = TextEffects()
    demo = replace(prefs, color="#ff6a9c", font_size=48, jump=0, opacity=100, text_style="glow", glow_strength=60)
    glyphs, _, _ = _glyph_layout("给今天一点节奏\nfrom the elevator you", 48, 690, demo.font_family)
    surface = renderer.prepare(glyphs, 48, demo, dpr)
    source = renderer.render(surface, demo)
    for name, background in (("dark", "#18232f"), ("light", "#f7f8fa")):
        image = transparent_image(QRectF(0, 0, 760, 210), dpr)
        image.fill(QColor(background))
        painter = QPainter(image)
        painter.translate(380, 105)
        painter.drawImage(surface.origin, source)
        painter.end()
        image.save(str(directory / f"glow-{name}.png"))
    source.save(str(directory / "glow-transparent.png"))

    benchmark_prefs = replace(prefs, font_size=32, jump=10, angle=12, region="edges", text_style="glow")
    area = QApplication.primaryScreen().availableGeometry()
    regions = display_regions(area.width(), area.height(), "edges")
    started = time.perf_counter()
    layouts = []
    for index, text in enumerate(("给今天一点节奏，让文字随音乐跳动", "from the elevator you · Hello music")):
        layout = build_layout(text, 730 + index, regions, [line.bounds for line in layouts], benchmark_prefs)
        if layout is None:
            return {"warm_frame_p95_under_33ms": False, "effect_benchmark": {"error": "双句布局无法生成"}}
        layout.surface = renderer.prepare(layout.glyphs, layout.font_size, benchmark_prefs, dpr, benchmark_prefs.jump)
        layouts.append(layout)
    cold_ms = (time.perf_counter() - started) * 1000
    canvas = transparent_image(QRectF(0, 0, area.width(), area.height()), dpr)

    def paint(seconds):
        canvas.fill(0)
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        for layout in layouts:
            painter.save()
            painter.setOpacity(benchmark_prefs.opacity / 100)
            painter.translate(layout.center)
            painter.rotate(layout.angle)
            painter.drawImage(layout.surface.origin, renderer.render(layout.surface, benchmark_prefs, seconds, .6, moving=True))
            painter.restore()
        painter.end()

    for index in range(5):
        paint(index / 30)
    measurements = []
    misses = renderer.misses
    for index in range(90):
        started = time.perf_counter()
        paint(index / 30)
        measurements.append((time.perf_counter() - started) * 1000)
    p95 = float(np.percentile(measurements, 95))
    metrics = {"samples": len(measurements), "glyphs": sum(len(layout.glyphs) for layout in layouts),
               "devicePixelRatio": dpr, "physicalCanvas": [canvas.width(), canvas.height()],
               "coldPrepareMs": round(cold_ms, 3), "warmMedianMs": round(float(np.median(measurements)), 3),
               "warmP95Ms": round(p95, 3), "cacheBytes": renderer.cache_bytes}
    return {"warm_frame_p95_under_33ms": p95 <= 33, "warm_frames_reuse_glow_cache": misses == renderer.misses,
            "effect_cache_within_64mib": renderer.cache_bytes <= 64 * 1024 * 1024, "effect_benchmark": metrics}
