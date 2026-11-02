# Copyright 2026 Alexander Lubovenko
# Licensed under the Apache License, Version 2.0

"""
Codepoints within one master: one given to several glyphs (4.22), several on
one glyph (4.23).

ufo2ft builds a master's cmap in `makeUnicodeToGlyphNameMapping`, walking the
glyphs in its official glyph order (.notdef first, then `public.glyphOrder`,
then the rest by name) and mapping every codepoint of each. The second glyph
to claim a codepoint stops the build:

    InvalidFontData: cannot map 'A.alt' to U+0041; already mapped to 'A'

Built with ufo2ft 3.9: this happens for every master, the default or not, a
whole UFO or a layer of one, in a variable build and in a static one. A glyph
listed in the designspace's `public.skipExportGlyphs` is dropped before the
cmap is built, so it claims nothing; the UFO's own key is ignored when the
build starts from a designspace (ufo2ft and fontmake both read only the
designspace's). Several codepoints on one glyph are legal: ufo2ft maps them
all in the same loop.

4.10 compares one glyph's unicodes *across* masters; this looks inside one
master, so a duplicate in one master only gives both rows, and both are right.

`unicode_findings` works on a single layer and is public, so a host that
checks a standalone UFO (Font-Rover) runs the same rule the designspace run
does.
"""

from __future__ import annotations

from typing import Any, Iterable, Iterator

from ..glyph_order import safe_glyph_order
from ..model import CATEGORY_GLYPHS, SEVERITY_INFO, SEVERITY_STRUCTURAL, CheckResult
from .base import BaseChecker

DUPLICATE_UNICODE = 22  # one codepoint on several glyphs of a master
MULTIPLE_UNICODES = 23  # one glyph with several codepoints

SKIP_EXPORT_KEY = "public.skipExportGlyphs"
NOTDEF = ".notdef"


def _u(codepoint: int) -> str:
    return f"U+{codepoint:04X}"


def _naked(layer: Any) -> Any:
    """The defcon (or ufoLib2) layer under a fontParts one, else the layer itself."""
    naked = getattr(layer, "naked", None)
    if callable(naked):
        try:
            return naked()
        except Exception:  # pragma: no cover - defensive
            pass
    return layer


def _claims(layer: Any) -> dict[int, list[str]]:
    """Codepoint -> the glyph names in this layer that carry it.

    defcon keeps this as `layer.unicodeData`, built from the glif headers
    without loading a glyph and kept current as unicodes change. Any other
    layer is read glyph by glyph.
    """
    data = getattr(_naked(layer), "unicodeData", None)
    if data is not None:
        try:
            return {int(cp): list(names) for cp, names in data.items() if names}
        except Exception:  # pragma: no cover - defensive, fall through to the glyphs
            pass
    claims: dict[int, list[str]] = {}
    for glyph in layer:
        for cp in getattr(glyph, "unicodes", None) or ():
            claims.setdefault(int(cp), []).append(glyph.name)
    return claims


def _glyph_order_of(layer: Any) -> list[str]:
    """The glyph order of the font the layer belongs to, if it can say."""
    font = getattr(layer, "font", None)
    if font is None:
        return []
    try:
        return safe_glyph_order(font)
    except Exception:  # pragma: no cover - defensive
        return []


def build_order(glyph_order: Iterable[str]) -> dict[str, int]:
    """Rank names as ufo2ft's `makeOfficialGlyphOrder` would place them.

    .notdef first, then the glyph order; a name the order does not list goes
    after it, by name (`sorted(...)` on the rank tuples does that).
    """
    rank: dict[str, int] = {NOTDEF: -1}
    for name in glyph_order:
        rank.setdefault(name, len(rank))
    return rank


def _sorted(names: Iterable[str], rank: dict[str, int]) -> list[str]:
    unlisted = len(rank) + 1
    return sorted(set(names), key=lambda n: (rank.get(n, unlisted), n))


class _UnicodeResults(BaseChecker):
    """Makes the results, so they carry category 4 like the rest of the phase."""

    CATEGORY = CATEGORY_GLYPHS

    def check(self) -> Iterator[CheckResult]:  # pragma: no cover - not a phase
        return iter(())


