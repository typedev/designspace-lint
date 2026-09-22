"""
Rules checker - validates rule definitions.

Category 7: Rules validation
Based on designspaceProblems checkRules().

Checks:
- 7.0: Rule has no conditions
- 7.1: Rule condition references undefined axis
- 7.2: Rule condition range invalid (min > max)
- 7.3: Rule condition range out of axis bounds
- 7.4: Rule has no substitutions
- 7.5: Rule substitution references undefined glyph
- 7.6: Duplicate rule name

Copyright 2024-2026 TypeDev
Licensed under the Apache License, Version 2.0
"""

from __future__ import annotations

import logging
from typing import Iterator

from ..model import CATEGORY_RULES, CheckResult
from .base import BaseChecker

logger = logging.getLogger(__name__)

# Error codes
RULE_NO_CONDITIONS = 0
RULE_UNDEFINED_AXIS = 1
RULE_INVALID_RANGE = 2
RULE_RANGE_OUT_OF_BOUNDS = 3
RULE_NO_SUBSTITUTIONS = 4
RULE_UNDEFINED_GLYPH = 5
RULE_DUPLICATE_NAME = 6


class RulesChecker(BaseChecker):
    """
    Validates rule definitions.

    These are design checks - they indicate issues that should be
    fixed but don't prevent the designspace from working.
    """

    CATEGORY = CATEGORY_RULES

    def check(self) -> Iterator[CheckResult]:
        """Run all rules validation checks."""
        doc = self.doc

        if not doc.rules:
            return  # No rules is valid

        # Build axis info for validation
        # Rule conditions use DESIGN-SPACE coordinates, not user-space
        axis_info = {}
        for axis in doc.axes:
            if axis.map:
                # Axis has mapping: get design-space (output) range
                outputs = [m[1] for m in axis.map]
                ds_min = min(outputs)
                ds_max = max(outputs)
            else:
                # No mapping: design-space = user-space
                ds_min = axis.minimum
                ds_max = axis.maximum

            axis_info[axis.name] = {
                "minimum": ds_min,
                "maximum": ds_max,
            }

        # Get all glyph names if we have entry
        all_glyphs: set[str] = set()
        if self.entry:
            for source in self.entry.sources:
                all_glyphs.update(source.font.keys())

        # Track rule names for duplicate detection
        seen_names: dict[str, int] = {}

        for i, rule in enumerate(doc.rules):
            rule_name = rule.name or f"rule_{i}"

            # Check 7.6: Duplicate rule name
            if rule_name in seen_names:
                yield self._make_result(
                    code=RULE_DUPLICATE_NAME,
                    description=f"Duplicate rule name: {rule_name}",
                    location=rule_name,
                    is_structural=False,
                    raw_data={
                        "ruleName": rule_name,
                        "ruleIndex": i,
                        "duplicateOf": seen_names[rule_name],
                    },
                )
            else:
                seen_names[rule_name] = i

            # Get conditions
            conditions = getattr(rule, "conditionSets", None) or []
            if not conditions:
                # Old-style conditions
                conditions = [[getattr(rule, "conditions", [])]]

            # Check 7.0: Rule has no conditions
            has_conditions = any(cond for cond_set in conditions for cond in cond_set)
            if not has_conditions:
                yield self._make_result(
                    code=RULE_NO_CONDITIONS,
                    description="Rule has no conditions",
                    location=rule_name,
                    is_structural=False,
                    raw_data={"ruleName": rule_name, "ruleIndex": i},
                )

            # Check conditions
            for cond_set in conditions:
                for condition in cond_set:
                    yield from self._check_condition(condition, rule_name, axis_info)

            # Check 7.4: Rule has no substitutions
            subs = getattr(rule, "subs", [])
            if not subs:
                yield self._make_result(
                    code=RULE_NO_SUBSTITUTIONS,
                    description="Rule has no substitutions",
                    location=rule_name,
                    is_structural=False,
                    raw_data={"ruleName": rule_name, "ruleIndex": i},
                )

            # Check 7.5: Substitution references undefined glyphs
            if all_glyphs:  # Only check if we have glyph data
                for old_glyph, new_glyph in subs:
                    if old_glyph not in all_glyphs:
                        yield self._make_result(
                            code=RULE_UNDEFINED_GLYPH,
                            description=(
                                f"Rule substitution references undefined glyph: {old_glyph}"
                            ),
                            location=rule_name,
                            glyph_name=old_glyph,
                            is_structural=False,
                            raw_data={
                                "ruleName": rule_name,
                                "glyphName": old_glyph,
                                "substitution": "source",
                            },
                        )
                    if new_glyph not in all_glyphs:
                        yield self._make_result(
                            code=RULE_UNDEFINED_GLYPH,
                            description=(
                                f"Rule substitution references undefined glyph: {new_glyph}"
                            ),
                            location=rule_name,
                            glyph_name=new_glyph,
                            is_structural=False,
                            raw_data={
                                "ruleName": rule_name,
                                "glyphName": new_glyph,
                                "substitution": "target",
                            },
                        )

    def _check_condition(self, condition, rule_name: str, axis_info: dict) -> Iterator[CheckResult]:
        """Check a single rule condition."""
        axis_name = condition.get("name")
        cond_min = condition.get("minimum")
        cond_max = condition.get("maximum")

        # Check 7.1: Condition references undefined axis
        if axis_name not in axis_info:
            yield self._make_result(
                code=RULE_UNDEFINED_AXIS,
                description=f"Rule condition references undefined axis: {axis_name}",
                location=rule_name,
                is_structural=False,
                raw_data={"ruleName": rule_name, "axisName": axis_name},
            )
            return

        axis = axis_info[axis_name]

        # Check 7.2: Invalid range (min > max)
        if cond_min is not None and cond_max is not None:
            if cond_min > cond_max:
                yield self._make_result(
                    code=RULE_INVALID_RANGE,
                    description=(
                        f"Rule condition has invalid range: "
                        f"{axis_name} min={cond_min} > max={cond_max}"
                    ),
                    location=rule_name,
                    is_structural=False,
                    raw_data={
                        "ruleName": rule_name,
                        "axisName": axis_name,
                        "minimum": cond_min,
                        "maximum": cond_max,
                    },
                )

        # Check 7.3: Range out of axis bounds
        if cond_min is not None and cond_min < axis["minimum"]:
            yield self._make_result(
                code=RULE_RANGE_OUT_OF_BOUNDS,
                description=(
                    f"Rule condition minimum below axis minimum: "
                    f"{axis_name} {cond_min} < {axis['minimum']}"
                ),
                location=rule_name,
                is_structural=False,
                raw_data={
                    "ruleName": rule_name,
                    "axisName": axis_name,
                    "conditionMinimum": cond_min,
                    "axisMinimum": axis["minimum"],
                },
            )

        if cond_max is not None and cond_max > axis["maximum"]:
            yield self._make_result(
                code=RULE_RANGE_OUT_OF_BOUNDS,
                description=(
                    f"Rule condition maximum above axis maximum: "
                    f"{axis_name} {cond_max} > {axis['maximum']}"
                ),
                location=rule_name,
                is_structural=False,
                raw_data={
                    "ruleName": rule_name,
                    "axisName": axis_name,
                    "conditionMaximum": cond_max,
                    "axisMaximum": axis["maximum"],
                },
            )
