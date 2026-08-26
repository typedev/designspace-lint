# Copyright 2024 Alexander Lubovenko
# Licensed under the Apache License, Version 2.0

"""
Defensive helpers for reading a font's glyph order.

``public.glyphOrder`` is a plain list in the UFO, and nothing on the writing
side checks it for repeats. Real sources carry them: Glyphs.app hands its
``glyphOrder`` custom parameter through unvalidated, so a designer who pastes a
name into the list twice ships a UFO whose order lists 813 names for 812 glyphs.

fontParts normalizes the list on *read* and refuses it::

    ValueError: Duplicate glyph names are not allowed.
                Glyph name(s) 'acutecomb' are duplicate.

The getter raises before the caller sees anything, so the common
``font.glyphOrder or font.keys()`` idiom does not protect against it either --
``or`` is never evaluated. In the grid that surfaced as a window with no glyphs
at all: ``prepare_placeholders`` died on the very first line that asked for the
order, and the font behind it was perfectly loadable.

A duplicate carries no information -- the second occurrence cannot place a
glyph that the first one already placed -- so the repair is to keep the first
occurrence and drop the rest, never to reject the font.
"""

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


def normalize_glyph_order(font: Any) -> int:
    """Rewrite a font's glyphOrder without repeats, in place.

    Unlike `safe_glyph_order` this changes the font, so the next writer puts a
    clean list on disk. A font whose order is already clean is left untouched
    and is *not* marked dirty.

    Args:
        font: fontParts (or defcon) font object.

    Returns:
        How many entries were removed; 0 when there was nothing to repair.
    """
    raw = _raw_glyph_order(font)
    if not raw:
        return 0

    kept = _first_wins(raw)
    removed = len(raw) - len(kept)
    if not removed:
        return 0

    font.glyphOrder = kept
    logger.info(
        "Removed %d duplicate name(s) from glyphOrder: %s",
        removed,
        ", ".join(duplicate_glyph_order_names(raw)),
    )
    return removed
