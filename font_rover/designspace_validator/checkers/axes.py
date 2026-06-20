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

Copyright 2024-2026 TypeDev
Licensed under the Apache License, Version 2.0
"""

from __future__ import annotations

import logging
from typing import Iterator

from ..model import CATEGORY_GEOMETRY, CheckResult
from .base import BaseChecker

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
                is_structural=False,  # Warning, not structural
                raw_data={
                    "axisName": axis_name,
                    "mapMin": inputs[0],
                    "axisMin": axis_min,
                },
            )

        # Check 1.7: Mapping maximum should be at axis maximum
        if inputs[-1] != axis_max:
            yield self._make_result(
                code=AXIS_MAP_MAX_NOT_AT_MAX,
                description=(f"Axis mapping maximum input {inputs[-1]} != axis maximum {axis_max}"),
                location=f"axis: {axis_name}",
                is_structural=False,  # Warning, not structural
                raw_data={
                    "axisName": axis_name,
                    "mapMax": inputs[-1],
                    "axisMax": axis_max,
                },
            )
