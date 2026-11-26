# Copyright 2026 Alexander Lubovenko
# Licensed under the Apache License, Version 2.0

"""
Contour direction, judged in each glyph on its own, and what a wrong one cuts.

Codes (category 4, group ``direction``):
- 4.29: a component runs the wrong way in its composite and cuts a hole
  where it overlaps another part: its base glyph is reversed, or it is
  mirrored there
- 4.30: a contour of the glyph runs against the convention: a counter
  running like the contour it lies in is filled; an outer contour running
  clockwise comes out of a TrueType build the wrong way and cuts ink
  wherever it overlaps
- 4.31: the default master is drawn in TrueType's direction

4.8 compares the masters with one another; these say whether they are right,
which they can all be wrong about at once. The rule is in
`designspace_lint.direction`. Roles are decided in the default master, whose
contours the others match (4.8 says where they do not); the holes are
measured in every master, since parts can touch in the bold ones only.

A part that lies entirely inside another's ink and runs against it is a
knockout -- a white digit in a black circle -- and is drawn so on purpose:
it is no hole here, and reversing the outer part alone would fill it, which
the blast radius of a fix says (``breaks``, reason "knockout").
"""

from __future__ import annotations

from typing import Iterator

from ..direction import Hole, component_pieces, contour_roles, crossing_pairs, flatten, lost_ink
from ..model import SEVERITY_DESIGN, CheckResult

PARTS_CANCEL = 29
CONTOUR_DIRECTION = 30
TRUETYPE_DIRECTION = 31

# Glyphs the convention is voted on, at most (spread over the glyph list).
_VOTERS = 400

_WORDS = {"ccw": "counter-clockwise", "cw": "clockwise"}


def _way(value: int) -> str:
    return "ccw" if value > 0 else "cw"


def _control_area(contour) -> float:
    total = 0.0
    for i in range(len(contour)):
        x0, y0 = contour[i - 1][0], contour[i - 1][1]
        x1, y1 = contour[i][0], contour[i][1]
        total += x0 * y1 - x1 * y0
    return total / 2


def _hole(hole: Hole) -> dict:
    return {"area": hole.area, "point": list(hole.point), "bbox": list(hole.bbox)}


