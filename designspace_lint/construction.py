# Copyright 2026 Alexander Lubovenko
# Licensed under the Apache License, Version 2.0

"""
The order a composite's components are expected in: bases first, then the
marks from the bottom up.

Unlike the rest of this package this is a convention, not a build
consequence: ufo2ft and varLib accept any order as long as the masters agree
(4.19). It is the rule Font-Rover's users asked for, implemented literally,
and it backs the opt-in `construction` phase (4.20, 4.21) as well as
Font-Rover's fix, which calls `canonical_component_order` on the master the
user picks so that the fix and the check can never disagree.

A component's role comes from its base glyph's unicode in the font:

- the base glyph's own first unicode; failing that, the unicode of the glyph
  named like it without the suffix (everything from the first ".");
- general category Mn, Me, Sk or Lm is a mark (`ACCENT`), anything else a
  `BASE`, and no unicode at all `UNKNOWN`;
- a name with "_" and no unicode of its own (after the suffix is stripped) is
  a ligature of its parts: all marks makes it a mark, otherwise it weighs as
  many bases as it has. A part with no unicode leaves the component unknown.

The rule applies when a glyph has a mark. Bases go first, heaviest first, then
the marks by the bottom of their placed outline, lowest first; ties keep
their current order. Unknown components count as marks when the glyph has a
known base; otherwise nothing is reordered. Every unknown component, and a
mark with no outline to measure, comes back as a note.
"""

from __future__ import annotations

import unicodedata

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.pointPen import PointToSegmentPen
from fontTools.pens.transformPen import TransformPen

ACCENT = "accent"
BASE = "base"
UNKNOWN = "unknown"

#: Unicode general categories that make a component a mark.
ACCENT_CATEGORIES = frozenset({"Mn", "Me", "Sk", "Lm"})

# Reasons given in the notes.
NO_UNICODE = "no unicode"
LIGATURE_PART_NO_UNICODE = "ligature part without a unicode"
MISSING_BASE = "base glyph not in the font"
NO_OUTLINE = "no outline to measure, order left as it is"


def _unicode_of(font, name: str) -> int | None:
    if not name or name not in font:
        return None
    unicodes = list(getattr(font[name], "unicodes", None) or ())
    return unicodes[0] if unicodes else None


def _kind(codepoint: int) -> str:
    return ACCENT if unicodedata.category(chr(codepoint)) in ACCENT_CATEGORIES else BASE


def component_role(font, base_name: str) -> tuple[str, int, str]:
    """The role of a component whose base glyph is `base_name`.

    Returns ``(kind, weight, reason)``: `kind` is `ACCENT`, `BASE` or
    `UNKNOWN`; `weight` is how many bases it counts as (0 for a mark); `reason`
    says why it is unknown, and is empty otherwise.
    """
    if base_name not in font:
        return UNKNOWN, 0, MISSING_BASE
    codepoint = _unicode_of(font, base_name)
    stem = base_name.split(".", 1)[0]
    if codepoint is None:
        codepoint = _unicode_of(font, stem)
    if codepoint is not None:
        kind = _kind(codepoint)
        return kind, (1 if kind == BASE else 0), ""
    if "_" in stem:
        parts = [part for part in stem.split("_") if part]
        weight = 0
        for part in parts:
            part_codepoint = _unicode_of(font, part)
            if part_codepoint is None:
                return UNKNOWN, 0, f"{LIGATURE_PART_NO_UNICODE} ({part})"
            weight += _kind(part_codepoint) == BASE
        return (ACCENT, 0, "") if weight == 0 else (BASE, weight, "")
    return UNKNOWN, 0, NO_UNICODE


class _Drawable:
    """A glyph drawn through its point pen, for the segment pens fontTools has."""

    def __init__(self, glyph):
        self._glyph = glyph

    def draw(self, pen):
        self._glyph.drawPoints(PointToSegmentPen(pen))


class _LayerGlyphSet:
    def __init__(self, layer):
        self._layer = layer

    def __contains__(self, name):
        return name in self._layer

    def __getitem__(self, name):
        return _Drawable(self._layer[name])


def component_y_min(component, layer) -> float | None:
    """The bottom of a component as placed: transformed, nested components drawn."""
    base_name = component.baseGlyph
    if base_name not in layer:
        return None
    glyph_set = _LayerGlyphSet(layer)
    bounds_pen = BoundsPen(glyph_set)
    try:
        glyph_set[base_name].draw(TransformPen(bounds_pen, tuple(component.transformation)))
    except KeyError:  # a nested component whose base is missing
        return None
    return bounds_pen.bounds[1] if bounds_pen.bounds else None


def canonical_component_order(glyph, font, layer=None) -> tuple[list[int], list[tuple[int, str]]]:
    """The order `glyph`'s components should be in, and what got in the way.

    Args:
        glyph: the composite, with `components` (each with `baseGlyph` and
            `transformation`).
        font: where the base glyphs' unicodes are read: the UFO's default
            layer, as ufo2ft reads the cmap -- a fontParts font will do.
        layer: where the components' outlines are drawn from, when they are
            not in `font`: the master's own layer for a layer source.

    Returns:
        ``(order, notes)``: `order` lists indexes into `glyph.components`, in
        the expected order -- ``list(range(n))`` when nothing should move;
        `notes` lists ``(component index, reason)`` for every component whose
        role is unknown, and for marks that could not be measured.
    """
    if layer is None:
        layer = font
    components = list(glyph.components)
    identity = list(range(len(components)))
    if len(components) < 2:
        return identity, []

    roles = [component_role(font, c.baseGlyph) for c in components]
    notes = [(i, reason) for i, (kind, _w, reason) in enumerate(roles) if kind == UNKNOWN]
    has_base = any(kind == BASE for kind, _w, _r in roles)
    has_accent = any(kind == ACCENT for kind, _w, _r in roles)

    if not has_base or (not has_accent and not notes):
        # Nothing known to put first, or no mark to put after it.
        return identity, notes

    # With a known base present, unknown components count as marks.
    keys = []
    for i, (kind, weight, _reason) in enumerate(roles):
        if kind == BASE:
            keys.append((-weight, 0.0))
            continue
        y_min = component_y_min(components[i], layer)
        if y_min is None:
            notes.append((i, NO_OUTLINE))
            return identity, notes
        keys.append((0, y_min))
    order = sorted(identity, key=lambda i: keys[i])
    return order, notes
