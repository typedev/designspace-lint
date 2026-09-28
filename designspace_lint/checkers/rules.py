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
- 7.7: Two rules substitute one glyph where their regions overlap

Copyright 2024-2026 TypeDev
Licensed under the Apache License, Version 2.0
"""

from __future__ import annotations

import logging
from typing import Iterator

from ..model import CATEGORY_RULES, SEVERITY_STRUCTURAL, CheckResult
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
# Codes past 6 are ours; designspaceProblems stops at 6.
RULE_OVERLAP = 7

SKIP_EXPORT_KEY = "public.skipExportGlyphs"


def _boxes(rule) -> list[dict]:
    """A rule's region as boxes, one per conditionset: axis -> (min, max).

    A condition without a minimum or maximum is open on that side, as varLib
    reads it. Coordinates stay in design space; the overlap test only needs
    their order, which normalization does not change.
    """
    boxes = []
    for cond_set in rule.conditionSets:
        box = {}
        for condition in cond_set:
            lo = condition.get("minimum")
            hi = condition.get("maximum")
            box[condition.get("name")] = (
                float("-inf") if lo is None else lo,
                float("inf") if hi is None else hi,
            )
        boxes.append(box)
    return boxes


def _boxes_overlap(a: dict, b: dict) -> bool:
    """Whether two boxes share a region with some extent on every axis.

    Touching at a boundary does not count: 400-700 and 700-900 is the usual
    way to hand one range over to the next.
    """
    for axis in set(a) | set(b):
        lo_a, hi_a = a.get(axis, (float("-inf"), float("inf")))
        lo_b, hi_b = b.get(axis, (float("-inf"), float("inf")))
        if max(lo_a, lo_b) >= min(hi_a, hi_b):
            return False
    return True


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

        # varLib checks rule glyphs against the variable font's glyph order,
        # which is the default master's: a glyph drawn only in other masters
        # stops the build ("Missing glyphs are referenced in conditional
        # substitution rules"). So the default master is what to check, not
        # every master together.
        all_glyphs: set[str] = set()
        default_label = ""
        if self.entry and self.entry.sources:
            default_source = self._default_font_source()
            if default_source is not None:
                all_glyphs = self._own_keys(default_source)
                try:
                    all_glyphs -= set(default_source.font.lib.get(SKIP_EXPORT_KEY, []))
                except Exception:  # pragma: no cover - defensive
                    pass
                default_label = self._label(default_source)

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

            conditions = getattr(rule, "conditionSets", None) or []

            # Check 7.0: a rule with no <conditionset> at all never applies:
            # `evaluateRule` is any() over no sets, and splitting the document
            # drops the rule. An *empty* <conditionset/> is the other thing --
            # the spec's way of writing an always-on rule -- and is fine.
            if not conditions:
                yield self._make_result(
                    code=RULE_NO_CONDITIONS,
                    description="rule has no conditionset, so it never applies",
                    location=rule_name,
                    details=(
                        "fontTools drops a rule without a <conditionset> when it builds or "
                        "splits the designspace. For a rule that applies everywhere, give it "
                        "an empty <conditionset/>."
                    ),
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
                            details=(
                                f"'{old_glyph}' is not exported by the default master "
                                f"{default_label}, and varLib refuses to build a rule that "
                                f"names a glyph the variable font does not have."
                            ),
                            is_structural=False,
                            severity=SEVERITY_STRUCTURAL,
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
                            details=(
                                f"'{new_glyph}' is not exported by the default master "
                                f"{default_label}, and varLib refuses to build a rule that "
                                f"names a glyph the variable font does not have."
                            ),
                            is_structural=False,
                            severity=SEVERITY_STRUCTURAL,
                            raw_data={
                                "ruleName": rule_name,
                                "glyphName": new_glyph,
                                "substitution": "target",
                            },
                        )

        yield from self._check_overlaps(doc.rules)

    def _check_overlaps(self, rules) -> Iterator[CheckResult]:
        """7.7: two rules that substitute one glyph over a shared region.

        varLib does not settle this by declaration order. Each rule becomes a
        lookup, the lookups are numbered in sorted order of their substitution
        maps (`featureVars.makeSubstitutionsHashable`), and in the overlap the
        first lookup to rewrite the glyph wins. Only rules with the same
        region are merged, and there the earlier rule wins. Static instances go
        through `processRules`, which applies rules in declaration order -- so
        the variable font and the instances can disagree about the same glyph.
        """
        prepared = []
        for i, rule in enumerate(rules):
            if not rule.conditionSets or not rule.subs:
                continue
            subs = dict(rule.subs)
            prepared.append((i, rule, _boxes(rule), subs, tuple(sorted(subs.items()))))

        for a in range(len(prepared)):
            i, rule_a, boxes_a, subs_a, key_a = prepared[a]
            for b in range(a + 1, len(prepared)):
                j, rule_b, boxes_b, subs_b, key_b = prepared[b]
                shared = sorted(
                    glyph for glyph in set(subs_a) & set(subs_b) if subs_a[glyph] != subs_b[glyph]
                )
                if not shared:
                    continue
                if not any(_boxes_overlap(x, y) for x in boxes_a for y in boxes_b):
                    continue

                name_a = rule_a.name or f"rule_{i}"
                name_b = rule_b.name or f"rule_{j}"
                same_region = sorted(map(repr, boxes_a)) == sorted(map(repr, boxes_b))
                vf_winner = name_a if same_region or key_a <= key_b else name_b
                vf_subs = subs_a if vf_winner == name_a else subs_b
                glyph = shared[0]
                agree = vf_winner == name_a
                yield self._make_result(
                    code=RULE_OVERLAP,
                    description=(
                        f"rules {name_a} and {name_b} both substitute /{glyph} where their "
                        f"regions overlap; the variable font uses {vf_winner}"
                    ),
                    location=f"{name_a}, {name_b}",
                    glyph_name=glyph,
                    details=(
                        f"In the overlap, /{glyph} becomes /{vf_subs[glyph]} in the variable "
                        f"font"
                        + (
                            ", as declared."
                            if agree
                            else (
                                f", but static instances apply rules in declaration order and "
                                f"give /{subs_a[glyph]}."
                            )
                        )
                        + " varLib orders these lookups by their substitutions, not by the "
                        "order of the rules. Make the regions disjoint to say which applies."
                        + (f" Also affected: {', '.join(shared[1:])}." if len(shared) > 1 else "")
                    ),
                    is_structural=False,
                    raw_data={
                        "rules": [name_a, name_b],
                        "glyphs": shared,
                        "variableFontRule": vf_winner,
                        "declarationOrderRule": name_a,
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
