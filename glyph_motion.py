"""Stateless character choreography: the song position is the only animation clock."""
from dataclasses import dataclass
import math
from PySide6.QtCore import QRectF
from PySide6.QtGui import QTransform


@dataclass(frozen=True)
class GlyphState:
    x: float
    y: float
    opacity: float = 1
    scale: float = 1
    rotation: float = 0


def smooth(value):
    value = max(0., min(1., value))
    return value * value * (3 - 2 * value)


def noise_value(seed, rank, axis, sample):
    value = (seed * 0x9E3779B1 + rank * 0x85EBCA77 + axis * 0xC2B2AE3D + sample) & 0xFFFFFFFF
    value = ((value ^ (value >> 16)) * 0x7FEB352D) & 0xFFFFFFFF
    value = ((value ^ (value >> 15)) * 0x846CA68B) & 0xFFFFFFFF
    return ((value ^ (value >> 16)) / 0xFFFFFFFF) * 2 - 1


def noise(seed, rank, axis, seconds, frequency=6):
    clock = seconds * frequency
    sample = math.floor(clock)
    weight = smooth(clock - sample)
    first = noise_value(seed, rank, axis, sample)
    return first + (noise_value(seed, rank, axis, sample + 1) - first) * weight


def stagger(position, start, end, rank, count, duration):
    total = max(0., end - start)
    if total == 0:
        return float(position >= end)
    duration = min(duration, total)
    delay = (total - duration) * rank / (count - 1) if count > 1 else 0
    return max(0., min(1., (position - start - delay) / duration))


def glyph_states(glyphs, prefs, item, position_ms, energy, pixels, seed=0, angle=0):
    visible = [glyph for glyph in glyphs if not glyph.path.isEmpty()]
    count, rank = len(visible), 0
    seconds = position_ms / 1000
    amplitude = prefs.jump * (.35 + .65 * max(0., min(1., energy)))
    falling = prefs.animation_style.startswith("fall_")
    shaking = prefs.animation_style.endswith("_shake")
    radians = math.radians(angle)
    result = []
    for glyph in glyphs:
        if glyph.path.isEmpty():
            result.append(GlyphState(glyph.x, glyph.baseline, 0))
            continue
        entering = stagger(position_ms, item.start_ms, item.entry_end_ms, rank, count, 140 * 100 / prefs.entry_speed)
        leaving = stagger(position_ms, item.exit_start_ms, item.end_ms, rank, count,
                          (350 if falling else 200) * 100 / prefs.exit_speed)
        opacity = smooth(entering) * (1 - smooth(leaving))
        if shaking:
            dx = amplitude * .3 * noise(seed, rank, 0, seconds, prefs.shake_frequency)
            dy = amplitude * .5 * noise(seed, rank, 1, seconds, prefs.shake_frequency)
        else:
            dx = 0
            dy = amplitude * .4 * math.sin(seconds * 2 * math.pi * 1.5 - rank * .6)
        distance = prefs.fall_distance * pixels / 32 * leaving ** 2 if falling else 0
        rotation = (8 if noise_value(seed, rank, 2, 0) >= 0 else -8) * leaving ** 2 if falling else 0
        # Convert screen-vertical fall to the tilted sentence's local coordinates.
        result.append(GlyphState(glyph.x + dx + math.sin(radians) * distance,
                                 glyph.baseline + dy + math.cos(radians) * distance,
                                 opacity, 1, rotation))
        rank += 1
    return result


def motion_bounds(ink, pixels, jump, style, angle=0, fall_distance=48):
    """Conservative local bounds including rotation, shake and screen-vertical fall."""
    if style == "classic":
        scaled = QRectF(ink.x() * 1.04, ink.y() * 1.04, ink.width() * 1.04, ink.height() * 1.04)
        return scaled.united(scaled.translated(0, -jump))
    bounds = QRectF(ink)
    if style.startswith("fall_"):
        for rotation in (-8, 8):
            bounds = bounds.united(QTransform().rotate(rotation).mapRect(ink))
        radians = math.radians(angle)
        distance = fall_distance * pixels / 32
        bounds = bounds.united(bounds.translated(math.sin(radians) * distance,
                                                math.cos(radians) * distance))
    return bounds.adjusted(-jump * .3 - 2, -jump * .5 - 2, jump * .3 + 2, jump * .5 + 2)
