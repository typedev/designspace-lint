"""
Instances checker - validates instance definitions.

Category 3: Instance validation
Based on designspaceProblems checkInstances().

Checks (codes match designspaceProblems):
- 3.1: Instance location missing
- 3.2: Instance location has value for undefined axis
- 3.3: Instance location has out of bounds value
- 3.4: Multiple instances on location
- 3.5: Instance location requires extrapolation (same as 3.3)
- 3.6: Missing family name
- 3.7: Missing style name
- 3.8: Missing output path (filename)
- 3.10: No instances defined
- 3.11: Instance at a discrete-axis value the axis does not declare
- 3.12: Instance refers to a location label the document does not have
- 3.13: Two instances with one name at different locations

Copyright 2024-2026 TypeDev
Licensed under the Apache License, Version 2.0
"""

from __future__ import annotations

import logging
from typing import Iterator

from ..model import CATEGORY_INSTANCES, SEVERITY_DESIGN, SEVERITY_STRUCTURAL, CheckResult
from .base import BaseChecker, format_value as _num
from ..raw_xml import undeclared_axis_dimensions
from .sources import discrete_value_problems

logger = logging.getLogger(__name__)

# Error codes (match designspaceProblems exactly)
INSTANCE_LOCATION_MISSING = 1  # 3,1
INSTANCE_UNDEFINED_AXIS = 2  # 3,2
INSTANCE_OUT_OF_BOUNDS = 3  # 3,3
INSTANCE_MULTIPLE_ON_LOCATION = 4  # 3,4
INSTANCE_REQUIRES_EXTRAPOLATION = 5  # 3,5 (same as out of bounds)
INSTANCE_MISSING_FAMILY_NAME = 6  # 3,6
INSTANCE_MISSING_STYLE_NAME = 7  # 3,7
INSTANCE_MISSING_FILENAME = 8  # 3,8
INSTANCE_NONE_DEFINED = 10  # 3,10
# Codes past 10 are ours; designspaceProblems stops at 10.
INSTANCE_OFF_DISCRETE_VALUES = 11
INSTANCE_UNKNOWN_LOCATION_LABEL = 12
INSTANCE_NAME_REUSED = 13


def _instance_name(instance) -> str:
    """Family and style, whichever of them the instance has."""
    return " ".join(n for n in (instance.familyName, instance.styleName) if n) or "unnamed"


def _pretty_location(location: dict) -> str:
    """Format location dict as readable string."""
    if not location:
        return "no location"
    parts = []
    for k, v in sorted(location.items()):
        if isinstance(v, float) and v == int(v):
            parts.append(f"{k}:{int(v)}")
        else:
            parts.append(f"{k}:{v}")
    return ", ".join(parts)


