"""Shared, bounded glyph glow cache and reusable per-line compositing surfaces."""
from collections import OrderedDict
from dataclasses import dataclass
import math
import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from glyph_motion import motion_bounds


def effect_geometry(pixels, style):
    """Visible outside stroke and finite glow support, in logical pixels."""
    return (1.2 * pixels / 32, 8 * pixels / 32) if style == "glow" else (1.2, 0)


def gaussian_alpha(alpha, sigma, radius):
    axis = np.arange(-radius, radius + 1, dtype=np.float32)
    kernel = np.exp(-(axis * axis) / (2 * sigma * sigma))
    kernel /= kernel.sum()
    height, width = alpha.shape
    padded = np.pad(alpha, ((0, 0), (radius, radius)))
    horizontal = np.zeros_like(alpha)
    for index, weight in enumerate(kernel):
        horizontal += padded[:, index:index + width] * weight
    padded = np.pad(horizontal, ((radius, radius), (0, 0)))
    result = np.zeros_like(alpha)
    for index, weight in enumerate(kernel):
        result += padded[index:index + height, :] * weight
    return result


def pixels_view(image):
    """RGBA byte order is explicit; rows may contain padding."""
    return np.ndarray((image.height(), image.width(), 4), dtype=np.uint8,
                      buffer=image.bits(), strides=(image.bytesPerLine(), 4, 1))


def transparent_image(bounds, dpr):
    image = QImage(max(1, math.ceil(bounds.width() * dpr)), max(1, math.ceil(bounds.height() * dpr)),
                   QImage.Format.Format_RGBA8888_Premultiplied)
    image.setDevicePixelRatio(dpr)
    image.fill(Qt.GlobalColor.transparent)
    return image


@dataclass
class LineSurface:
    glyphs: list
    image: QImage
    origin: QPointF
    assets: list
    pixels: int
    materials: object = None
    material_key: object = None


