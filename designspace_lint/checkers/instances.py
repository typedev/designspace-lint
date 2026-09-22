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

Copyright 2024-2026 TypeDev
Licensed under the Apache License, Version 2.0
"""

from __future__ import annotations

import logging
from typing import Iterator

from ..model import CATEGORY_INSTANCES, CheckResult
from .base import BaseChecker

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

        for i, instance in enumerate(doc.instances):
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
                    raw_data={"instance": i, "path": getattr(instance, "path", None)},
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

            # 3,6: Missing family name
            if not instance.familyName:
                details = f"instance at {_pretty_location(location)}"
                yield self._make_result(
                    code=INSTANCE_MISSING_FAMILY_NAME,
                    description="missing family name",
                    location=f"instance {i}",
                    details=details,
                    is_structural=False,
                    raw_data={"instance": i},
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
                    raw_data={"instance": i},
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
                    raw_data={"instance": i},
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
                        "instances": [inst.familyName + " " + inst.styleName for _, inst in items],
                    },
                )
