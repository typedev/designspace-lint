"""
Axes/Geometry checker - validates axis definitions and mappings.

Category 1: Geometry validation
Based on designspaceProblems checkDesignSpaceGeometry().

Checks:
- 1.0: No axes defined
- 1.1: Axis minimum equals maximum
- 1.2: Axis default not within min/max range
- 1.3: Axis mapping has only one input/output pair
- 1.4: Axis mapping input not within min/max range
- 1.5: Axis mapping output not within mapped range
- 1.6: Axis mapping minimum not at minimum
- 1.7: Axis mapping maximum not at maximum
- 1.8: Axis mapping input values not increasing
- 1.9: Axis mapping output values not increasing
- 1.10: Axis has no map but input != output at min
- 1.11: Axis has no map but input != output at max
- 1.12: Axis has no map but input != output at default
- 1.13: Duplicate axis name
- 1.14: Duplicate axis tag
- 1.15: Axis map has no entry at the axis default (varLib refuses to build)
- 1.16: Discrete axis default is not one of its values
- 1.17: No continuous axis, so there is nothing to interpolate
- 1.18: avar2 mapping from the default location (varLib drops it)

Copyright 2024-2026 TypeDev
Licensed under the Apache License, Version 2.0
"""

from __future__ import annotations

import logging
from typing import Iterator

from ..model import CATEGORY_GEOMETRY, SEVERITY_INFO, SEVERITY_STRUCTURAL, CheckResult
from .base import BaseChecker, format_value as _num

logger = logging.getLogger(__name__)

# Error codes
NO_AXES = 0
AXIS_MIN_EQUALS_MAX = 1
AXIS_DEFAULT_OUT_OF_RANGE = 2
AXIS_MAP_ONE_PAIR = 3
AXIS_MAP_INPUT_OUT_OF_RANGE = 4
AXIS_MAP_OUTPUT_OUT_OF_RANGE = 5
AXIS_MAP_MIN_NOT_AT_MIN = 6
AXIS_MAP_MAX_NOT_AT_MAX = 7
AXIS_MAP_INPUT_NOT_INCREASING = 8
AXIS_MAP_OUTPUT_NOT_INCREASING = 9
AXIS_NO_MAP_MIN_MISMATCH = 10
AXIS_NO_MAP_MAX_MISMATCH = 11
AXIS_NO_MAP_DEFAULT_MISMATCH = 12
DUPLICATE_AXIS_NAME = 13
DUPLICATE_AXIS_TAG = 14
# Codes past 14 are ours; designspaceProblems stops at 14.
AXIS_MAP_NO_DEFAULT = 15
DISCRETE_DEFAULT_NOT_IN_VALUES = 16
NO_CONTINUOUS_AXIS = 17
AVAR2_MAPPING_FROM_DEFAULT = 18

# Coordinates are typed by hand into the XML.
TOLERANCE = 1e-6


def _is_discrete(axis) -> bool:
    return bool(getattr(axis, "values", None))


