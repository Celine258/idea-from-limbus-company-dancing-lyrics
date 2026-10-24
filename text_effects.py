"""Shared, bounded glyph glow cache and reusable per-line compositing surfaces."""
from collections import OrderedDict
from dataclasses import dataclass, replace
import math
import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from glyph_motion import motion_bounds, GlyphState
import gradients
import scramble


def effect_geometry(pixels, style, variant="standard"):
    """Visible outside stroke and finite glow support, in logical pixels."""
    if style == "glow" and variant == "carmen":
        return (.65 * pixels / 32, 12 * pixels / 32)
    return (1.2 * pixels / 32, 8 * pixels / 32) if style != "solid" else (1.2, 0)


def effect_palette(prefs):
    if prefs.text_style == "glow" and prefs.glow_variant == "carmen":
        return QColor("#ffe6bd"), QColor("#f2b772"), QColor("#ffb655")
    return QColor("#ffffff"), QColor(prefs.color), QColor(prefs.color)


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
    gradient_bounds: object = None
    gradient_regions: object = None
    replacements: object = None
    replacement_scales: object = None


class TextEffects:
    def __init__(self, limit_bytes=64 * 1024 * 1024):
        self.limit_bytes = limit_bytes
        self.cache = OrderedDict()
        self.replacement_cache = OrderedDict()
        self.cache_bytes = 0
        self.hits = self.misses = 0

    def clear(self):
        self.cache.clear()
        self.replacement_cache.clear()
        self.cache_bytes = 0

    def _reserve(self, size):
        while self.cache_bytes + size > self.limit_bytes and (self.cache or self.replacement_cache):
            if self.cache:
                previous, _ = self.cache.popitem(last=False)[1]
                self.cache_bytes -= previous.sizeInBytes()
            else:
                previous = self.replacement_cache.popitem(last=False)[1]
                self.cache_bytes -= previous[0].sizeInBytes() + previous[1].sizeInBytes()

    def glow(self, glyph, pixels, family, color, dpr, variant="standard"):
        path = glyph.path
        if path.isEmpty():
            return None
        if glyph.effect_key is None:
            glyph.effect_key = (path.fillRule().value, tuple((element.x, element.y, element.type.value)
                                for element in (path.elementAt(i) for i in range(path.elementCount()))))
        key = (glyph.effect_key, pixels, family, color.rgba(), dpr, variant)
        if key in self.cache:
            self.hits += 1
            self.cache.move_to_end(key)
            return self.cache[key]
        self.misses += 1
        stroke, radius = effect_geometry(pixels, "glow", variant)
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
            self._reserve(size)
            self.cache[key] = asset
            self.cache_bytes += size
        return asset

    def prepare(self, glyphs, pixels, prefs, dpr, jump_limit=0, angle=0, _regions=None, _replacements=True):
        surface = None
        for ready in self.prepare_steps(glyphs, pixels, prefs, dpr, jump_limit, angle, _regions, _replacements):
            if ready is not None:
                surface = ready
        return surface

    def prepare_steps(self, glyphs, pixels, prefs, dpr, jump_limit=0, angle=0, _regions=None, _replacements=True):
        """GUI-thread batches: publish the entrance before preparing exit symbols.

        Yield None after a glyph/material, or a usable surface when ready. The
        overlay advances these steps between frames and preloads the next cue.
        No worker touches Qt fonts, shared caches or the playback clock.
        """
        _, _, color = effect_palette(prefs)
        stroke, radius = effect_geometry(pixels, prefs.text_style, prefs.glow_variant)
        margin = stroke + radius + 3 / dpr
        bounds = QRectF()
        assets = []
        gradient_bounds = QRectF()
        gradient_regions = {0: QRectF(), 1: QRectF()}
        for glyph in glyphs:
            if not glyph.path.isEmpty():
                ink = glyph.path.boundingRect().translated(glyph.x, glyph.baseline)
                gradient_bounds = gradient_bounds.united(ink)
                gradient_regions[glyph.language] = gradient_regions[glyph.language].united(ink)
        if _regions is not None:
            gradient_regions = _regions
        for glyph in glyphs:
            glyph_pixels = glyph.pixels or pixels
            gradient_outline = prefs.text_style == "glow" and prefs.glow_variant == "gradient"
            asset = self.glow(glyph, glyph_pixels, prefs.font_family, QColor("white") if gradient_outline else color,
                              dpr, prefs.glow_variant) if prefs.text_style != "solid" else None
            if asset and gradient_outline:
                asset = (gradients.tint(asset[0], asset[1], glyph, gradient_regions[glyph.language], prefs), asset[1])
            if not glyph.path.isEmpty():
                ink = glyph.path.boundingRect().adjusted(-margin, -margin, margin, margin)
                if asset:
                    ink = ink.united(QRectF(asset[1], asset[0].deviceIndependentSize()))
                ink = motion_bounds(ink, pixels, jump_limit, prefs.animation_style, angle, prefs.fall_distance, prefs.singing_sync)
                ink.translate(glyph.x, glyph.baseline)
                bounds = bounds.united(ink)
            assets.append(asset)
            yield None
        bounds = bounds.toAlignedRect()
        surface = LineSurface(glyphs, transparent_image(bounds, dpr), QPointF(bounds.x(), bounds.y()), assets, pixels)
        surface.gradient_bounds = gradient_bounds
        surface.gradient_regions = gradient_regions
        if prefs.animation_style != "classic" or prefs.singing_sync or gradients.enabled(prefs) or prefs.scramble_exit:
            yield from self._material_steps(surface, prefs)
        yield surface
        if prefs.scramble_exit and _replacements:
            variants = []
            variant_scales = []
            for glyph in glyphs:
                if glyph.path.isEmpty():
                    variants.append(None)
                    variant_scales.append(None)
                    continue
                center = glyph.path.boundingRect().center()
                paths = scramble.paths(prefs.font_family, glyph.pixels or pixels, glyph.cell_width or glyph.path.boundingRect().width(), center.x(), center.y())
                items = []
                scales = []
                region = gradient_regions[glyph.language]
                for index, path in enumerate(paths):
                    scales.append(min(1, max(1, glyph.cell_width or glyph.path.boundingRect().width()) / max(1, path.boundingRect().width())))
                    # Solid colours do not depend on sentence placement or cell
                    # width (fitting happens when drawing). Share their symbols.
                    placement = (glyph.x, glyph.baseline, region.getRect()) if gradients.enabled(prefs) else ()
                    key = (prefs.font_family, glyph.pixels or pixels, placement,
                           dpr, prefs.text_style, prefs.glow_variant, prefs.color, prefs.gradient_colors, prefs.gradient_direction,
                           prefs.glow_strength, prefs.singing_sync, index)
                    material = self.replacement_cache.get(key)
                    if material is None:
                        variant = replace(glyph, path=path, effect_key=None)
                        prepared = self.prepare([variant], pixels, prefs, dpr, _regions=gradient_regions, _replacements=False)
                        material = self._materials(prepared, prefs)[0]
                        size = material[0].sizeInBytes() + material[1].sizeInBytes()
                        if size <= self.limit_bytes:
                            self._reserve(size)
                            self.replacement_cache[key] = material
                            self.cache_bytes += size
                    else:
                        self.replacement_cache.move_to_end(key)
                    items.append(material)
                    bounds = bounds.united(QRectF(QPointF(material[2]) + QPointF(glyph.x, glyph.baseline), material[0].deviceIndependentSize()).toAlignedRect())
                    yield None
                variants.append(items)
                variant_scales.append(scales)
            surface.replacements = variants
            surface.replacement_scales = variant_scales
            surface.origin = QPointF(bounds.x(), bounds.y())
            surface.image = transparent_image(bounds, dpr)
        yield surface

    def _materials(self, surface, prefs):
        for _ in self._material_steps(surface, prefs):
            pass
        return surface.materials

    def _material_steps(self, surface, prefs):
        """Cache complete glyph materials; fades multiply their final RGBA once.

        Disjoint halo/body pixels allow all halos to precede the white cores.
        A body knockout excludes neighbouring halos underneath fading white ink.
        """
        key = (prefs.text_style, prefs.color, prefs.glow_strength, prefs.singing_sync, prefs.glow_variant,
               prefs.gradient_colors, prefs.gradient_direction)
        if surface.material_key == key:
            return
        materials = []
        dpr = surface.image.devicePixelRatio()
        stroke, radius = effect_geometry(surface.pixels, prefs.text_style, prefs.glow_variant)
        core, outline, _ = effect_palette(prefs)
        for index, glyph in enumerate(surface.glyphs):
            if glyph.path.isEmpty():
                materials.append(None)
                yield None
                continue
            glyph_pixels = glyph.pixels or surface.pixels
            stroke, radius = effect_geometry(glyph_pixels, prefs.text_style, prefs.glow_variant)
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
            region = surface.gradient_regions[glyph.language]
            outline_brush = gradients.brush(region, glyph, prefs) if prefs.text_style == "glow" and prefs.glow_variant == "gradient" else outline
            painter.setPen(QPen(outline_brush if prefs.text_style != "solid" else QColor(10, 22, 26, 210),
                                stroke * 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.setBrush(Qt.BrushStyle.NoBrush if prefs.text_style != "solid" else QColor(prefs.color))
            if prefs.text_style == "glow" and prefs.glow_variant == "gradient":
                painter.save()
                painter.translate(.75 * glyph_pixels / 32, .75 * glyph_pixels / 32)
                painter.drawPath(glyph.path)
                painter.restore()
            painter.drawPath(glyph.path)
            if prefs.text_style != "solid":
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(gradients.brush(region, glyph, prefs) if prefs.text_style == "gradient_fill" else core)
                painter.drawPath(glyph.path)
            painter.end()
            painter = QPainter(mask)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.translate(-origin)
            painter.setPen(QPen(Qt.GlobalColor.white, stroke * 2, Qt.PenStyle.SolidLine,
                                Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.setBrush(Qt.GlobalColor.white)
            if prefs.text_style == "glow" and prefs.glow_variant == "gradient":
                painter.save()
                painter.translate(.75 * glyph_pixels / 32, .75 * glyph_pixels / 32)
                painter.drawPath(glyph.path)
                painter.restore()
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
            yield None
        surface.materials, surface.material_key = materials, key

    def _render_states(self, surface, prefs, states):
        materials = self._materials(surface, prefs)
        surface.image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(surface.image)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        painter.translate(-surface.origin)

        def draw(index, layer, opacity):
            material, state = materials[index], states[index]
            fit = 1
            if state.replacement >= 0 and surface.replacements and surface.replacements[index]:
                material = surface.replacements[index][state.replacement]
                fit = surface.replacement_scales[index][state.replacement]
            if material is None or state.opacity <= 0:
                return
            painter.save()
            painter.translate(state.x, state.y)
            painter.rotate(state.rotation)
            painter.scale(state.scale * fit, state.scale * fit)
            painter.setOpacity(opacity)
            painter.drawImage(material[2], material[layer])
            painter.restore()

        for index, state in enumerate(states):
            gain = 1
            if prefs.singing_sync and prefs.text_style != "solid" and prefs.glow_strength:
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
        strength = prefs.motion_strength / 100
        if states is None and gradients.enabled(prefs):
            states = [GlyphState(glyph.x, glyph.baseline - prefs.jump * strength * energy *
                                (0.6 + 0.4 * math.sin(seconds * 8 - glyph.index * .6)) if moving else glyph.baseline,
                                scale=1 + .04 * energy * strength if moving else 1) for glyph in surface.glyphs]
        if states is not None:
            return self._render_states(surface, prefs, states)
        surface.image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(surface.image)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        painter.translate(-surface.origin)
        poses = [(glyph.x, glyph.baseline - prefs.jump * strength * energy *
                  (0.6 + 0.4 * math.sin(seconds * 8 - glyph.index * .6)) if moving else glyph.baseline)
                 for glyph in surface.glyphs]
        scale = 1 + .04 * energy * strength if moving else 1

        def place(index):
            painter.save()
            painter.translate(*poses[index])
            painter.scale(scale, scale)

        core, color, _ = effect_palette(prefs)
        if prefs.text_style == "glow":
            painter.setOpacity(prefs.glow_strength / 100)
            if prefs.glow_strength:
                for index, asset in enumerate(surface.assets):
                    if asset:
                        place(index)
                        painter.drawImage(asset[1], asset[0])
                        painter.restore()
            painter.setOpacity(1)
            stroke, _ = effect_geometry(surface.pixels, "glow", prefs.glow_variant)
            painter.setPen(QPen(color, 2 * stroke, Qt.PenStyle.SolidLine,
                                Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            for index, glyph in enumerate(surface.glyphs):
                place(index)
                painter.drawPath(glyph.path)
                painter.restore()
            # Draw all white cores last so neighbouring halos never tint them.
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(core)
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
