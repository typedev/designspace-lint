# Copyright 2026 Alexander Lubovenko
# Licensed under the Apache License, Version 2.0

"""
avar2 `<mappings>`, read the way varLib compiles them.

What the build does with a mapping, verified against fontTools 4.65:

- Its values are design coordinates, normalized linearly with the axis'
  design triple -- `map_forward` of minimum, default and maximum -- and
  **clamped** to it (`varLib._add_avar`, `models.normalizeValue`). A value past
  the axis end is quietly moved to the end.
- An axis left out of the input is not constrained: the mapping applies at
  every value of it. An axis left out of the output is not moved.
- The mappings become one VariationModel over their inputs, which refuses two
  equal inputs ("Locations must be unique") after dropping zero coordinates --
  so two mappings from the default location, on any axes, stop the build.
- The deltas are evaluated at the coordinates *before* avar2 is applied
  (`ttLib.tables._a_v_a_r.renormalizeLocation`), so a mapping keyed on an axis
  never fires because another mapping moved that axis.
- Splitting the document for the build drops a mapping that names an axis the
  sub-font does not have -- unknown, misspelled, or discrete -- silently for an
  input and with only a log line for an output (`designspaceLib.split`).
- Masters are normalized with the same triples and never extrapolated, so an
  output past the outermost master on that side of an axis moves nothing, or
  rolls back toward the default as the last master's support tapers off.

1.18 (a mapping from the default location) lives in `axes.py`; these follow it.
"""

from __future__ import annotations

from typing import Iterator

from fontTools.varLib.models import normalizeValue

from ..axis_span import design_location
from ..model import SEVERITY_DESIGN, SEVERITY_INFO, SEVERITY_STRUCTURAL, CheckResult
from .base import format_value as _num

AVAR2_DUPLICATE_INPUT = 23
AVAR2_UNKNOWN_AXIS = 24
AVAR2_VALUE_CLAMPED = 25
AVAR2_PAST_THE_MASTERS = 26
AVAR2_CHAINED = 27
AVAR2_UNDRIVEN_HIDDEN_AXIS = 28

# Normalized coordinates compare exactly in fontTools; this only absorbs the
# float noise of our own arithmetic.
EPSILON = 1e-9


def _triples(doc) -> dict[str, tuple[float, float, float]]:
    """Design (minimum, default, maximum) of each continuous axis."""
    triples = {}
    for axis in doc.axes:
        if getattr(axis, "values", None):
            continue
        try:
            triples[axis.name] = tuple(
                axis.map_forward(v) for v in (axis.minimum, axis.default, axis.maximum)
            )
        except Exception:  # pragma: no cover - defensive
            triples[axis.name] = (axis.minimum, axis.default, axis.maximum)
    return triples


def _label(i: int) -> str:
    return f"mapping {i + 1}"