class DirectionChecks:
    """4.29-4.31 over one interpolable slice."""

    def __init__(self, checker, sources, default_source):
        self.checker = checker
        self.sources = list(sources)
        self.default = default_source
        self.names = {id(s): checker._designspace_name(s) for s in self.sources}
        self.labels = {checker._designspace_name(s): checker._label(s) for s in self.sources}
        self._outlines: dict[tuple[int, str], tuple | None] = {}
        self._roles: dict[str, tuple] = {}
        self._used_by: dict[str, dict] = {}
        self._users: dict[str, set[str]] | None = None
        self.clockwise_outer = False

    # --- reading -----------------------------------------------------------------

    def outline(self, source, name):
        key = (id(source), name)
        if key not in self._outlines:
            from .glyphs import _Outline

            glyph = self.checker._own_glyph(source, name)
            if glyph is None:
                self._outlines[key] = None
            else:
                outline = _Outline(glyph)
                self._outlines[key] = (outline.contours, outline.components)
        return self._outlines[key]

    def _has_bases(self, source, components, seen=None) -> bool:
        """Whether this master draws every glyph the components lead to."""
        seen = set() if seen is None else seen
        for base, _t in components:
            if base in seen:
                continue
            seen.add(base)
            outline = self.outline(source, base)
            if outline is None or not self._has_bases(source, outline[1], seen):
                return False
        return True

    def pieces(self, source, components):
        return component_pieces(components, lambda name: self.outline(source, name))

    def _masters_of(self, name, count):
        """The masters drawing ``name`` with the default's contour count and all its bases,
        the default first."""
        for source in sorted(self.sources, key=lambda s: s is not self.default):
            outline = self.outline(source, name)
            if outline is None or len(outline[0]) != count:
                continue
            if outline[1] and not self._has_bases(source, outline[1]):
                continue
            yield source, outline

    def _measure(self, name, count, split) -> tuple[dict, bool]:
        """Holes per master between the part ``split`` picks and the rest.

        ``split(contours, pieces)`` returns (part, rest) polygons. Returns the
        holes by source name, knockouts left out, and whether there was one.
        """
        holes, knockout = {}, False
        for source, (contours, components) in self._masters_of(name, count):
            pieces = self.pieces(source, components) if components else []
            part, rest = split(contours, pieces)
            hole = lost_ink(part, rest)
            if hole is None:
                continue
            if hole.knockout:
                if source is self.default:
                    # a knockout is the design, as the default master draws it
                    return {}, True
                knockout = True
            else:
                holes[self.names[id(source)]] = hole
        return holes, knockout

    def contour_holes(self, name, index, count):
        def split(contours, pieces):
            polygons = [flatten(c) for c in contours]
            rest = [p for i, p in enumerate(polygons) if i != index] + [p.polygon for p in pieces]
            return [polygons[index]], rest

        return self._measure(name, count, split)

    def piece_holes(self, name, component, path, chosen, count, reverse=False):
        """Holes cut by the pieces of one component whose contours are ``chosen``."""

        def split(contours, pieces):
            part, rest = [], [flatten(c) for c in contours]
            for piece in pieces:
                if piece.component == component and piece.path == path and piece.contour in chosen:
                    part.append(piece.polygon[::-1] if reverse else piece.polygon)
                else:
                    rest.append(piece.polygon)
            return part, rest

        return self._measure(name, count, split)

    def _masters_text(self, holes: dict) -> str:
        worst = max(holes, key=lambda name: holes[name].area)
        return (
            f"{len(holes)} master{'s' if len(holes) != 1 else ''}, up to "
            f"{holes[worst].area:.0f} square units in {self.labels.get(worst, worst)}"
        )

    # --- the convention ----------------------------------------------------------

    def vote(self) -> tuple[int, int]:
        """(clockwise, all) among the default master's glyphs, by each one's largest contour."""
        names = sorted(self.checker._own_keys(self.default))
        stride = max(1, len(names) // _VOTERS)
        clockwise = total = 0
        for name in names[::stride]:
            outline = self.outline(self.default, name)
            if outline is None or not outline[0]:
                continue
            area = max((_control_area(c) for c in outline[0]), key=abs)
            if abs(area) < 1.0:
                continue
            total += 1
            clockwise += area < 0
        return clockwise, total

    # --- roles in the default master ---------------------------------------------

    def roles(self, name) -> tuple:
        """(roles, pieces) of a glyph in the default master; () when it has no contours."""
        if name not in self._roles:
            outline = self.outline(self.default, name)
            if outline is None or not outline[0]:
                self._roles[name] = ()
            else:
                contours, components = outline
                pieces = self.pieces(self.default, components) if components else []
                roles = contour_roles(contours, [p.polygon for p in pieces], self.clockwise_outer)
                self._roles[name] = (roles, pieces)
        return self._roles[name]

    def wrong_in(self, name) -> set[int]:
        found = self.roles(name)
        return {r.contour for r in found[0] if r.wrong} if found else set()

    def judged_in(self, name) -> set[int]:
        found = self.roles(name)
        return {r.contour for r in found[0] if r.judged and r.actual} if found else set()

    # --- the checks --------------------------------------------------------------

    def run(self, glyph_names, whole_master: bool) -> Iterator[CheckResult]:
        clockwise, total = self.vote()
        self.clockwise_outer = total > 0 and clockwise * 2 > total
        if self.clockwise_outer and whole_master:
            yield self._truetype_result(clockwise, total)
        names = sorted(self.checker._own_keys(self.default))
        if glyph_names is not None:
            names = [n for n in names if n in glyph_names]
        for name in names:
            if self.checker._cancel_requested():
                return
            yield from self._contour_results(name)
            yield from self._component_results(name)

    def _truetype_result(self, clockwise, total) -> CheckResult:
        return self.checker._make_result(
            code=TRUETYPE_DIRECTION,
            description=(
                f"the default master is drawn in TrueType's direction: {clockwise} of "
                f"{total} glyphs run their largest contour clockwise"
            ),
            location=self.checker._label(self.default),
            details=(
                "ufo2ft expects PostScript's direction in a UFO (outer contours "
                "counter-clockwise): it writes a CFF font as drawn and reverses the "
                "contours of a TrueType one. Drawn this way, both come out against their "
                "format's convention (FontBakery's outline_direction warns on the TrueType "
                "font), unless the TrueType build keeps the direction (fontmake "
                "--keep-direction, ufo2ft reverseDirection=False); the CFF one still runs "
                "clockwise. The other direction checks follow this master's direction."
            ),
            severity=SEVERITY_DESIGN,
            raw_data={
                "sourceName": self.names[id(self.default)],
                "clockwiseGlyphs": clockwise,
                "votedGlyphs": total,
                "convention": "truetype",
            },
        )

    def _container(self, role, pieces, count):
        if role.container is None:
            return None
        if role.container < count:
            return {"contourIndex": role.container}
        piece = pieces[role.container - count]
        return {
            "component": piece.component,
            "contourIndex": piece.contour,
            "componentPath": list(piece.path),
        }

    def _container_way(self, role, roles, pieces, count) -> int:
        if role.container is None:
            return 0
        if role.container < count:
            return roles[role.container].actual
        from ..direction import signed_area

        return 1 if signed_area(pieces[role.container - count].polygon) > 0 else -1

    def _contour_results(self, name) -> Iterator[CheckResult]:
        found = self.roles(name)
        if not found:
            return
        roles, pieces = found
        pairs = crossing_pairs(roles)
        wrong = [r for r in roles if r.wrong]
        if not wrong and not pairs:
            return
        count = len(roles)
        entries, texts = [], []
        for r in wrong:
            entry = {
                "contourIndex": r.contour,
                "role": r.role,
                "depth": r.depth,
                "expected": _way(r.expected),
                "actual": _way(r.actual),
                "container": self._container(r, pieces, count),
            }
            text = (
                f"contour {r.contour} ({r.role}) runs {_WORDS[entry['actual']]}, "
                f"{_WORDS[entry['expected']]} expected"
            )
            holes = {}
            if r.depth % 2 and r.reason != "crossing":
                if self._container_way(r, roles, pieces, count) == r.actual:
                    entry["consequence"] = "filledCounter"
                    text += ": it runs like the contour it lies in, so the counter is filled"
                else:
                    entry["consequence"] = "againstConvention"
                    text += (
                        ": so does the contour it lies in, so it still shows, but a TrueType "
                        "build turns both the wrong way"
                    )
            else:
                holes, knockout = self.contour_holes(name, r.contour, count)
                if holes:
                    entry["consequence"] = "cutsInk"
                    text += f": it cuts ink where it overlaps, in {self._masters_text(holes)}"
                else:
                    entry["consequence"] = "againstConvention"
                    text += (
                        ": what lies inside it shows through, as a knockout, and a TrueType "
                        "build turns it the wrong way"
                        if knockout
                        else ": alone it looks the same, but a TrueType build turns it the "
                        "wrong way"
                    )
            entry["holes"] = {m: _hole(h) for m, h in holes.items()}
            entries.append(entry)
            texts.append(text)
        by_index = {r.contour: r for r in roles}
        for i, j in pairs:
            texts.append(
                f"contours {i} and {j} cross inside the same contour and run the same way: "
                "one of them should run the other way (or two counters overlap, which no "
                "direction fixes)"
            )
            for a, b in ((i, j), (j, i)):
                r = by_index[a]
                holes, _knockout = self.contour_holes(name, a, count)
                entries.append(
                    {
                        "contourIndex": a,
                        "role": r.role,
                        "depth": r.depth,
                        "actual": _way(r.actual),
                        "container": self._container(r, pieces, count),
                        "ambiguous": True,
                        "crosses": [b],
                        "consequence": "cutsInk" if holes else "againstConvention",
                        "holes": {m: _hole(h) for m, h in holes.items()},
                    }
                )
        entries.sort(key=lambda e: e["contourIndex"])
        raw = {
            "glyphName": name,
            "contours": entries,
            "convention": "truetype" if self.clockwise_outer else "postscript",
        }
        advice = " Reverse it in every master, keeping its start point."
        if wrong and self.users().get(name):
            used = self.used_by(name)
            raw["usedBy"] = used
            if used["breaks"]:
                knockouts = [e for e in used["breaks"] if e["reason"] == "knockout"]
                advice = (
                    f" It is used as a component: reversing it would cut or fill "
                    f"{len(used['breaks'])} composite(s)"
                    + (
                        f", {len(knockouts)} of which knock their inner part out of it, "
                        "drawn so on purpose"
                        if knockouts
                        else ""
                    )
                    + " (see usedBy)."
                )
        first = entries[0]
        if len(entries) == 1 and first["consequence"] == "filledCounter":
            description = (
                f"counter (contour {first['contourIndex']}) runs like its outer contour: filled"
            )
        elif len(entries) == 1 and first["consequence"] == "cutsInk":
            description = f"contour {first['contourIndex']} runs the wrong way and cuts ink"
        elif pairs and len(entries) == 2:
            description = f"contours {pairs[0][0]} and {pairs[0][1]} cross and run the same way"
        elif len(entries) == 1:
            description = f"contour {first['contourIndex']} runs against the convention"
        else:
            description = f"{len(entries)} contours run the wrong way"
        yield self.checker._make_result(
            code=CONTOUR_DIRECTION,
            description=description,
            glyph_name=name,
            location=self.checker._label(self.default),
            details=(
                "Renderers fill by the nonzero rule: a counter is a hole because it runs "
                "against its outer contour, and overlapping ink stays ink only where it runs "
                "the same way. " + "; ".join(texts) + "." + advice
            ),
            severity=SEVERITY_DESIGN,
            raw_data=raw,
        )

    # --- 4.29 ----------------------------------------------------------------------

    def _groups(self, name):
        """Per (component, path): the base's contours that run the wrong way here, and why."""
        outline = self.outline(self.default, name)
        if outline is None or not outline[1]:
            return {}
        groups: dict[tuple, dict] = {}
        for piece in self.pieces(self.default, outline[1]):
            base = piece.path[-1]
            if piece.contour not in self.judged_in(base):
                continue
            reversed_base = piece.contour in self.wrong_in(base)
            mirrored = piece.determinant < 0
            if reversed_base == mirrored:
                continue  # right, or wrong twice over
            group = groups.setdefault(
                (piece.component, piece.path),
                {"cause": "baseReversed" if reversed_base else "mirrored", "contours": set()},
            )
            group["contours"].add(piece.contour)
        return groups

    def _component_results(self, name) -> Iterator[CheckResult]:
        groups = self._groups(name)
        if not groups:
            return
        count = len(self.outline(self.default, name)[0])
        for (component, path), group in sorted(groups.items()):
            holes, _knockout = self.piece_holes(name, component, path, group["contours"], count)
            if not holes:
                continue
            base = path[-1]
            raw = {
                "glyphName": name,
                "componentIndex": component,
                "baseGlyph": base,
                "componentPath": [name, *path],
                "cause": group["cause"],
                "holes": {m: _hole(h) for m, h in holes.items()},
            }
            where = self._masters_text(holes)
            if group["cause"] == "mirrored":
                raw["determinant"] = self._determinants(name, component, path)
                why = (
                    f"It is mirrored here, which turns its direction round, while {base} "
                    f"itself runs the right way: the fix is here, a copy of {base} drawn the "
                    "other way, or the component decomposed and reversed"
                )
            else:
                raw["reverse"] = sorted(self.wrong_in(base))
                used = raw["usedBy"] = self.used_by(base)
                why = (
                    f"{base} runs the wrong way (4.30 on it); reversing it fixes "
                    f"{len(used['fixes'])} composite(s)"
                    + (
                        f" and cuts or fills {len(used['breaks'])} (see usedBy)"
                        if used["breaks"]
                        else ""
                    )
                )
            yield self.checker._make_result(
                code=PARTS_CANCEL,
                description=f"component {component} ({base}) cuts a hole where it overlaps",
                glyph_name=name,
                location=where,
                details=(
                    "Overlapping parts stay ink only where they run the same way; this one "
                    f"runs the other way and their windings cancel, in {where}. A variable "
                    "font shows the hole, and so does a static one that keeps its overlaps; a "
                    "CFF build that removes overlaps bakes it into the outline. " + why + "."
                ),
                severity=SEVERITY_DESIGN,
                raw_data=raw,
            )

    def _determinants(self, name, component, path) -> dict:
        found = {}
        for source in self.sources:
            outline = self.outline(source, name)
            if outline is None or not outline[1]:
                continue
            for piece in self.pieces(source, outline[1]):
                if piece.component == component and piece.path == path:
                    found[self.names[id(source)]] = round(piece.determinant, 4)
                    break
        return found

    # --- what reversing a base glyph does --------------------------------------------

    def users(self) -> dict[str, set[str]]:
        """Base glyph -> the glyphs that use it as a component, in the default master."""
        if self._users is None:
            self._users = {}
            for glyph in sorted(self.checker._own_keys(self.default)):
                outline = self.outline(self.default, glyph)
                for base, _t in outline[1] if outline else ():
                    self._users.setdefault(base, set()).add(glyph)
        return self._users

    def used_by(self, base: str) -> dict:
        """What reversing the wrong contours of ``base`` does to every composite drawing it."""
        if base in self._used_by:
            return self._used_by[base]
        chosen = self.wrong_in(base)
        users = self.users()
        seen, queue = set(), sorted(users.get(base, ()))
        while queue:
            glyph = queue.pop(0)
            if glyph not in seen:
                seen.add(glyph)
                queue.extend(sorted(users.get(glyph, ())))
        result: dict[str, list] = {"fixes": [], "unaffected": [], "breaks": []}
        for glyph in sorted(seen):
            outline = self.outline(self.default, glyph)
            count = len(outline[0])
            keys = sorted(
                {
                    (p.component, p.path, p.determinant < 0)
                    for p in self.pieces(self.default, outline[1])
                    if p.path[-1] == base
                }
            )
            for component, path, mirrored in keys:
                entry = {
                    "glyphName": glyph,
                    "componentIndex": component,
                    "componentPath": [glyph, *path],
                }
                if mirrored:
                    # right here only because it is mirrored: reversed, it cuts
                    after, _k = self.piece_holes(glyph, component, path, chosen, count, True)
                    if after:
                        result["breaks"].append(
                            {**entry, "masters": sorted(after), "reason": "mirrored"}
                        )
                        continue
                else:
                    now, knockout = self.piece_holes(glyph, component, path, chosen, count)
                    if now:
                        result["fixes"].append({**entry, "masters": sorted(now)})
                        continue
                    if knockout:
                        # what lies inside it shows through; reversed, it is filled
                        masters = [self.names[id(s)] for s, _o in self._masters_of(glyph, count)]
                        result["breaks"].append(
                            {**entry, "masters": sorted(masters), "reason": "knockout"}
                        )
                        continue
                result["unaffected"].append(entry)
        self._used_by[base] = result
        return result
