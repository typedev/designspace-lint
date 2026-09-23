# Copyright 2024-2026 TypeDev
# Licensed under the Apache License, Version 2.0

"""
Reading kerning from a UFO that may not be readable.

fontParts normalizes kerning as it hands it over, and refuses outright when a
key breaks its rules -- an empty glyph or group name raises "Kerning key items
must be at least one character long". Real families carry such files: Amstelvar
has one, written by a tool years ago, and nothing has complained since.

A validator that dies on the file it is meant to report on is no use, so this
goes around the normalizer the way `safe_glyph_order` does, and hands back both
the pairs it could read and the keys it had to refuse -- so the malformed ones
become a finding rather than a crashed phase.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _raw_kerning(font: Any) -> dict | None:
    """The kerning as stored, bypassing fontParts' normalizer."""
    naked = getattr(font, "naked", None)
    if naked is not None:
        try:
            return dict(naked().kerning)
        except Exception:  # pragma: no cover - defensive
            return None
    return None


def malformed_keys(pairs: dict) -> list[tuple]:
    """Pairs whose key a UFO reader will refuse: an empty or non-string side."""
    bad = []
    for key in pairs:
        if not isinstance(key, tuple) or len(key) != 2:
            bad.append(key)
            continue
        first, second = key
        if not isinstance(first, str) or not isinstance(second, str) or not first or not second:
            bad.append(key)
    return bad


def safe_kerning(font: Any) -> tuple[dict, list[tuple]]:
    """Read a font's kerning without letting a malformed key raise.

    Returns:
        ``(pairs, malformed)`` -- the pairs that can be used, and the keys that
        cannot. When the font reads normally, ``malformed`` is empty.
    """
    try:
        return dict(font.kerning), []
    except Exception as exc:
        logger.debug("fontParts refused this kerning (%s); reading it raw", exc)

    raw = _raw_kerning(font)
    if raw is None:
        return {}, []

    bad = malformed_keys(raw)
    usable = {k: v for k, v in raw.items() if k not in bad}
    return usable, bad


__all__ = ["safe_kerning", "malformed_keys"]
