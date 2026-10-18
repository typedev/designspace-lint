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
- a letter (general category Lu, Ll, Lt or Lo) is a `BASE`; everything else
  is a mark (`ACCENT`): Mn, Me, Sk, Lm, but also So, Co, Po, Nd, and a glyph
  with no unicode at all. Fonts encode marks oddly -- a hook as U+2440 OCR
  HOOK, a comma accent in the private use area -- and a letter is the one
  thing that is reliably a base;
- a name with "_" and no unicode of its own (after the suffix is stripped) is
  a ligature of its parts: it weighs as many bases as it has letter parts, and
  with none it is a mark. A part with no unicode is not a letter.

The rule applies when a glyph has both a base and a mark. Bases go first,
heaviest first, then the marks by the bottom of their placed outline, lowest
first; ties keep their current order. A component with no unicode is ordered
as a mark and comes back as a note, as does a mark with no outline to
measure, which leaves the order as it is.
"""

from __future__ import annotations

import unicodedata

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.pointPen import PointToSegmentPen
from fontTools.pens.transformPen import TransformPen

ACCENT = "accent"
BASE = "base"
#: No longer returned: a component with no unicode is a mark. Kept for 0.9.x.
UNKNOWN = "unknown"

#: Unicode general categories that make a component a base; any other is a mark.
BASE_CATEGORIES = frozenset({"Lu", "Ll", "Lt", "Lo"})

#: The mark categories of 0.8.1, no longer used. Kept for 0.9.x.
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
    return BASE if unicodedata.category(chr(codepoint)) in BASE_CATEGORIES else ACCENT


def component_role(font, base_name: str) -> tuple[str, int, str]:
    """The role of a component whose base glyph is `base_name`.

    Returns ``(kind, weight, reason)``: `kind` is `BASE` or `ACCENT`;
    `weight` is how many bases it counts as (0 for a mark); `reason` says why
    no unicode was found for it (or a part of it), and is empty otherwise.
    """
    if base_name not in font:
        return ACCENT, 0, MISSING_BASE
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
        missing = []
        for part in parts:
            part_codepoint = _unicode_of(font, part)
            if part_codepoint is None:
                missing.append(part)
            elif _kind(part_codepoint) == BASE:
                weight += 1
        reason = f"{LIGATURE_PART_NO_UNICODE} ({', '.join(missing)})" if missing else ""
        return (BASE, weight, reason) if weight else (ACCENT, 0, reason)
    return ACCENT, 0, NO_UNICODE


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
        `notes` lists ``(component index, reason)`` for every component with
        no unicode to go by, and for marks that could not be measured.
    """
    if layer is None:
        layer = font
    components = list(glyph.components)
    identity = list(range(len(components)))
    if len(components) < 2:
        return identity, []

    roles = [component_role(font, c.baseGlyph) for c in components]
    notes = [(i, reason) for i, (_kind, _w, reason) in enumerate(roles) if reason]
    has_base = any(kind == BASE for kind, _w, _r in roles)
    has_accent = any(kind == ACCENT for kind, _w, _r in roles)

    if not (has_base and has_accent):
        # No letter to put first, or no mark to put after it.
        return identity, notes

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