class Avar2Checks:
    """Mixed into the axes checker: `self._make_result` makes category-1 results."""

    def _check_avar2(self, doc) -> Iterator[CheckResult]:
        mappings = getattr(doc, "axisMappings", None) or []
        if not mappings:
            return
        triples = _triples(doc)
        discrete = {axis.name for axis in doc.axes if getattr(axis, "values", None)}
        tags = {axis.tag: axis.name for axis in doc.axes if axis.tag}

        yield from self._avar2_unknown_axes(mappings, triples, discrete, tags)
        yield from self._avar2_duplicate_inputs(mappings, triples)
        yield from self._avar2_clamped(mappings, triples)
        yield from self._avar2_past_the_masters(doc, mappings, triples)
        yield from self._avar2_chained(mappings, triples)
        yield from self._avar2_undriven_hidden(doc, mappings, triples)

    # --- 1.24 ------------------------------------------------------------

    def _avar2_unknown_axes(self, mappings, triples, discrete, tags) -> Iterator[CheckResult]:
        for i, mapping in enumerate(mappings):
            for side, location in (
                ("input", mapping.inputLocation),
                ("output", mapping.outputLocation),
            ):
                for name in location or {}:
                    if name in triples:
                        continue
                    if name in discrete:
                        why = f"{name} is a discrete axis, which avar2 does not vary"
                    elif name in tags:
                        why = f"{name} is not an axis name; did you mean {tags[name]}?"
                    else:
                        why = f"the designspace has no axis {name}"
                    yield self._make_result(
                        code=AVAR2_UNKNOWN_AXIS,
                        description=f"avar2 mapping {side} names {name}: the mapping is dropped",
                        location=_label(i),
                        details=(
                            f"{why[0].upper()}{why[1:]}. Splitting the designspace for the "
                            f"build leaves out any mapping that names an axis the variable "
                            f"font does not have"
                            + (
                                " -- without a message."
                                if side == "input"
                                else ", with only a line in the log."
                            )
                        ),
                        is_structural=False,
                        severity=SEVERITY_STRUCTURAL,
                        raw_data={"mappingIndex": i, "side": side, "axisName": name},
                    )

    # --- 1.23 ------------------------------------------------------------

    def _avar2_duplicate_inputs(self, mappings, triples) -> Iterator[CheckResult]:
        """Mappings varLib's model sees at one location: the build stops."""
        seen: dict[tuple, int] = {}
        for i, mapping in enumerate(mappings):
            names = set(mapping.inputLocation or {}) | set(mapping.outputLocation or {})
            if any(name not in triples for name in names):
                continue  # dropped by the split (1.24), never reaches the model
            key = []
            for name, value in (mapping.inputLocation or {}).items():
                normalized = normalizeValue(value, triples[name])
                if abs(normalized) > EPSILON:
                    key.append((name, round(normalized, 9)))
            key = tuple(sorted(key))
            if key in seen:
                first = seen[key]
                where = (
                    "the default location"
                    if not key
                    else ", ".join(f"{name} {_num(v)}" for name, v in key)
                )
                yield self._make_result(
                    code=AVAR2_DUPLICATE_INPUT,
                    description=(
                        f"avar2 mappings {first + 1} and {i + 1} have the same input: "
                        f"varLib refuses to build"
                    ),
                    location=_label(i),
                    details=(
                        f"Both read from {where} once normalized (values past the axis ends "
                        f"are clamped, axes at their default drop out). The mappings form one "
                        f'variation model, which stops with "Locations must be unique." and '
                        f"does not say which mappings."
                    ),
                    is_structural=False,
                    severity=SEVERITY_STRUCTURAL,
                    raw_data={"mappingIndex": i, "duplicateOf": first},
                )
            else:
                seen[key] = i

    # --- 1.25 ------------------------------------------------------------

    def _avar2_clamped(self, mappings, triples) -> Iterator[CheckResult]:
        """Values past the axis ends: moved to the end, without a word."""
        for i, mapping in enumerate(mappings):
            outside = []
            for side, location in (
                ("input", mapping.inputLocation),
                ("output", mapping.outputLocation),
            ):
                for name, value in (location or {}).items():
                    if name not in triples:
                        continue
                    lo, _default, hi = triples[name]
                    lo, hi = min(lo, hi), max(lo, hi)
                    if value < lo - EPSILON or value > hi + EPSILON:
                        end = lo if value < lo else hi
                        outside.append((side, name, value, end))
            if not outside:
                continue
            shown = ", ".join(
                f"{side} {name} {_num(value)} -> {_num(end)}"
                for side, name, value, end in outside[:4]
            )
            more = len(outside) - 4
            yield self._make_result(
                code=AVAR2_VALUE_CLAMPED,
                description=f"avar2 mapping value past the axis end is clamped: {shown}"
                + (f" (+{more} more)" if more > 0 else ""),
                location=_label(i),
                details=(
                    "varLib normalizes mapping values with the axis' own minimum, default and "
                    "maximum and clamps them, so the value used is the axis end. Mappings "
                    "that differ only past the end become one plateau."
                ),
                is_structural=False,
                severity=SEVERITY_DESIGN,
                raw_data={
                    "mappingIndex": i,
                    "clamped": [
                        {"side": side, "axisName": name, "value": value, "usedValue": end}
                        for side, name, value, end in outside
                    ],
                },
            )

    # --- 1.26 ------------------------------------------------------------

    def _avar2_past_the_masters(self, doc, mappings, triples) -> Iterator[CheckResult]:
        """Outputs beyond the outermost master: nothing there varies."""
        if not doc.sources:
            return
        extent: dict[str, tuple[float, float]] = {}
        for source in doc.sources:
            location = design_location(source, doc)
            for name, triple in triples.items():
                value = normalizeValue(location.get(name, triple[1]), triple)
                lo, hi = extent.get(name, (0.0, 0.0))
                extent[name] = (min(lo, value), max(hi, value))

        for i, mapping in enumerate(mappings):
            beyond = []
            for name, value in (mapping.outputLocation or {}).items():
                if name not in triples:
                    continue
                normalized = normalizeValue(value, triples[name])
                lo, hi = extent.get(name, (0.0, 0.0))
                if normalized > hi + EPSILON or normalized < lo - EPSILON:
                    beyond.append((name, value, normalized, lo, hi))
            if not beyond:
                continue
            shown = ", ".join(f"{name} {_num(value)}" for name, value, *_ in beyond)
            none_there = [name for name, _v, n, lo, hi in beyond if (hi if n > 0 else lo) == 0.0]
            yield self._make_result(
                code=AVAR2_PAST_THE_MASTERS,
                description=f"avar2 mapping sends {shown} past the outermost master",
                location=_label(i),
                details=(
                    "Masters are not extrapolated. "
                    + (
                        f"No master varies {', '.join(none_there)} on that side of the default, "
                        f"so this output moves nothing. "
                        if none_there
                        else ""
                    )
                    + "Past the last master on an axis its effect tapers back toward the "
                    "default, so the glyphs move less the further the mapping sends them."
                ),
                is_structural=False,
                severity=SEVERITY_DESIGN,
                raw_data={
                    "mappingIndex": i,
                    "axes": [
                        {"axisName": name, "value": value, "masterExtent": [lo, hi]}
                        for name, value, _n, lo, hi in beyond
                    ],
                },
            )

    # --- 1.27 ------------------------------------------------------------

    def _avar2_chained(self, mappings, triples) -> Iterator[CheckResult]:
        """One mapping's output feeding another's input: the second never sees it."""
        writers: dict[str, list[int]] = {}
        for i, mapping in enumerate(mappings):
            own_inputs = set(mapping.inputLocation or {})
            for name in mapping.outputLocation or {}:
                if name in triples and name not in own_inputs:
                    writers.setdefault(name, []).append(i)
        for j, mapping in enumerate(mappings):
            for name in mapping.inputLocation or {}:
                sources = [i for i in writers.get(name, []) if i != j]
                if not sources:
                    continue
                yield self._make_result(
                    code=AVAR2_CHAINED,
                    description=(
                        f"avar2 mapping {j + 1} reads {name}, which mapping "
                        f"{sources[0] + 1} writes: the one does not feed the other"
                    ),
                    location=_label(j),
                    details=(
                        "Every mapping is evaluated at the coordinates the user set, before "
                        "any mapping is applied. A value another mapping writes to "
                        f"{name} never reaches this mapping's input; it fires only when "
                        f"{name} itself is set."
                    ),
                    is_structural=False,
                    severity=SEVERITY_DESIGN,
                    raw_data={"mappingIndex": j, "axisName": name, "writers": sources},
                )

    # --- 1.28 ------------------------------------------------------------

    def _avar2_undriven_hidden(self, doc, mappings, triples) -> Iterator[CheckResult]:
        """A hidden axis with masters that no mapping touches."""
        touched = set()
        for mapping in mappings:
            touched |= set(mapping.inputLocation or {}) | set(mapping.outputLocation or {})
        for axis in doc.axes:
            if not getattr(axis, "hidden", False) or axis.name in touched:
                continue
            if axis.name not in triples:
                continue
            triple = triples[axis.name]
            off_default = [
                source
                for source in doc.sources
                if abs(
                    normalizeValue(design_location(source, doc).get(axis.name, triple[1]), triple)
                )
                > EPSILON
            ]
            if not off_default:
                continue
            yield self._make_result(
                code=AVAR2_UNDRIVEN_HIDDEN_AXIS,
                description=(
                    f"hidden axis {axis.name} has {len(off_default)} master(s) off its default, "
                    f"and no mapping moves it"
                ),
                location=f"axis: {axis.name}",
                details=(
                    "Applications do not offer a hidden axis, and no avar2 mapping reads or "
                    "writes this one, so its masters are reached only by setting the axis "
                    "directly. Intended for some axes, an oversight for others."
                ),
                severity=SEVERITY_INFO,
                raw_data={"axisName": axis.name, "masters": len(off_default)},
            )
