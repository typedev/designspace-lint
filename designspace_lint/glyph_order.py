# Copyright 2024-2026 TypeDev
# Licensed under the Apache License, Version 2.0

"""
Reading a font's glyph order, and working out which names are "extra".

`safe_glyph_order` exists because a UFO can name the same glyph twice in
`public.glyphOrder` -- Glyphs.app writes such files -- and fontParts' getter
*raises* on that rather than handing back the list. A validator that dies while
reading the thing it is meant to report on is no use, so this goes around the
normalizer to the object underneath and collapses the repeats itself.

The rest of the module answers the glyph-order questions the checks ask, with
the two rules that decide them written down where they can be read:

- `public.glyphOrder` wins over the glyphs a font physically holds. A name
  listed there with nothing behind it (a template entry) is still a name the
  designspace carries, so it counts.
- The physical keys are the fallback *only* for a font that has no glyph order
  at all.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _raw_glyph_order(font: Any) -> Optional[list[str]]:
    """Read glyphOrder around the fontParts normalizer.

    The defcon/ufoLib2 object underneath stores the list as written, so it
    hands back the duplicates rather than raising on them.
    """
    naked = getattr(font, "naked", None)
    if naked is not None:
        try:
            return list(naked().glyphOrder or [])
        except Exception:  # pragma: no cover - defensive
            pass
    try:
        return list(font.lib.get("public.glyphOrder") or [])
    except Exception:  # pragma: no cover - defensive
        return None


def _first_wins(order: list[str]) -> list[str]:
    """Drop repeated names, keeping the position of the first occurrence."""
    seen: set[str] = set()
    kept: list[str] = []
    for name in order:
        if name in seen:
            continue
        seen.add(name)
        kept.append(name)
    return kept


def duplicate_glyph_order_names(order: list[str]) -> list[str]:
    """The names that appear more than once, in order of their first repeat."""
    seen: set[str] = set()
    dupes: list[str] = []
    for name in order:
        if name in seen and name not in dupes:
            dupes.append(name)
        seen.add(name)
    return dupes


def safe_glyph_order(font: Any) -> list[str]:
    """Read `font.glyphOrder` without letting a duplicate name raise.

    Args:
        font: fontParts (or defcon) font object.

    Returns:
        The glyph order with repeats collapsed, or an empty list when the font
        has no order at all. Callers keep their existing
        ``safe_glyph_order(font) or font.keys()`` fallback for that case.
    """
    try:
        raw = list(font.glyphOrder or [])
    except ValueError:
        # fontParts refused the list -- go around it to the object underneath,
        # which stores it as written.
        raw = _raw_glyph_order(font) or []
    except Exception:  # pragma: no cover - defensive
        return []

    if not raw:
        return []

    # Collapse repeats even when the getter did not object: defcon and ufoLib2
    # hand the list back unvalidated, so the caller would otherwise place the
    # same glyph twice depending on which object it happened to hold.
    kept = _first_wins(raw)
    if len(kept) != len(raw):
        logger.warning(
            "glyphOrder lists %d name(s) more than once (%s) - keeping the first "
            "occurrence of each; %d entries became %d",
            len(raw) - len(kept),
            ", ".join(duplicate_glyph_order_names(raw)),
            len(raw),
            len(kept),
        )
    return kept


def source_order(source: Any) -> list[str]:
    """A master's glyph order, falling back to the glyphs it actually draws."""
    order = safe_glyph_order(source.font)
    if order:
        return order
    try:
        if source.master_layer_name():
            return list(source.get_layer().keys())
        return list(source.font.keys())
    except Exception:  # pragma: no cover - defensive
        return []


def owns_glyph(source: Any, name: str) -> bool:
    """Whether this master draws the glyph itself, ignoring other layers.

    Replaces an index-based lookup that read the whole parent UFO's keys, so a
    layer master used to claim glyphs it does not draw.
    """
    try:
        if source.master_layer_name():
            return name in source.get_layer()
        return name in source.font
    except Exception:  # pragma: no cover - defensive
        return False


def extras_for_subdoc(default_source: Any, other_sources: list) -> list[str]:
    """Names the other masters carry that the default's glyph order does not.

    The default master decides what the family contains: varLib copies it and
    builds variations on top, so a glyph only another master lists is dropped
    from the compiled font. This returns those names, in the order the other
    masters introduce them.
    """
    if default_source is None:
        return []
    seen = set(source_order(default_source))
    extras: list[str] = []
    for source in other_sources:
        for name in source_order(source):
            if name in seen:
                continue
            seen.add(name)
            extras.append(name)
    return extras


__all__ = [
    "safe_glyph_order",
    "duplicate_glyph_order_names",
    "source_order",
    "owns_glyph",
    "extras_for_subdoc",
]
