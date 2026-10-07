from dataclasses import dataclass, replace
import math
import random
from PySide6.QtCore import QPointF, QRectF, QTextBoundaryFinder
from PySide6.QtGui import QFontMetricsF, QPainterPath
from fonts import lyric_font
from settings import DEFAULT_FONT_FAMILY, Preferences
from text_effects import effect_geometry
from glyph_motion import motion_bounds


def graphemes(text: str) -> list[str]:
    """Do not split combining marks or joined emoji in the middle."""
    finder = QTextBoundaryFinder(QTextBoundaryFinder.BoundaryType.Grapheme, text)
    result = []
    start = 0
    # QTextBoundaryFinder indexes UTF-16; slice the same representation.
    raw = text.encode("utf-16-le")
    while (end := finder.toNextBoundary()) >= 0:
        result.append(raw[start * 2:end * 2].decode("utf-16-le"))
        start = end
    return result


@dataclass
class Glyph:
    path: QPainterPath
    x: float
    baseline: float
    index: int
    effect_key: tuple | None = None


@dataclass
class LineLayout:
    glyphs: list[Glyph]
    center: QPointF
    angle: float
    bounds: QRectF
    font_size: int
    surface: object = None


def display_regions(width: int, height: int, mode: str) -> list[QRectF]:
    pad = min(24, width * 0.02, height * 0.03)
    if mode == "edges":
        band = max(1.0, width * 0.22 - 2 * pad)
        return [QRectF(pad, pad, band, height - 2 * pad),
                QRectF(width - pad - band, pad, band, height - 2 * pad)]
    return [QRectF(pad, pad, width - 2 * pad, height - 2 * pad)]


def _glyph_layout(text: str, pixels: int, max_width: float, family: str = DEFAULT_FONT_FAMILY):
    font = lyric_font(family, pixels)
    metrics = QFontMetricsF(font)
    rows: list[list[str]] = [[]]
    row_width = 0.0
    for char in graphemes(text):
        if char in ("\n", "\r\n"):
            rows.append([])
            row_width = 0.0
            continue
        advance = metrics.horizontalAdvance(char)
        if rows[-1] and row_width + advance > max_width:
            rows.append([])
            row_width = 0.0
        rows[-1].append(char)
        row_width += advance
    widths = [sum(metrics.horizontalAdvance(char) for char in row) for row in rows]
    glyphs = []
    index = 0
    height = metrics.height() * len(rows)
    for row_index, row in enumerate(rows):
        x = -widths[row_index] / 2
        baseline = -height / 2 + metrics.ascent() + row_index * metrics.height()
        for char in row:
            advance = metrics.horizontalAdvance(char)
            path = QPainterPath()
            if not char.isspace():
                path.addText(QPointF(-advance / 2, 0), font, char)
            glyphs.append(Glyph(path, x + advance / 2, baseline, index))
            x += advance
            index += 1
    width = max(widths, default=0)
    bounds = QRectF(-width / 2, -height / 2, width, height)
    for glyph in glyphs:
        bounds = bounds.united(glyph.path.boundingRect().translated(glyph.x, glyph.baseline))
    # Imported fonts can draw outside their advances/ascent. Include their ink
    # in the centered box used for rotation, collision and screen clipping.
    return glyphs, 2 * max(abs(bounds.left()), abs(bounds.right())), 2 * max(abs(bounds.top()), abs(bounds.bottom()))


def build_layout(text: str, seed: int, regions: list[QRectF], occupied: list[QRectF],
                 prefs: Preferences) -> LineLayout | None:
    rng = random.Random(seed)
    regions = list(regions)
    rng.shuffle(regions)
    fallback = None
    for region in regions:
        angle = rng.uniform(-prefs.angle, prefs.angle)
        for pixels in range(prefs.font_size, 9, -1):
            reserve = 50
            if prefs.animation_style != "classic":
                reserve += prefs.jump * .6 + 8
                if prefs.animation_style.startswith("fall_"):
                    reserve += pixels * 1.5 * abs(math.sin(math.radians(angle)))
            glyphs, width, height = _glyph_layout(text, pixels, max(10, region.width() - reserve), prefs.font_family)
            # Include stroke, character scale, jumping and fade-out drift.
            stroke, glow = effect_geometry(pixels, prefs.text_style)
            margin = stroke + glow + 4
            box_w = (width + 2 * margin) * 1.04 + 16
            box_h = (height + 2 * margin) * 1.04 + 2 * prefs.jump + 36
            if prefs.animation_style != "classic":
                animated = QRectF()
                for glyph in glyphs:
                    if not glyph.path.isEmpty():
                        ink = glyph.path.boundingRect().adjusted(-margin, -margin, margin, margin)
                        animated = animated.united(motion_bounds(ink, pixels, prefs.jump, prefs.animation_style, angle)
                                                   .translated(glyph.x, glyph.baseline))
                box_w = 2 * max(abs(animated.left()), abs(animated.right())) + 16
                box_h = 2 * max(abs(animated.top()), abs(animated.bottom())) + 16
            rad = math.radians(angle)
            rotated_w = abs(box_w * math.cos(rad)) + abs(box_h * math.sin(rad))
            rotated_h = abs(box_w * math.sin(rad)) + abs(box_h * math.cos(rad))
            if rotated_w > region.width() or rotated_h > region.height():
                continue
            x_low, x_high = region.left() + rotated_w / 2, region.right() - rotated_w / 2
            y_low, y_high = region.top() + rotated_h / 2, region.bottom() - rotated_h / 2
            for _ in range(12):
                center = QPointF(rng.uniform(x_low, x_high), rng.uniform(y_low, y_high))
                bounds = QRectF(center.x() - rotated_w / 2, center.y() - rotated_h / 2,
                                rotated_w, rotated_h)
                item = LineLayout(glyphs, center, angle, bounds, pixels)
                if not any(bounds.intersects(rect.adjusted(-12, -12, 12, 12)) for rect in occupied):
                    return item
            # Try fixed empty slots before using a smaller font or dropping the older sentence.
            for fraction in (0.18, 0.5, 0.82):
                center = QPointF((x_low + x_high) / 2, y_low + (y_high - y_low) * fraction)
                bounds = QRectF(center.x() - rotated_w / 2, center.y() - rotated_h / 2,
                                rotated_w, rotated_h)
                item = LineLayout(glyphs, center, angle, bounds, pixels)
                fallback = fallback or item
                if not any(bounds.intersects(rect.adjusted(-12, -12, 12, 12)) for rect in occupied):
                    return item
            break
    if fallback is None and prefs.animation_style != "classic" and prefs.angle:
        # Very narrow bands with long imported glyphs may only fit without sentence tilt.
        return build_layout(text, seed, regions, occupied, replace(prefs, angle=0))
    return fallback  # Overlay drops conflicting older instances in this rare case.