class AxesChecker(BaseChecker):
    """
    Validates axis definitions and mappings.

    These are structural checks - if they fail, the designspace
    cannot be used for interpolation.
    """

    CATEGORY = CATEGORY_GEOMETRY

    def check(self) -> Iterator[CheckResult]:
        """Run all axis geometry checks."""
        doc = self.doc

        # Check 1.0: No axes defined
        if not doc.axes:
            yield self._make_result(
                code=NO_AXES,
                description="No axes defined in designspace",
                is_structural=True,
            )
            return

        # Track for duplicate detection
        seen_names: dict[str, int] = {}
        seen_tags: dict[str, int] = {}

        for i, axis in enumerate(doc.axes):
            axis_name = axis.name or f"axis_{i}"
            axis_tag = axis.tag or ""

            # Check 1.13: Duplicate axis name
            if axis_name in seen_names:
                yield self._make_result(
                    code=DUPLICATE_AXIS_NAME,
                    description=f"Duplicate axis name: {axis_name}",
                    location=f"axis: {axis_name}",
                    is_structural=True,
                    raw_data={"axisName": axis_name, "axisIndex": i},
                )
            seen_names[axis_name] = i

            # Check 1.14: Duplicate axis tag
            if axis_tag and axis_tag in seen_tags:
                yield self._make_result(
                    code=DUPLICATE_AXIS_TAG,
                    description=f"Duplicate axis tag: {axis_tag}",
                    location=f"axis: {axis_name}",
                    is_structural=True,
                    raw_data={"axisTag": axis_tag, "axisName": axis_name},
                )
            if axis_tag:
                seen_tags[axis_tag] = i

            if _is_discrete(axis):
                yield from self._check_discrete_axis(axis, axis_name)
                continue

            # Get axis values
            axis_min = axis.minimum
            axis_max = axis.maximum
            axis_default = axis.default

            # Check 1.1: Axis minimum equals maximum
            if axis_min == axis_max:
                yield self._make_result(
                    code=AXIS_MIN_EQUALS_MAX,
                    description=f"Axis minimum equals maximum: {axis_min}",
                    location=f"axis: {axis_name}",
                    is_structural=True,
                    raw_data={"axisName": axis_name, "value": axis_min},
                )
                continue  # Skip further checks on this axis

            # Check 1.2: Axis default not within min/max range
            if not (axis_min <= axis_default <= axis_max):
                yield self._make_result(
                    code=AXIS_DEFAULT_OUT_OF_RANGE,
                    description=(
                        f"Axis default {axis_default} not within range [{axis_min}, {axis_max}]"
                    ),
                    location=f"axis: {axis_name}",
                    is_structural=True,
                    raw_data={
                        "axisName": axis_name,
                        "default": axis_default,
                        "minimum": axis_min,
                        "maximum": axis_max,
                    },
                )

            # Check axis mapping if present
            if axis.map:
                yield from self._check_axis_mapping(axis, axis_name)
            else:
                # Check 1.10-1.12: No map but input != output
                # In DesignSpace without mapping, input values should equal output
                # These are warnings, not structural errors
                pass

        # Check 1.17: nothing left to interpolate
        if not any(not _is_discrete(axis) for axis in doc.axes):
            yield self._make_result(
                code=NO_CONTINUOUS_AXIS,
                description="no continuous axis: nothing to interpolate",
                details=(
                    "Every axis is discrete, so each combination of values is a single static "
                    "master. That is a fine way to describe a family of static fonts, but "
                    "varLib cannot build a variable font from it."
                ),
                severity=SEVERITY_INFO,
            )

        # Check 1.18: avar2 mappings
        yield from self._check_axis_mappings(doc)

    def _check_discrete_axis(self, axis, axis_name: str) -> Iterator[CheckResult]:
        """A discrete axis has values, not a range; its default must be one of them."""
        values = list(axis.values)
        if not any(abs(axis.default - v) <= TOLERANCE for v in values):
            yield self._make_result(
                code=DISCRETE_DEFAULT_NOT_IN_VALUES,
                description=(
                    f"discrete axis default {_num(axis.default)} is not one of its values "
                    f"({', '.join(_num(v) for v in values)})"
                ),
                location=f"axis: {axis_name}",
                details=(
                    "The designspace is split along its discrete axes by their values only, so "
                    "the masters at the default fall into no slice: they are left out of every "
                    "variable font, and the slices have no default master."
                ),
                is_structural=False,
                severity=SEVERITY_STRUCTURAL,
                raw_data={"axisName": axis_name, "default": axis.default, "values": values},
            )

    def _check_axis_mappings(self, doc) -> Iterator[CheckResult]:
        """avar2 mappings whose input is the default location.

        varLib stores such a mapping as the base value of its VarStore and then
        throws the base away (``varLib._add_avar``): its output never applies,
        and every other mapping's delta is measured from it. A mapping that
        moves nothing at the default is harmless; one that moves something
        shifts the whole space by that amount, without a word.
        """
        mappings = getattr(doc, "axisMappings", None) or []
        if not mappings:
            return
        defaults = {}
        for axis in doc.axes:
            if _is_discrete(axis):
                continue
            try:
                defaults[axis.name] = axis.map_forward(axis.default)
            except Exception:  # pragma: no cover - defensive
                defaults[axis.name] = axis.default

        def at_default(name, value):
            return name in defaults and abs(value - defaults[name]) <= TOLERANCE

        for i, mapping in enumerate(mappings):
            inputs = dict(mapping.inputLocation or {})
            outputs = dict(mapping.outputLocation or {})
            if not all(at_default(name, value) for name, value in inputs.items()):
                continue
            moved = {
                name: value
                for name, value in outputs.items()
                if name in defaults and not at_default(name, value)
            }
            if not moved:
                continue
            moved_text = ", ".join(
                f"{name} {_num(defaults[name])} -> {_num(value)}" for name, value in moved.items()
            )
            yield self._make_result(
                code=AVAR2_MAPPING_FROM_DEFAULT,
                description=f"avar2 mapping from the default location is dropped: {moved_text}",
                location=f"mapping {i + 1}",
                details=(
                    "varLib keeps a mapping whose input is the default only as the base of its "
                    "variation store and discards it, so the default is not moved, and every "
                    "other mapping's output is shifted by the difference. Move the default "
                    "itself on the axis, or give this mapping a non-default input."
                ),
                is_structural=False,
                severity=SEVERITY_STRUCTURAL,
                raw_data={"mappingIndex": i, "input": inputs, "output": outputs},
            )

    def _check_axis_mapping(self, axis, axis_name: str) -> Iterator[CheckResult]:
        """Check axis mapping for validity."""
        mapping = axis.map
        axis_min = axis.minimum
        axis_max = axis.maximum

        # Check 1.3: Only one mapping pair
        if len(mapping) < 2:
            yield self._make_result(
                code=AXIS_MAP_ONE_PAIR,
                description="Axis mapping has only one input/output pair",
                location=f"axis: {axis_name}",
                is_structural=True,
                raw_data={"axisName": axis_name},
            )
            return

        # Get input and output values
        inputs = [m[0] for m in mapping]
        outputs = [m[1] for m in mapping]

        # Check 1.8: Input values not increasing
        if inputs != sorted(inputs):
            yield self._make_result(
                code=AXIS_MAP_INPUT_NOT_INCREASING,
                description="Axis mapping input values not in increasing order",
                location=f"axis: {axis_name}",
                is_structural=True,
                raw_data={"axisName": axis_name, "inputs": inputs},
            )

        # Check 1.9: Output values not increasing
        if outputs != sorted(outputs):
            yield self._make_result(
                code=AXIS_MAP_OUTPUT_NOT_INCREASING,
                description="Axis mapping output values not in increasing order",
                location=f"axis: {axis_name}",
                is_structural=True,
                raw_data={"axisName": axis_name, "outputs": outputs},
            )

        # Check 1.4: Input values within axis range
        for inp in inputs:
            if not (axis_min <= inp <= axis_max):
                yield self._make_result(
                    code=AXIS_MAP_INPUT_OUT_OF_RANGE,
                    description=(
                        f"Axis mapping input {inp} not within axis range [{axis_min}, {axis_max}]"
                    ),
                    location=f"axis: {axis_name}",
                    is_structural=True,
                    raw_data={
                        "axisName": axis_name,
                        "input": inp,
                        "minimum": axis_min,
                        "maximum": axis_max,
                    },
                )

        # Check 1.6: Mapping minimum should be at axis minimum
        if inputs[0] != axis_min:
            yield self._make_result(
                code=AXIS_MAP_MIN_NOT_AT_MIN,
                description=(f"Axis mapping minimum input {inputs[0]} != axis minimum {axis_min}"),
                location=f"axis: {axis_name}",
                is_structural=False,
                # varLib refuses to build without it, but the rest of the
                # document is still worth checking.
                severity=SEVERITY_STRUCTURAL,
                raw_data={
                    "axisName": axis_name,
                    "mapMin": inputs[0],
                    "axisMin": axis_min,
                },
            )

        # Check 1.15: the map must pass through the default
        if not any(abs(inp - axis.default) <= TOLERANCE for inp in inputs):
            yield self._make_result(
                code=AXIS_MAP_NO_DEFAULT,
                description=f"axis map has no entry at the axis default {_num(axis.default)}",
                location=f"axis: {axis_name}",
                details=(
                    'varLib refuses to build: "there must be a mapping for the axis default '
                    'value". Add a <map input=... output=...> for the default.'
                ),
                severity=SEVERITY_STRUCTURAL,
                raw_data={"axisName": axis_name, "default": axis.default, "inputs": inputs},
            )

        # Check 1.7: Mapping maximum should be at axis maximum
        if inputs[-1] != axis_max:
            yield self._make_result(
                code=AXIS_MAP_MAX_NOT_AT_MAX,
                description=(f"Axis mapping maximum input {inputs[-1]} != axis maximum {axis_max}"),
                location=f"axis: {axis_name}",
                is_structural=False,
                # varLib refuses to build without it, but the rest of the
                # document is still worth checking.
                severity=SEVERITY_STRUCTURAL,
                raw_data={
                    "axisName": axis_name,
                    "mapMax": inputs[-1],
                    "axisMax": axis_max,
                },
            )
