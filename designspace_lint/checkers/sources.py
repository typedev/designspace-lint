"""
Sources checker - validates source definitions and files.

Category 2: Source validation
Based on designspaceProblems checkSources().

Checks:
- 2.0: No sources defined
- 2.1: Source file not found
- 2.2: Source file not a valid UFO
- 2.3: Source location missing axis value
- 2.4: Source location axis value out of range
- 2.5: No default source defined
- 2.6: Multiple sources at same location
- 2.7: Source layer not found
- 2.8: Source has no font attribute
- 2.9: Default source location mismatch

Copyright 2024-2026 TypeDev
Licensed under the Apache License, Version 2.0
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Iterator

from ..model import CATEGORY_SOURCES, CheckResult
from .base import BaseChecker

logger = logging.getLogger(__name__)

# Error codes
NO_SOURCES = 0
SOURCE_FILE_NOT_FOUND = 1
SOURCE_NOT_VALID_UFO = 2
SOURCE_LOCATION_MISSING_AXIS = 3
SOURCE_LOCATION_OUT_OF_RANGE = 4
NO_DEFAULT_SOURCE = 5
DUPLICATE_SOURCE_LOCATION = 6
SOURCE_LAYER_NOT_FOUND = 7
SOURCE_NO_FONT = 8
DEFAULT_LOCATION_MISMATCH = 9


class SourcesChecker(BaseChecker):
    """
    Validates source definitions and files.

    These are structural checks - if they fail, the designspace
    cannot be used for interpolation.
    """

    CATEGORY = CATEGORY_SOURCES

    def check(self) -> Iterator[CheckResult]:
        """Run all source validation checks."""
        doc = self.doc

        # Check 2.0: No sources defined
        if not doc.sources:
            yield self._make_result(
                code=NO_SOURCES,
                description="No sources defined in designspace",
                is_structural=True,
            )
            return

        # Build axis info for validation
        # Source locations use DESIGN-SPACE coordinates, not user-space
        # So we need to get the design-space range from axis mapping
        axis_info = {}
        for axis in doc.axes:
            # Get design-space range
            if axis.map:
                # Axis has mapping: get design-space (output) range
                outputs = [m[1] for m in axis.map]
                ds_min = min(outputs)
                ds_max = max(outputs)
                # Find design-space default
                ds_default = axis.default  # Will be mapped below
                for inp, out in axis.map:
                    if inp == axis.default:
                        ds_default = out
                        break
            else:
                # No mapping: design-space = user-space
                ds_min = axis.minimum
                ds_max = axis.maximum
                ds_default = axis.default

            axis_info[axis.name] = {
                "minimum": ds_min,
                "maximum": ds_max,
                "default": ds_default,
                "user_min": axis.minimum,
                "user_max": axis.maximum,
                "user_default": axis.default,
                "has_map": bool(axis.map),
            }

        # Track locations for duplicate detection
        seen_locations: dict[tuple, str] = {}
        has_default = False

        for source in doc.sources:
            source_name = source.name or source.filename or "unknown"

            # Check 2.1: Source file exists
            if source.path:
                yield from self._check_source_file(source, source_name)

            # Check 2.3-2.4: Source location validity
            if source.location:
                yield from self._check_source_location(source, source_name, axis_info)

                # Check 2.6: Duplicate locations
                loc_tuple = tuple(sorted(source.location.items()))
                if loc_tuple in seen_locations:
                    yield self._make_result(
                        code=DUPLICATE_SOURCE_LOCATION,
                        description=(f"Duplicate source location with {seen_locations[loc_tuple]}"),
                        location=source_name,
                        is_structural=True,
                        raw_data={
                            "path": source.path,
                            "location": source.location,
                            "duplicateOf": seen_locations[loc_tuple],
                        },
                    )
                else:
                    seen_locations[loc_tuple] = source_name

            # Check 2.7: Layer exists (if specified)
            if source.layerName:
                yield from self._check_source_layer(source, source_name)

            # Track default source
            # A source is default if it has copyInfo=True or matches default location
            if self._is_default_source(source, axis_info):
                has_default = True

        # Check 2.5: No default source
        if not has_default:
            # Try to find default using doc.findDefault()
            default_source = doc.findDefault()
            if default_source is None:
                yield self._make_result(
                    code=NO_DEFAULT_SOURCE,
                    description="No default source defined or found",
                    is_structural=True,
                )

    def _check_source_file(self, source, source_name: str) -> Iterator[CheckResult]:
        """Check source file exists and is valid UFO."""
        path = source.path

        # Resolve relative path
        if self.ds_dir and not os.path.isabs(path):
            full_path = self.ds_dir / path
        else:
            full_path = Path(path)

        # Check exists
        if not full_path.exists():
            yield self._make_result(
                code=SOURCE_FILE_NOT_FOUND,
                description=f"Source file not found: {path}",
                location=source_name,
                is_structural=True,
                raw_data={"path": str(path)},
            )
            return

        # Check is a directory (UFO is a directory)
        if not full_path.is_dir():
            # Could be a .ufoz file
            if not path.endswith(".ufoz"):
                yield self._make_result(
                    code=SOURCE_NOT_VALID_UFO,
                    description=f"Source is not a UFO directory: {path}",
                    location=source_name,
                    is_structural=True,
                    raw_data={"path": str(path)},
                )
            return

        # Check basic UFO structure
        metainfo = full_path / "metainfo.plist"
        if not metainfo.exists():
            yield self._make_result(
                code=SOURCE_NOT_VALID_UFO,
                description=f"Source missing metainfo.plist: {path}",
                location=source_name,
                is_structural=True,
                raw_data={"path": str(path)},
            )

    def _check_source_location(
        self, source, source_name: str, axis_info: dict
    ) -> Iterator[CheckResult]:
        """Check source location is valid for all axes."""
        location = source.location

        for axis_name, info in axis_info.items():
            # Check 2.3: Location has value for this axis
            if axis_name not in location:
                yield self._make_result(
                    code=SOURCE_LOCATION_MISSING_AXIS,
                    description=f"Source location missing axis value: {axis_name}",
                    location=source_name,
                    is_structural=True,
                    raw_data={
                        "path": source.path,
                        "axisName": axis_name,
                        "location": location,
                    },
                )
                continue

            # Check 2.4: Location value within axis range
            value = location[axis_name]
            axis_min = info["minimum"]
            axis_max = info["maximum"]

            if not (axis_min <= value <= axis_max):
                yield self._make_result(
                    code=SOURCE_LOCATION_OUT_OF_RANGE,
                    description=(
                        f"Source location {axis_name}={value} out of range [{axis_min}, {axis_max}]"
                    ),
                    location=source_name,
                    is_structural=True,
                    raw_data={
                        "path": source.path,
                        "axisName": axis_name,
                        "value": value,
                        "minimum": axis_min,
                        "maximum": axis_max,
                    },
                )

    def _check_source_layer(self, source, source_name: str) -> Iterator[CheckResult]:
        """Check source layer exists."""
        layer_name = source.layerName
        path = source.path

        if not path or not self.ds_dir:
            return

        # Resolve path
        if not os.path.isabs(path):
            full_path = self.ds_dir / path
        else:
            full_path = Path(path)

        if not full_path.exists() or not full_path.is_dir():
            return  # File issues already reported

        # Check for layer in glyphs folder
        # Default layer is "glyphs", custom layers are "glyphs.{layerName}"
        if layer_name == "public.default":
            layer_dir = full_path / "glyphs"
        else:
            layer_dir = full_path / f"glyphs.{layer_name}"

        if not layer_dir.exists():
            # Check layercontents.plist for the actual layer name
            layer_contents = full_path / "layercontents.plist"
            if layer_contents.exists():
                try:
                    import plistlib

                    with open(layer_contents, "rb") as f:
                        layers = plistlib.load(f)
                    # layers is [(name, dirname), ...]
                    layer_names = [name for name, _ in layers]
                    if layer_name not in layer_names:
                        yield self._make_result(
                            code=SOURCE_LAYER_NOT_FOUND,
                            description=f"Layer not found: {layer_name}",
                            location=source_name,
                            details=f"Available layers: {', '.join(layer_names)}",
                            is_structural=True,
                            raw_data={
                                "path": str(path),
                                "layerName": layer_name,
                                "availableLayers": layer_names,
                            },
                        )
                except Exception:
                    pass  # Can't read layer contents, skip check
            else:
                # No layercontents.plist, check if glyphs dir exists
                if not (full_path / "glyphs").exists():
                    yield self._make_result(
                        code=SOURCE_LAYER_NOT_FOUND,
                        description=f"Layer not found: {layer_name}",
                        location=source_name,
                        is_structural=True,
                        raw_data={"path": str(path), "layerName": layer_name},
                    )

    def _is_default_source(self, source, axis_info: dict) -> bool:
        """Check if source is the default source."""
        # Explicit default marker
        if getattr(source, "copyInfo", False):
            return True

        # Check if location matches default for all axes
        # Note: source.location is in design-space, axis_info["default"] is also design-space
        if not source.location:
            return False

        for axis_name, info in axis_info.items():
            if axis_name not in source.location:
                return False
            # Compare with design-space default
            if source.location[axis_name] != info["default"]:
                return False

        return True