class TextEffects:
    def __init__(self, limit_bytes=64 * 1024 * 1024):
        self.limit_bytes = limit_bytes
        self.cache = OrderedDict()
        self.cache_bytes = 0
        self.hits = self.misses = 0

    def clear(self):
        self.cache.clear()
        self.cache_bytes = 0

    def glow(self, glyph, pixels, family, color, dpr):
        path = glyph.path
        if path.isEmpty():
            return None
        if glyph.effect_key is None:
            glyph.effect_key = (path.fillRule().value, tuple((element.x, element.y, element.type.value)
                                for element in (path.elementAt(i) for i in range(path.elementCount()))))
        key = (glyph.effect_key, pixels, family, color.rgba(), dpr)
        if key in self.cache:
            self.hits += 1
            self.cache.move_to_end(key)
            return self.cache[key]
        self.misses += 1
        stroke, radius = effect_geometry(pixels, "glow")
        margin = stroke + math.ceil(radius * dpr) / dpr + 2 / dpr
        bounds = path.boundingRect().adjusted(-margin, -margin, margin, margin).toAlignedRect()
        image = transparent_image(bounds, dpr)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(-bounds.x(), -bounds.y())
        painter.setPen(QPen(Qt.GlobalColor.white, 2 * stroke, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.GlobalColor.white)
        painter.drawPath(path)
        painter.end()
        alpha = pixels_view(image)[:, :, 3].astype(np.float32) / 255
        blurred = gaussian_alpha(alpha, max(.1, radius * dpr / 3), max(1, math.ceil(radius * dpr)))
        view = pixels_view(image)
        channel = np.rint(np.clip(blurred, 0, 1) * 255).astype(np.uint8)
        view[:, :, 3] = channel
        for index, value in enumerate((color.red(), color.green(), color.blue())):
            view[:, :, index] = np.rint(channel.astype(np.float32) * value / 255).astype(np.uint8)
        asset = (image, QPointF(bounds.x(), bounds.y()))
        size = image.sizeInBytes()
        if size <= self.limit_bytes:
            while self.cache and self.cache_bytes + size > self.limit_bytes:
                previous, _ = self.cache.popitem(last=False)[1]
                self.cache_bytes -= previous.sizeInBytes()
            self.cache[key] = asset
            self.cache_bytes += size
        return asset

    def prepare(self, glyphs, pixels, prefs, dpr, jump_limit=0, angle=0):
        color = QColor(prefs.color)
        stroke, radius = effect_geometry(pixels, prefs.text_style)
        margin = stroke + radius + 3 / dpr
        bounds = QRectF()
        assets = []
        for glyph in glyphs:
            asset = self.glow(glyph, pixels, prefs.font_family, color, dpr) if prefs.text_style == "glow" else None
            if not glyph.path.isEmpty():
                ink = glyph.path.boundingRect().adjusted(-margin, -margin, margin, margin)
                if asset:
                    ink = ink.united(QRectF(asset[1], asset[0].deviceIndependentSize()))
                ink = motion_bounds(ink, pixels, jump_limit, prefs.animation_style, angle, prefs.fall_distance, prefs.singing_sync)
                ink.translate(glyph.x, glyph.baseline)
                bounds = bounds.united(ink)
            assets.append(asset)
        bounds = bounds.toAlignedRect()
        surface = LineSurface(glyphs, transparent_image(bounds, dpr), QPointF(bounds.x(), bounds.y()), assets, pixels)
        if prefs.animation_style != "classic" or prefs.singing_sync:
            self._materials(surface, prefs)
        return surface

    def _materials(self, surface, prefs):
        """Cache complete glyph materials; fades multiply their final RGBA once.

        Disjoint halo/body pixels allow all halos to precede the white cores.
        A body knockout excludes neighbouring halos underneath fading white ink.
        """
        key = (prefs.text_style, prefs.color, prefs.glow_strength, prefs.singing_sync)
        if surface.material_key == key:
            return surface.materials
        materials = []
        dpr = surface.image.devicePixelRatio()
        stroke, radius = effect_geometry(surface.pixels, prefs.text_style)
        for index, glyph in enumerate(surface.glyphs):
            if glyph.path.isEmpty():
                materials.append(None)
                continue
            glow = surface.assets[index]
            if glow:
                origin = glow[1]
                bounds = QRectF(origin, glow[0].deviceIndependentSize())
            else:
                bounds = glyph.path.boundingRect().adjusted(-stroke-3, -stroke-3, stroke+3, stroke+3).toAlignedRect()
                origin = bounds.topLeft()
            image, mask = transparent_image(bounds, dpr), transparent_image(bounds, dpr)
            painter = QPainter(image)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.translate(-origin)
            if glow and prefs.glow_strength:
                painter.setOpacity(prefs.glow_strength / 100)
                painter.drawImage(origin, glow[0])
            painter.setOpacity(1)
            painter.setPen(QPen(QColor(prefs.color) if prefs.text_style == "glow" else QColor(10, 22, 26, 210),
                                stroke * 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.setBrush(Qt.BrushStyle.NoBrush if prefs.text_style == "glow" else QColor(prefs.color))
            painter.drawPath(glyph.path)
            if prefs.text_style == "glow":
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(Qt.GlobalColor.white)
                painter.drawPath(glyph.path)
            painter.end()
            painter = QPainter(mask)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.translate(-origin)
            painter.setPen(QPen(Qt.GlobalColor.white, stroke * 2, Qt.PenStyle.SolidLine,
                                Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.setBrush(Qt.GlobalColor.white)
            painter.drawPath(glyph.path)
            painter.end()
            body_pixels = pixels_view(mask)[:, :, 3] > 0
            halo, body = image.copy(), image.copy()
            pixels_view(halo)[body_pixels] = 0
            pixels_view(body)[~body_pixels] = 0
            if glow and prefs.singing_sync and prefs.glow_strength:
                # Cache the peak halo once; singing intensity is a composition weight.
                halo.fill(Qt.GlobalColor.transparent)
                painter = QPainter(halo)
                painter.setOpacity(min(100, prefs.glow_strength * 1.4) / 100)
                painter.drawImage(QPointF(), glow[0])
                painter.end()
                pixels_view(halo)[body_pixels] = 0
            materials.append((halo, body, origin))
        surface.materials, surface.material_key = materials, key
        return materials

    def _render_states(self, surface, prefs, states):
        materials = self._materials(surface, prefs)
        surface.image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(surface.image)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        painter.translate(-surface.origin)

        def draw(index, layer, opacity):
            material, state = materials[index], states[index]
            if material is None or state.opacity <= 0:
                return
            painter.save()
            painter.translate(state.x, state.y)
            painter.rotate(state.rotation)
            painter.scale(state.scale, state.scale)
            painter.setOpacity(opacity)
            painter.drawImage(material[2], material[layer])
            painter.restore()

        for index, state in enumerate(states):
            gain = 1
            if prefs.singing_sync and prefs.text_style == "glow" and prefs.glow_strength:
                peak = min(100, prefs.glow_strength * 1.4)
                gain = (prefs.glow_strength + (peak - prefs.glow_strength) * state.emphasis) / peak
            draw(index, 0, state.opacity * gain)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut)
        for index in range(len(states)):
            draw(index, 1, 1)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        for index, state in enumerate(states):
            draw(index, 1, state.opacity)
        painter.end()
        return surface.image

    def render(self, surface, prefs, seconds=0, energy=0, moving=False, states=None):
        if states is not None:
            return self._render_states(surface, prefs, states)
        surface.image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(surface.image)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        painter.translate(-surface.origin)
        poses = [(glyph.x, glyph.baseline - prefs.jump * energy *
                  (0.6 + 0.4 * math.sin(seconds * 8 - glyph.index * .6)) if moving else glyph.baseline)
                 for glyph in surface.glyphs]
        scale = 1 + .04 * energy if moving else 1

        def place(index):
            painter.save()
            painter.translate(*poses[index])
            painter.scale(scale, scale)

        color = QColor(prefs.color)
        if prefs.text_style == "glow":
            painter.setOpacity(prefs.glow_strength / 100)
            if prefs.glow_strength:
                for index, asset in enumerate(surface.assets):
                    if asset:
                        place(index)
                        painter.drawImage(asset[1], asset[0])
                        painter.restore()
            painter.setOpacity(1)
            stroke, _ = effect_geometry(surface.pixels, "glow")
            painter.setPen(QPen(color, 2 * stroke, Qt.PenStyle.SolidLine,
                                Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            for index, glyph in enumerate(surface.glyphs):
                place(index)
                painter.drawPath(glyph.path)
                painter.restore()
            # Draw all white cores last so neighbouring halos never tint them.
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(Qt.GlobalColor.white)
        else:
            painter.setPen(QPen(QColor(10, 22, 26, 210), 2.4, Qt.PenStyle.SolidLine,
                                Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.setBrush(color)
        for index, glyph in enumerate(surface.glyphs):
            place(index)
            painter.drawPath(glyph.path)
            painter.restore()
        painter.end()
        return surface.image


TEXT_EFFECTS = TextEffects()