class InstancesChecker(BaseChecker):
    """
    Validates instance definitions.

    Matches designspaceProblems checkInstances() behavior exactly.
    """

    CATEGORY = CATEGORY_INSTANCES

    def check(self) -> Iterator[CheckResult]:
        """Run all instance validation checks."""
        doc = self.doc

        # 3,10: No instances defined
        if not doc.instances or len(doc.instances) == 0:
            yield self._make_result(
                code=INSTANCE_NONE_DEFINED,
                description="no instances defined",
                location="designspace",
                is_structural=False,
                raw_data={},
            )
            return

        # Build axis info for validation
        # Get axis ranges (design-space coordinates via mapping)
        axis_values = {}
        for axis in doc.axes:
            if axis.map:
                # Axis has mapping: get design-space (output) range
                outputs = [m[1] for m in axis.map]
                ds_min = min(outputs)
                ds_max = max(outputs)
                # Also get mapped default
                ds_def = axis.default
                for input_val, output_val in axis.map:
                    if input_val == axis.default:
                        ds_def = output_val
                        break
            else:
                # No mapping: design-space = user-space
                ds_min = axis.minimum
                ds_max = axis.maximum
                ds_def = axis.default

            axis_values[axis.name] = (ds_min, ds_def, ds_max)

        # Track locations for duplicate detection
        all_locations: dict[tuple, list] = {}
        # And names, for the reverse: one name at several locations
        all_names: dict[tuple, list] = {}
        label_names = {label.name for label in getattr(doc, "locationLabels", None) or []}

        for i, instance in enumerate(doc.instances):
            # An unknown location label is reported by check_document (3.12);
            # there is no location here to check.
            label = getattr(instance, "locationLabel", None)
            if label and label not in label_names:
                continue

            # Get full design location
            try:
                location = instance.getFullDesignLocation(doc)
            except Exception:
                location = getattr(instance, "location", None) or getattr(
                    instance, "designLocation", None
                )

            # 3,1: Instance location missing
            if location is None:
                details = (
                    f"No design or user location for {instance.familyName} {instance.styleName}"
                )
                yield self._make_result(
                    code=INSTANCE_LOCATION_MISSING,
                    description="instance location missing",
                    location=f"instance {i}",
                    details=details,
                    is_structural=False,
                    raw_data={
                        "instance": i,
                        "instanceIndex": i,
                        "path": getattr(instance, "path", None),
                    },
                )
            else:
                # Check location values against axis ranges
                for axis_name, axis_value in location.items():
                    # Handle tuple values (anisotropic)
                    if isinstance(axis_value, tuple):
                        values_to_check = list(axis_value)
                    else:
                        values_to_check = [axis_value]

                    for val in values_to_check:
                        if axis_name in axis_values:
                            mn, df, mx = axis_values[axis_name]
                            if not (mn <= val <= mx):
                                # 3,3 and 3,5: Out of bounds / requires extrapolation
                                details = f"{instance.familyName}-{instance.styleName} {axis_name}: {val} is outside of extremes"
                                yield self._make_result(
                                    code=INSTANCE_OUT_OF_BOUNDS,
                                    description="instance location has out of bounds value",
                                    location=f"{instance.familyName} {instance.styleName}",
                                    details=details,
                                    is_structural=False,
                                    raw_data={
                                        "min": mn,
                                        "max": mx,
                                        "value": val,
                                        "axisName": axis_name,
                                    },
                                )
                                yield self._make_result(
                                    code=INSTANCE_REQUIRES_EXTRAPOLATION,
                                    description="instance location requires extrapolation",
                                    location=f"{instance.familyName} {instance.styleName}",
                                    details=details,
                                    is_structural=False,
                                    raw_data={
                                        "min": mn,
                                        "max": mx,
                                        "value": val,
                                        "axisName": axis_name,
                                    },
                                )
                        else:
                            # 3,2: Undefined axis
                            yield self._make_result(
                                code=INSTANCE_UNDEFINED_AXIS,
                                description="instance location has value for undefined axis",
                                location=f"instance {i}",
                                is_structural=False,
                                raw_data={"axisName": axis_name},
                            )

                # Track for duplicate detection
                key = tuple(sorted(location.items()))
                if key not in all_locations:
                    all_locations[key] = []
                all_locations[key].append((i, instance))

                if instance.familyName or instance.styleName:
                    name_key = (instance.familyName, instance.styleName)
                    all_names.setdefault(name_key, []).append((key, instance))

            # 3,6: Missing family name
            if not instance.familyName:
                details = f"instance at {_pretty_location(location)}"
                yield self._make_result(
                    code=INSTANCE_MISSING_FAMILY_NAME,
                    description="missing family name",
                    location=f"instance {i}",
                    details=details,
                    is_structural=False,
                    raw_data={"instance": i, "instanceIndex": i, "instanceName": instance.name},
                )

            # 3,7: Missing style name
            if not instance.styleName:
                details = f"instance at {_pretty_location(location)}"
                yield self._make_result(
                    code=INSTANCE_MISSING_STYLE_NAME,
                    description="missing style name",
                    location=f"instance {i}",
                    details=details,
                    is_structural=False,
                    raw_data={"instance": i, "instanceIndex": i, "instanceName": instance.name},
                )

            # 3,8: Missing output path (filename)
            if not instance.filename:
                details = f"no location for {instance.familyName} {instance.styleName}"
                yield self._make_result(
                    code=INSTANCE_MISSING_FILENAME,
                    description="missing output path",
                    location=f"{instance.familyName} {instance.styleName}",
                    details=details,
                    is_structural=False,
                    raw_data={"instance": i, "instanceIndex": i, "instanceName": instance.name},
                )

        # 3,4: Multiple instances on location (ONE problem per location, not per instance)
        for key, items in all_locations.items():
            if len(items) > 1:
                first_instance = items[0][1]
                loc = first_instance.location or dict(key)
                details = f"multiple instances at {_pretty_location(loc)}"
                yield self._make_result(
                    code=INSTANCE_MULTIPLE_ON_LOCATION,
                    description="multiple instances on location",
                    location=f"[{_pretty_location(loc)}]",
                    details=details,
                    is_structural=False,
                    raw_data={
                        "location": dict(key),
                        "instances": [_instance_name(inst) for _, inst in items],
                    },
                )

        # 3,13: one name, several locations -- a style menu cannot tell them apart
        for (family, style), items in all_names.items():
            locations = {key for key, _ in items}
            if len(locations) > 1:
                name = _instance_name(items[0][1])
                yield self._make_result(
                    code=INSTANCE_NAME_REUSED,
                    description=f"{len(locations)} instances named {name} at different locations",
                    location=name,
                    details="; ".join(_pretty_location(dict(key)) for key in sorted(locations)),
                    is_structural=False,
                    severity=SEVERITY_DESIGN,
                    raw_data={"familyName": family, "styleName": style},
                )

    def _unknown_label_result(self, i, instance, label_names) -> CheckResult | None:
        """3,12: a location label that does not exist.

        Reading the file accepts it; resolving the location raises, and with
        it the split into discrete slices and varLib's own loading.
        """
        label = getattr(instance, "locationLabel", None)
        if not label or label in label_names:
            return None
        return self._make_result(
            code=INSTANCE_UNKNOWN_LOCATION_LABEL,
            description=f"instance refers to an unknown location label: {label}",
            location=_instance_name(instance),
            details=(
                "fontTools cannot resolve this instance's location, so splitting the "
                "designspace and building it both fail on it. Define the label under "
                "<labels>, or give the instance a location."
            ),
            is_structural=False,
            severity=SEVERITY_STRUCTURAL,
            raw_data={
                "instance": i,
                "instanceIndex": i,
                "instanceName": instance.name,
                "locationLabel": label,
            },
        )

    def check_document(self, doc) -> Iterator[CheckResult]:
        """The instance checks that need the whole document, before it is split.

        Splitting drops an instance off its discrete axis' values, and fails
        outright on an unknown location label, so neither can be seen per slice.
        """
        label_names = {label.name for label in getattr(doc, "locationLabels", None) or []}
        for i, instance in enumerate(doc.instances):
            result = self._unknown_label_result(i, instance, label_names)
            if result is not None:
                yield result
        yield from self._check_stray_dimensions(doc)
        yield from self._check_discrete_values(doc)

    def _check_stray_dimensions(self, doc) -> Iterator[CheckResult]:
        """3,2 from the file: fontTools drops these dimensions while reading it."""
        for stray in undeclared_axis_dimensions(self.path or getattr(doc, "path", None)):
            if stray.kind == "source":
                continue
            where = stray.owner if stray.kind == "instance" else f"label {stray.owner}"
            yield self._make_result(
                code=INSTANCE_UNDEFINED_AXIS,
                description="instance location has value for undefined axis",
                location=where,
                details=(
                    f"{stray.axis} is not an axis of this designspace. fontTools ignores the "
                    f"dimension when it reads the file, so the {stray.kind} sits at that "
                    f"axis' default instead."
                ),
                is_structural=False,
                raw_data={"axisName": stray.axis, "kind": stray.kind},
            )

    def _check_discrete_values(self, doc) -> Iterator[CheckResult]:
        """3.11: instances off their discrete axis' values."""
        for instance, axis, value in discrete_value_problems(doc, doc.instances):
            values = ", ".join(_num(v) for v in axis.values)
            yield self._make_result(
                code=INSTANCE_OFF_DISCRETE_VALUES,
                description=(
                    f"instance at {axis.name}={_num(value)}, which is not one of the axis' "
                    f"values ({values})"
                ),
                location=_instance_name(instance),
                details=(
                    "The designspace is split along its discrete axes by their declared "
                    "values, so this instance belongs to no slice and is never generated."
                ),
                is_structural=False,
                severity=SEVERITY_DESIGN,
                raw_data={"axisName": axis.name, "value": value},
            )
