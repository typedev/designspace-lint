# Copyright 2026 Alexander Lubovenko
# Licensed under the Apache License, Version 2.0

"""
Labels checker - DesignSpace 5 axis labels, location labels and what the build
makes of them.

Category 10: Labels (ours; designspaceProblems predates DesignSpace 5)

Labels feed two things in a build (fontTools 4.65, through `varLib.build_many`,
which ufo2ft calls):

- the STAT table (`varLib.stat.buildVFStatTable`), which keeps a label only
  when its value falls inside the variable font, and validates nothing else --
  ranges, links and duplicates are written as they are;
- instance names. Splitting the document (`splitInterpolable(makeNames=True)`)
  names every instance from the labels at its location
  (`designspaceLib.statNames.getStatNames`), and keeps the author's style name
  only where the instance has localised style names of its own (any language,
  usually `xml:lang="en"`): a plain `stylename` alone is replaced
  in fvar by the name the labels spell. When every label there is elidable and
  the document has no `elidedfallbackname`, that name is empty.

Checks:
- 10.0: Instance name replaced in the variable font by the one the labels spell
- 10.1: A location value no label of its axis covers
- 10.2: A location whose labels are all elidable, with no elidedfallbackname
- 10.3: Label outside its axis, or outside a declared variable font
- 10.4: Location label that does not name every axis
- 10.5: Range label that does not hold together
- 10.6: Style linking that points nowhere, or is missing
- 10.7: Duplicate labels, and discrete values without one
"""

from __future__ import annotations

import logging
from typing import Iterator

from ..model import (
    CATEGORY_LABELS,
    SEVERITY_DESIGN,
    SEVERITY_INFO,
    SEVERITY_STRUCTURAL,
    CheckResult,
)
from .base import BaseChecker, format_value as _num

logger = logging.getLogger(__name__)

INSTANCE_NAME_REPLACED = 0
VALUE_WITHOUT_LABEL = 1
ALL_ELIDED_NO_FALLBACK = 2
LABEL_OUTSIDE = 3
PARTIAL_LOCATION_LABEL = 4
RANGE_LABEL_MALFORMED = 5
STYLE_LINK = 6
LABEL_REDUNDANT = 7

TOLERANCE = 1e-6


def _is_discrete(axis) -> bool:
    return bool(getattr(axis, "values", None))


def _matches(label, value) -> bool:
    """How `getStatNames` picks a label: its value, or its inclusive range."""
    if label.userValue == value:
        return True
    return (
        label.userMinimum is not None
        and label.userMaximum is not None
        and label.userMinimum <= value <= label.userMaximum
    )


def _in_axis(axis, value) -> bool:
    if _is_discrete(axis):
        return any(abs(value - v) <= TOLERANCE for v in axis.values)
    return axis.minimum - TOLERANCE <= value <= axis.maximum + TOLERANCE


