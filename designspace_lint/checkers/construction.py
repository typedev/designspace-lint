# Copyright 2026 Alexander Lubovenko
# Licensed under the Apache License, Version 2.0

"""
How composites are built: bases first, then the marks from the bottom up.

A convention rather than a build consequence -- ufo2ft and varLib take the
components in any order, as long as the masters agree (that is 4.19). The
rule lives in `designspace_lint.construction`, where Font-Rover's fix calls
it too; this phase runs it over every master.

Codes (category 4):
- 4.20: components out of the expected order (warning)
- 4.21: components whose role the rule cannot tell (information)

Only on request (`--construction`).
"""

from __future__ import annotations

from typing import Iterator

from ..construction import canonical_component_order
from ..model import SEVERITY_DESIGN, SEVERITY_INFO, CheckResult, GlyphProblemType
from .glyphs import GlyphsChecker

COMPONENT_ORDER_CANONICAL = 20
COMPONENT_ROLE_UNKNOWN = 21


class ConstructionChecker(GlyphsChecker):
    """Checks each master's composites against the expected component order."""

    def check(self) -> Iterator[CheckResult]:
        entry = self.entry
        if entry is None:
            return
        for _discrete_loc, _sub_doc, sources, _pairs in self._slices():
            glyph_names = set()
            for source in sources:
                glyph_names |= self._own_keys(source)
            if self.only_glyphs is not None:
                glyph_names &= self.only_glyphs
            ordered = sorted(glyph_names)
            for i, glyph_name in enumerate(ordered):
                yield from self._check_composite(glyph_name, sources)
                if self._on_glyph_progress:
                    self._on_glyph_progress(i + 1, len(ordered))

    def _layers(self, source):
        """Where a master's unicodes are read, and where its outlines are drawn."""
        font = source.font
        if self._is_layer_source(source):
            return font, source.get_layer()
        return font, font

    def _check_composite(self, glyph_name: str, sources) -> Iterator[CheckResult]:
        wrong: dict[tuple, list[str]] = {}  # (current, expected) -> [sources]
        expected_orders = set()
        notes: dict[tuple, list[str]] = {}  # (index, base, reason) -> [sources]
        checked = 0  # masters with this composite
        for source in sources:
            glyph = self._own_glyph(source, glyph_name)
            if glyph is None or len(glyph.components) < 2:
                continue
            font, layer = self._layers(source)
            order, glyph_notes = canonical_component_order(glyph, font, layer)
            names = [component.baseGlyph for component in glyph.components]
            label = self._label(source)
            expected = tuple(names[i] for i in order)
            expected_orders.add(expected)
            checked += 1
            if order != sorted(order):
                wrong.setdefault((tuple(names), expected), []).append(label)
            for index, reason in glyph_notes:
                notes.setdefault((index, names[index], reason), []).append(label)

        if wrong:
            yield self._order_result(glyph_name, wrong, len(expected_orders) > 1, checked)
        if notes:
            yield self._unknown_result(glyph_name, notes)

    def _order_result(self, glyph_name, wrong, expected_differs, checked) -> CheckResult:
        ranked = sorted(wrong.items(), key=lambda item: -len(item[1]))
        groups = {f"order{i + 1}": sources for i, (_key, sources) in enumerate(ranked)}
        current = {f"order{i + 1}": list(key[0]) for i, (key, _s) in enumerate(ranked)}
        expected = {f"order{i + 1}": list(key[1]) for i, (key, _s) in enumerate(ranked)}
        first = ranked[0][0]
        description = (
            f"components out of order: {', '.join(first[0])} should be {', '.join(first[1])}"
        )
        details = (
            f"Glyph '{glyph_name}' does not list its components bases first and then the "
            f"marks from the bottom up: "
            + "; ".join(
                f"{', '.join(current[key])} should be {', '.join(expected[key])} in "
                f"{len(groups[key])} source(s)"
                for key in groups
            )
            + ". The font builds either way; this is the house order."
        )
        if expected_differs:
            description += " (the expected order differs between masters)"
            details += (
                " The marks do not stack the same way in every master, so the expected "
                "order is not the same everywhere; it is listed per group."
            )
        return self._make_result(
            code=COMPONENT_ORDER_CANONICAL,
            description=description,
            glyph_name=glyph_name,
            location=_masters_location(groups, checked),
            details=details,
            severity=SEVERITY_DESIGN,
            problem_type=GlyphProblemType.COMPONENT_MISMATCH,
            raw_data={
                "glyphName": glyph_name,
                "locationType": "groups",
                "groups": groups,
                "current": current,
                "expected": expected,
                "expectedDiffers": expected_differs,
            },
        )

    def _unknown_result(self, glyph_name, notes) -> CheckResult:
        components = [
            {"index": index, "baseGlyph": base, "reason": reason, "sources": sources}
            for (index, base, reason), sources in sorted(notes.items())
        ]
        shown = ", ".join(f"{c['baseGlyph']} ({c['reason']})" for c in components)
        return self._make_result(
            code=COMPONENT_ROLE_UNKNOWN,
            description=f"component role unknown: {shown}",
            glyph_name=glyph_name,
            details=(
                f"Glyph '{glyph_name}': the component order rule cannot tell whether "
                f"{shown} is a base or a mark. With a known base in the glyph an unknown "
                f"component is ordered as a mark; otherwise the order is left as it is."
            ),
            severity=SEVERITY_INFO,
            problem_type=GlyphProblemType.COMPONENT_MISMATCH,
            raw_data={"glyphName": glyph_name, "components": components},
        )


def _masters_location(groups: dict[str, list[str]], checked: int) -> str:
    """Which masters are out of order: named when one is, counted otherwise."""
    wrong = [source for sources in groups.values() for source in sources]
    if len(wrong) == 1:
        return wrong[0].replace(".ufo", "")
    if len(wrong) == checked:
        return f"all {checked} sources"
    return f"{len(wrong)} of {checked} sources"