def unicode_findings(
    layer: Any,
    *,
    source_name: str,
    layer_name: str | None = None,
    location: str = "",
    glyphs: Iterable[str] | None = None,
    glyph_order: Iterable[str] | None = None,
    skip_export: Iterable[str] = (),
) -> Iterator[CheckResult]:
    """4.22 and 4.23 for one layer: the glyphs one master compiles.

    Args:
        layer: a fontParts, defcon or similar layer (iterable of glyphs with
            `name` and `unicodes`; a defcon `unicodeData` is used when there).
        source_name: the `sourceName` locator.
        layer_name: the `layerName` locator; None for a UFO's default layer.
        location: the human-readable location of the findings.
        glyphs: report only codepoints one of these glyphs claims (4.22) and
            only these glyphs (4.23). None checks everything.
        glyph_order: the order ufo2ft reads the glyphs in. Defaults to the
            glyph order of `layer.font` when the layer knows its font.
        skip_export: glyphs the build leaves out. For a designspace that is
            the designspace's `public.skipExportGlyphs`; for a UFO built on
            its own, the UFO's.
    """
    claims = _claims(layer)
    skipped = set(skip_export or ())
    wanted = set(glyphs) if glyphs is not None else None
    rank = build_order(glyph_order if glyph_order is not None else _glyph_order_of(layer))
    maker = _UnicodeResults()
    locators = {"sourceName": source_name, "layerName": layer_name}

    codepoints_per_glyph: dict[str, int] = {}
    for codepoint in sorted(claims):
        names = _sorted((n for n in claims[codepoint] if n not in skipped), rank)
        for name in names:
            codepoints_per_glyph[name] = codepoints_per_glyph.get(name, 0) + 1
        if len(names) < 2 or (wanted is not None and wanted.isdisjoint(names)):
            continue
        first, second = names[0], names[1]
        listed = ", ".join(f"'{n}'" for n in names)
        yield maker._make_result(
            code=DUPLICATE_UNICODE,
            description=f"{_u(codepoint)} is given to {len(names)} glyphs: {listed}",
            glyph_name=first,
            location=location,
            details=(
                f"A codepoint maps to one glyph only. fontmake (ufo2ft) stops on the "
                f"second one: \"cannot map '{second}' to {_u(codepoint)}; already mapped "
                f"to '{first}'\". Keep the codepoint on one glyph and take it off the others."
            ),
            severity=SEVERITY_STRUCTURAL,
            raw_data={
                "glyphName": first,
                "glyphNames": names,
                "codepoint": codepoint,
                **locators,
            },
        )

    several = [n for n, count in codepoints_per_glyph.items() if count > 1]
    for name in _sorted(several, rank):
        if wanted is not None and name not in wanted:
            continue
        try:
            codepoints = [int(cp) for cp in layer[name].unicodes]
        except Exception:  # pragma: no cover - defensive
            continue
        if len(codepoints) < 2:  # pragma: no cover - changed under us
            continue
        shown = ", ".join(_u(cp) for cp in codepoints)
        yield maker._make_result(
            code=MULTIPLE_UNICODES,
            description=f"'{name}' has {len(codepoints)} unicodes: {shown}",
            glyph_name=name,
            location=location,
            details=(
                f"Legal: ufo2ft maps every codepoint of a glyph, so all of {shown} "
                f"show '{name}'. Tools that read one unicode per glyph (glyph.unicode) "
                f"see only {_u(codepoints[0])}. Characters meant to look different "
                f"need glyphs of their own."
            ),
            severity=SEVERITY_INFO,
            raw_data={"glyphName": name, "codepoints": codepoints, **locators},
        )


def designspace_skip_export(doc: Any) -> list[str]:
    """The skipExportGlyphs a designspace build honours: the designspace's own."""
    try:
        return list((getattr(doc, "lib", None) or {}).get(SKIP_EXPORT_KEY) or [])
    except Exception:  # pragma: no cover - defensive
        return []


__all__ = ["DUPLICATE_UNICODE", "MULTIPLE_UNICODES", "unicode_findings"]