class LabelsChecker(BaseChecker):
    """Checks DS5 labels against what STAT and the instance names will be."""

    CATEGORY = CATEGORY_LABELS

    def check(self) -> Iterator[CheckResult]:
        doc = self.doc
        if getattr(doc, "formatTuple", (5, 0)) < (5, 0):
            return
        labelled = [axis for axis in doc.axes if axis.axisLabels]
        if not labelled and not doc.locationLabels:
            return  # STAT comes from elsewhere, and names from the instances

        yield from self._check_axis_labels(doc)
        yield from self._check_location_labels(doc)
        yield from self._check_links(doc)
        yield from self._check_names(doc, labelled)
        yield from self._check_variable_fonts(doc)

    # --- the labels themselves ------------------------------------------

    def _check_axis_labels(self, doc) -> Iterator[CheckResult]:
        for axis in doc.axes:
            seen: dict[float, str] = {}
            ranges = []
            for label in axis.axisLabels:
                where = f"axis {axis.name}: {label.name}"
                if not _in_axis(axis, label.userValue):
                    yield self._make_result(
                        code=LABEL_OUTSIDE,
                        description=(
                            f"label {label.name} at {_num(label.userValue)} is outside the "
                            f"axis {axis.name}: it is left out of STAT"
                        ),
                        location=where,
                        details=(
                            "fontTools keeps an axis label in STAT only when its value lies "
                            "inside the variable font."
                        ),
                        is_structural=False,
                        severity=SEVERITY_DESIGN,
                        raw_data={"axisName": axis.name, "label": label.name},
                    )
                if label.userValue in seen:
                    yield self._make_result(
                        code=LABEL_REDUNDANT,
                        description=(
                            f"labels {seen[label.userValue]} and {label.name} share "
                            f"{axis.name} {_num(label.userValue)}"
                        ),
                        location=where,
                        details=(
                            "Both go into STAT; names are made from the first, in document order."
                        ),
                        severity=SEVERITY_INFO,
                        raw_data={
                            "axisName": axis.name,
                            "labels": [seen[label.userValue], label.name],
                        },
                    )
                else:
                    seen[label.userValue] = label.name

                lo, hi = label.userMinimum, label.userMaximum
                if lo is None or hi is None:
                    continue
                problem = None
                if lo > hi:
                    problem = f"its minimum {_num(lo)} is above its maximum {_num(hi)}"
                elif not lo <= label.userValue <= hi:
                    problem = (
                        f"its value {_num(label.userValue)} is outside its own range "
                        f"{_num(lo)}-{_num(hi)}"
                    )
                elif label.linkedUserValue is not None:
                    problem = (
                        "it has both a range and a linked value; STAT keeps the link and drops "
                        "the range"
                    )
                if problem:
                    yield self._make_result(
                        code=RANGE_LABEL_MALFORMED,
                        description=f"range label {label.name} on {axis.name}: {problem}",
                        location=where,
                        details="STAT is written from the label as it stands; nothing checks it.",
                        is_structural=False,
                        severity=SEVERITY_DESIGN,
                        raw_data={"axisName": axis.name, "label": label.name},
                    )
                else:
                    for other_lo, other_hi, other in ranges:
                        if max(lo, other_lo) < min(hi, other_hi):
                            yield self._make_result(
                                code=RANGE_LABEL_MALFORMED,
                                description=(
                                    f"range labels {other} and {label.name} overlap on {axis.name}"
                                ),
                                location=where,
                                details=(
                                    f"Between {_num(max(lo, other_lo))} and "
                                    f"{_num(min(hi, other_hi))} both apply; instance names "
                                    f"take {other}, the first in document order."
                                ),
                                is_structural=False,
                                severity=SEVERITY_DESIGN,
                                raw_data={"axisName": axis.name, "labels": [other, label.name]},
                            )
                    ranges.append((lo, hi, label.name))

            if _is_discrete(axis) and axis.axisLabels:
                labelled = {label.userValue for label in axis.axisLabels}
                for value in axis.values:
                    if not any(abs(value - v) <= TOLERANCE for v in labelled):
                        yield self._make_result(
                            code=LABEL_REDUNDANT,
                            description=(
                                f"{axis.name} {_num(value)} has no label: its variable font "
                                f"gets no STAT value for {axis.name}"
                            ),
                            location=f"axis {axis.name}",
                            severity=SEVERITY_INFO,
                            raw_data={"axisName": axis.name, "value": value},
                        )

    def _check_location_labels(self, doc) -> Iterator[CheckResult]:
        axes = {axis.name: axis for axis in doc.axes}
        for label in doc.locationLabels:
            where = f"location label {label.name}"
            location = dict(label.userLocation or {})
            missing = [name for name in axes if name not in location]
            if missing:
                yield self._make_result(
                    code=PARTIAL_LOCATION_LABEL,
                    description=(
                        f"location label {label.name} does not name {', '.join(missing)}: it "
                        f"never names an instance"
                    ),
                    location=where,
                    details=(
                        "fontTools looks a location label up by comparing its location with "
                        "the instance's full one, so a label that leaves an axis out never "
                        "matches. STAT still lists it, at the axis defaults."
                    ),
                    is_structural=False,
                    severity=SEVERITY_DESIGN,
                    raw_data={"label": label.name, "missingAxes": missing},
                )
            outside = [
                f"{name} {_num(value)}"
                for name, value in location.items()
                if name in axes and not _in_axis(axes[name], value)
            ]
            if outside:
                yield self._make_result(
                    code=LABEL_OUTSIDE,
                    description=(
                        f"location label {label.name} lies outside the axes "
                        f"({', '.join(outside)}): it is left out of STAT"
                    ),
                    location=where,
                    is_structural=False,
                    severity=SEVERITY_DESIGN,
                    raw_data={"label": label.name},
                )

    def _check_links(self, doc) -> Iterator[CheckResult]:
        """Style linking: `linkeduservalue` is what makes Bold the bold of Regular."""
        unlinked_instances = [i for i in doc.instances if not i.styleMapStyleName]
        for axis in doc.axes:
            if not axis.axisLabels:
                continue
            values = {label.userValue for label in axis.axisLabels}
            for label in axis.axisLabels:
                linked = label.linkedUserValue
                if linked is None:
                    continue
                if linked not in values or not _in_axis(axis, linked):
                    yield self._make_result(
                        code=STYLE_LINK,
                        description=(
                            f"label {label.name} links to {axis.name} {_num(linked)}, where "
                            f"there is no label"
                        ),
                        location=f"axis {axis.name}: {label.name}",
                        details=(
                            "STAT carries the link as written, and instances there cannot be "
                            "style-linked to it: a Bold named from these labels is not the "
                            "bold of anything."
                        ),
                        is_structural=False,
                        severity=SEVERITY_DESIGN,
                        raw_data={"axisName": axis.name, "label": label.name, "linked": linked},
                    )
            if not unlinked_instances or any(
                label.linkedUserValue is not None for label in axis.axisLabels
            ):
                continue
            wants_link = (axis.tag == "wght" and {400, 700} <= values) or (
                axis.tag in ("ital", "slnt") and len(values) > 1
            )
            if wants_link:
                yield self._make_result(
                    code=STYLE_LINK,
                    description=(
                        f"no label on {axis.name} links to another: instances without a "
                        f"stylemapstylename are not style-linked along it"
                    ),
                    location=f"axis {axis.name}",
                    details=(
                        f"{len(unlinked_instances)} instance(s) take their style-map names from "
                        f"the labels, which pair Regular with Bold (or Upright with Italic) "
                        f"only through linkeduservalue."
                    ),
                    severity=SEVERITY_INFO,
                    raw_data={"axisName": axis.name},
                )

    # --- the names the build makes from them --------------------------------

    def _check_names(self, doc, labelled) -> Iterator[CheckResult]:
        from fontTools.designspaceLib.statNames import getStatNames

        locations = []
        default = {axis.name: axis.default for axis in doc.axes}
        locations.append(("the default location", default, None))
        for index, instance in enumerate(doc.instances):
            try:
                location = instance.getFullUserLocation(doc)
            except Exception:
                continue  # an unknown location label: 3.12
            name = " ".join(n for n in (instance.familyName, instance.styleName) if n)
            locations.append((name or "an unnamed instance", location, (index, instance)))

        elided_everywhere = []
        for where, location, indexed in locations:
            index, instance = indexed if indexed else (None, None)
            locator = {"instanceName": instance.name, "instanceIndex": index} if instance else {}
            for axis in labelled:
                value = location.get(axis.name, axis.default)
                if not any(_matches(label, value) for label in axis.axisLabels):
                    yield self._make_result(
                        code=VALUE_WITHOUT_LABEL,
                        description=(
                            f"no label on {axis.name} covers {_num(value)}, used by {where}"
                        ),
                        location=where,
                        details=(
                            "Names made from the labels leave this axis out, and STAT has no "
                            "value for this location."
                        ),
                        is_structural=False,
                        severity=SEVERITY_DESIGN,
                        raw_data={"axisName": axis.name, "value": value, **locator},
                    )
            try:
                stat = getStatNames(doc, location).styleNames.get("en")
            except Exception as exc:
                logger.debug(f"getStatNames failed for {where}: {exc}")
                continue
            if stat == "":
                elided_everywhere.append(where)
            if instance is None or not instance.styleName:
                continue
            # The split replaces the instance's localised names with the label
            # ones only when it has none at all (`split.py`: `localisedStyleName
            # or statNames.styleNames`); with any language given, fvar adds
            # "en" from the stylename itself (`varLib._add_fvar`).
            if instance.localisedStyleName or stat is None:
                continue
            if stat == instance.styleName:
                continue
            empty = stat == ""
            yield self._make_result(
                code=INSTANCE_NAME_REPLACED,
                description=(
                    f"instance {where} gets an empty style name in the variable font"
                    if empty
                    else f"instance {where} is named {stat!r} in the variable font"
                ),
                location=where,
                details=(
                    "Splitting the designspace names each instance from the labels at its "
                    "location, and the variable font's instance name is taken from that "
                    "unless the instance has a localised style name, in any language. "
                    "Here that is "
                    f"{stat!r}, not {instance.styleName!r}. "
                    + (
                        "Every label at this location is elidable and the document has no "
                        "elidedfallbackname, so nothing is left. "
                        if empty
                        else ""
                    )
                    + 'Add <stylename xml:lang="en"> to keep the name'
                    + (", or set elidedfallbackname." if empty else ".")
                ),
                is_structural=False,
                severity=SEVERITY_STRUCTURAL if empty else SEVERITY_DESIGN,
                raw_data={
                    "styleName": instance.styleName,
                    "statStyleName": stat,
                    **locator,
                },
            )

        if elided_everywhere and not doc.elidedFallbackName:
            yield self._make_result(
                code=ALL_ELIDED_NO_FALLBACK,
                description=(
                    "no elidedfallbackname, and every label is elided at "
                    + ", ".join(elided_everywhere[:3])
                    + (
                        f" (+{len(elided_everywhere) - 3} more)"
                        if len(elided_everywhere) > 3
                        else ""
                    )
                ),
                location="designspace",
                details=(
                    "A name made from labels that are all elidable is empty unless the "
                    'document gives elidedfallbackname (usually "Regular"); the variable '
                    "font's default instance is then nameless."
                ),
                is_structural=False,
                severity=SEVERITY_DESIGN,
                raw_data={"locations": elided_everywhere},
            )

    def _check_variable_fonts(self, doc) -> Iterator[CheckResult]:
        """Labels a declared variable font's subset leaves out of its STAT."""
        if not getattr(doc, "variableFonts", None):
            return
        from fontTools.designspaceLib.types import getVFUserRegion, locationInRegion

        for vf in doc.variableFonts:
            try:
                region = getVFUserRegion(doc, vf)
            except Exception:
                continue  # 1.19 / 1.20
            dropped = []
            for axis in doc.axes:
                # A discrete axis is one value per variable font: every other
                # value's label is left out by design.
                if axis.name not in region or _is_discrete(axis):
                    continue
                for label in axis.axisLabels:
                    if not _in_axis(axis, label.userValue):
                        continue  # reported once, for the axis
                    if not locationInRegion({axis.name: label.userValue}, region):
                        dropped.append(f"{axis.name} {label.name}")
            if dropped:
                yield self._make_result(
                    code=LABEL_OUTSIDE,
                    description=(
                        f"variable font {vf.name} leaves {len(dropped)} label(s) out of its "
                        f"STAT: {', '.join(dropped[:4])}" + (" ..." if len(dropped) > 4 else "")
                    ),
                    location=f"variable font {vf.name}",
                    details=(
                        "Its subset does not reach these values. Usually intended; check the "
                        "subset if a style is missing from the font's menu."
                    ),
                    severity=SEVERITY_INFO,
                    raw_data={"variableFont": vf.name, "labels": dropped},
                )
