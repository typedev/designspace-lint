# Copyright 2026 Alexander Lubovenko
# Licensed under the Apache License, Version 2.0

"""
Every code the checks can report, with what a consumer needs to present it.

A host application groups, filters and labels findings. Before this catalogue
it had to copy the code lists by hand, and every new check showed up as an
unknown code until someone edited the copy. Now it can read them from here:

    from designspace_lint.codes import CODES
    info = CODES[(problem.category, problem.code)]
    info.title, info.group, info.default_severity, info.locators

`CODES` is part of the public contract, like the numbers themselves: a
`(category, code)` pair is never renumbered or reused, and a group slug is
never renamed without a release of deprecation. A test checks that every code
a checker can emit is listed here, that the listed severities are the ones
emitted, and that the `locators` keys are present in `raw_data` every time.

`locators` are the `raw_data` keys guaranteed for that code, for finding the
thing a finding is about without parsing its `location` string. The vocabulary
is fixed: `instanceName` (the instance's `name`), `instanceIndex` (its position
in the document), `sourceName`, `layerName`, `axisName`, `ruleName`,
`glyphName`, `mappingIndex`. A code with no locators promises none yet; they
are added as checks are revisited, never removed.
"""

from __future__ import annotations

from dataclasses import dataclass

from .model import SEVERITY_DESIGN, SEVERITY_INFO, SEVERITY_STRUCTURAL

ERR, WARN, INFO = SEVERITY_STRUCTURAL, SEVERITY_DESIGN, SEVERITY_INFO


@dataclass(frozen=True)
class CodeInfo:
    """What one `(category, code)` means."""

    category: int
    code: int
    #: The constant's name in its checker module, e.g. "GLYPH_AXIS_SPAN_GAP".
    const_name: str
    #: A short title for a list or a filter, e.g. "Glyph does not reach an axis end".
    title: str
    #: A stable slug grouping related codes, e.g. "avar2".
    group: str
    #: The group's display title.
    group_title: str
    #: The severity the code is reported at; see `severities` for the exceptions.
    default_severity: int
    #: The engine phase that reports it.
    phase: str
    #: Every severity the code can be reported at, `default_severity` first.
    severities: tuple[int, ...] = ()
    #: Reported only by `lint(..., interpolatable=True)`.
    interpolatable_only: bool = False
    #: `raw_data` keys guaranteed on every finding with this code.
    locators: tuple[str, ...] = ()
    #: Declared but no longer reported; the number stays taken.
    retired: bool = False


GROUPS = {
    "run": "File and run",
    "axes": "Axes",
    "variable-fonts": "Variable fonts",
    "avar2": "avar2 mappings",
    "sources": "Sources",
    "instances": "Instances",
    "compatibility": "Glyph compatibility",
    "coverage": "Glyph coverage",
    "interpolation": "Point correspondence",
    "kerning": "Kerning",
    "fontinfo": "Font info",
    "rules": "Rules",
    "features": "Features",
    "glyph-order": "Glyph order",
    "labels": "Labels and names",
}

_PHASE = {
    0: "file",
    1: "geometry",
    2: "sources",
    3: "instances",
    4: "glyphs",
    5: "kerning",
    6: "fontinfo",
    7: "rules",
    8: "features",
    9: "glyphorder",
    10: "labels",
}

# (category, code, const_name, title, group, severity or (severities...), locators, flags)
_TABLE = [
    # --- 0 File and run ---
    (0, 0, "FILE_CANNOT_READ", "Designspace cannot be read", "run", ERR, ()),
    (0, 1, "PHASE_FAILED", "A check stopped early", "run", ERR, ()),
    # --- 1 Axes ---
    (1, 0, "NO_AXES", "No axes", "axes", ERR, ()),
    (1, 1, "AXIS_MIN_EQUALS_MAX", "Axis minimum equals maximum", "axes", ERR, ("axisName",)),
    (
        1,
        2,
        "AXIS_DEFAULT_OUT_OF_RANGE",
        "Axis default outside its range",
        "axes",
        ERR,
        ("axisName",),
    ),
    (1, 3, "AXIS_MAP_ONE_PAIR", "Axis map with a single pair", "axes", ERR, ("axisName",)),
    (
        1,
        4,
        "AXIS_MAP_INPUT_OUT_OF_RANGE",
        "Axis map input outside the axis",
        "axes",
        ERR,
        ("axisName",),
    ),
    (
        1,
        5,
        "AXIS_MAP_OUTPUT_OUT_OF_RANGE",
        "Axis map output outside its range",
        "axes",
        ERR,
        (),
        "retired",
    ),
    (1, 6, "AXIS_MAP_MIN_NOT_AT_MIN", "Axis map misses the minimum", "axes", ERR, ("axisName",)),
    (1, 7, "AXIS_MAP_MAX_NOT_AT_MAX", "Axis map misses the maximum", "axes", ERR, ("axisName",)),
    (
        1,
        8,
        "AXIS_MAP_INPUT_NOT_INCREASING",
        "Axis map inputs not increasing",
        "axes",
        ERR,
        ("axisName",),
    ),
    (
        1,
        9,
        "AXIS_MAP_OUTPUT_NOT_INCREASING",
        "Axis map outputs not increasing",
        "axes",
        ERR,
        ("axisName",),
    ),
    (
        1,
        10,
        "AXIS_NO_MAP_MIN_MISMATCH",
        "Unmapped axis minimum mismatch",
        "axes",
        INFO,
        (),
        "retired",
    ),
    (
        1,
        11,
        "AXIS_NO_MAP_MAX_MISMATCH",
        "Unmapped axis maximum mismatch",
        "axes",
        INFO,
        (),
        "retired",
    ),
    (
        1,
        12,
        "AXIS_NO_MAP_DEFAULT_MISMATCH",
        "Unmapped axis default mismatch",
        "axes",
        INFO,
        (),
        "retired",
    ),
    (1, 13, "DUPLICATE_AXIS_NAME", "Duplicate axis name", "axes", ERR, ("axisName",)),
    (1, 14, "DUPLICATE_AXIS_TAG", "Duplicate axis tag", "axes", ERR, ("axisName",)),
    (1, 15, "AXIS_MAP_NO_DEFAULT", "Axis map misses the default", "axes", ERR, ("axisName",)),
    (
        1,
        16,
        "DISCRETE_DEFAULT_NOT_IN_VALUES",
        "Discrete default not among its values",
        "axes",
        ERR,
        ("axisName",),
    ),
    (1, 17, "NO_CONTINUOUS_AXIS", "No continuous axis", "axes", INFO, ()),
    (
        1,
        18,
        "AVAR2_MAPPING_FROM_DEFAULT",
        "avar2 mapping from the default is dropped",
        "avar2",
        ERR,
        ("mappingIndex",),
    ),
    (
        1,
        19,
        "VF_UNKNOWN_AXIS",
        "Variable font subsets an unknown axis",
        "variable-fonts",
        ERR,
        ("axisName",),
    ),
    (
        1,
        20,
        "VF_RANGE_ON_DISCRETE_AXIS",
        "Variable font range over a discrete axis",
        "variable-fonts",
        ERR,
        ("axisName",),
    ),
    (
        1,
        21,
        "VF_SUBSET_SELECTS_NOTHING",
        "Variable font subset selects nothing",
        "variable-fonts",
        ERR,
        ("axisName",),
    ),
    (
        1,
        22,
        "VF_ZERO_DEFAULT_IGNORED",
        "Variable font default of 0 ignored",
        "variable-fonts",
        ERR,
        ("axisName",),
    ),
    (
        1,
        23,
        "AVAR2_DUPLICATE_INPUT",
        "avar2 mappings with one input",
        "avar2",
        ERR,
        ("mappingIndex",),
    ),
    (
        1,
        24,
        "AVAR2_UNKNOWN_AXIS",
        "avar2 mapping names an unknown axis",
        "avar2",
        ERR,
        ("mappingIndex", "axisName"),
    ),
    (
        1,
        25,
        "AVAR2_VALUE_CLAMPED",
        "avar2 value past the axis end",
        "avar2",
        WARN,
        ("mappingIndex",),
    ),
    (
        1,
        26,
        "AVAR2_PAST_THE_MASTERS",
        "avar2 output past the outermost master",
        "avar2",
        WARN,
        ("mappingIndex",),
    ),
    (1, 27, "AVAR2_CHAINED", "avar2 mappings chained", "avar2", WARN, ("mappingIndex", "axisName")),
    (
        1,
        28,
        "AVAR2_UNDRIVEN_HIDDEN_AXIS",
        "Hidden axis no mapping moves",
        "avar2",
        INFO,
        ("axisName",),
    ),
    (
        1,
        29,
        "AVAR2_NOT_MONOTONIC",
        "avar2 runs a visible axis backwards",
        "avar2",
        WARN,
        ("axisName",),
    ),
    # --- 2 Sources ---
    (2, 0, "NO_SOURCES", "No sources", "sources", ERR, ()),
    (2, 1, "SOURCE_FILE_NOT_FOUND", "Source UFO not found", "sources", ERR, ("sourceName",)),
    (2, 2, "SOURCE_NOT_VALID_UFO", "Source is not a UFO", "sources", ERR, ("sourceName",)),
    (
        2,
        3,
        "SOURCE_LOCATION_MISSING_AXIS",
        "Source location on an undeclared axis",
        "sources",
        ERR,
        ("sourceName", "axisName"),
    ),
    (
        2,
        4,
        "SOURCE_LOCATION_OUT_OF_RANGE",
        "Source location outside the axis",
        "sources",
        ERR,
        ("axisName",),
    ),
    (2, 5, "NO_DEFAULT_SOURCE", "No default source", "sources", ERR, ()),
    (
        2,
        6,
        "DUPLICATE_SOURCE_LOCATION",
        "Two sources at one location",
        "sources",
        ERR,
        ("sourceName",),
    ),
    (2, 7, "SOURCE_LAYER_NOT_FOUND", "Source layer not found", "sources", ERR, ("layerName",)),
    (2, 8, "SOURCE_NO_FONT", "Source has no font", "sources", ERR, (), "retired"),
    (
        2,
        9,
        "DEFAULT_LOCATION_MISMATCH",
        "Default source location mismatch",
        "sources",
        ERR,
        (),
        "retired",
    ),
    (
        2,
        10,
        "SOURCE_OFF_DISCRETE_VALUES",
        "Source off a discrete axis' values",
        "sources",
        ERR,
        ("sourceName", "axisName"),
    ),
    # --- 3 Instances ---
    (
        3,
        1,
        "INSTANCE_LOCATION_MISSING",
        "Instance has no location",
        "instances",
        INFO,
        ("instanceIndex",),
    ),
    (
        3,
        2,
        "INSTANCE_UNDEFINED_AXIS",
        "Instance location on an undeclared axis",
        "instances",
        INFO,
        ("axisName",),
    ),
    (3, 3, "INSTANCE_OUT_OF_BOUNDS", "Instance outside the axes", "instances", INFO, ("axisName",)),
    (3, 4, "INSTANCE_MULTIPLE_ON_LOCATION", "Two instances at one location", "instances", INFO, ()),
    (
        3,
        5,
        "INSTANCE_REQUIRES_EXTRAPOLATION",
        "Instance needs extrapolation",
        "instances",
        INFO,
        ("axisName",),
    ),
    (
        3,
        6,
        "INSTANCE_MISSING_FAMILY_NAME",
        "Instance without a family name",
        "instances",
        INFO,
        ("instanceIndex",),
    ),
    (
        3,
        7,
        "INSTANCE_MISSING_STYLE_NAME",
        "Instance without a style name",
        "instances",
        INFO,
        ("instanceIndex",),
    ),
    (
        3,
        8,
        "INSTANCE_MISSING_FILENAME",
        "Instance without a file name",
        "instances",
        INFO,
        ("instanceIndex",),
    ),
    (3, 10, "INSTANCE_NONE_DEFINED", "No instances", "instances", INFO, ()),
    (
        3,
        11,
        "INSTANCE_OFF_DISCRETE_VALUES",
        "Instance off a discrete axis' values",
        "instances",
        WARN,
        ("axisName",),
    ),
    (
        3,
        12,
        "INSTANCE_UNKNOWN_LOCATION_LABEL",
        "Instance names an unknown location label",
        "instances",
        ERR,
        ("instanceIndex", "instanceName"),
    ),
    (3, 13, "INSTANCE_NAME_REUSED", "One instance name at two locations", "instances", WARN, ()),
    # --- 4 Glyphs ---
    (
        4,
        0,
        "DIFFERENT_CONTOUR_COUNT",
        "Different contour counts",
        "compatibility",
        WARN,
        ("glyphName",),
    ),
    (4, 1, "DIFFERENT_COMPONENTS", "Different components", "compatibility", WARN, ("glyphName",)),
    (4, 2, "DIFFERENT_ANCHORS", "Different anchors", "compatibility", WARN, ("glyphName",)),
    (
        4,
        3,
        "DIFFERENT_ON_CURVES",
        "Different on-curve points",
        "compatibility",
        WARN,
        ("glyphName",),
    ),
    (
        4,
        4,
        "DIFFERENT_OFF_CURVES",
        "Different off-curve points",
        "compatibility",
        WARN,
        ("glyphName",),
    ),
    (4, 5, "WRONG_CURVE_TYPE", "Different curve types", "compatibility", WARN, ("glyphName",)),
    (
        4,
        7,
        "DEFAULT_GLYPH_EMPTY",
        "Glyph missing from the default",
        "coverage",
        ERR,
        ("glyphName",),
    ),
    (
        4,
        8,
        "WRONG_CONTOUR_DIRECTION",
        "Different contour directions",
        "compatibility",
        WARN,
        ("glyphName",),
    ),
    (4, 9, "INCOMPATIBLE_GLYPH", "Incompatible structures", "compatibility", WARN, ("glyphName",)),
    (4, 10, "DIFFERENT_UNICODES", "Different unicodes", "compatibility", WARN, ("glyphName",)),
    (
        4,
        11,
        "GLYPH_AXIS_SPAN_GAP",
        "Glyph does not reach an axis end",
        "coverage",
        ERR,
        ("glyphName", "axisName"),
    ),
    (4, 12, "GLYPH_EMPTY_IN_SOURCE", "Glyph empty in a master", "coverage", WARN, ("glyphName",)),
    (4, 13, "GLYPH_STATIC", "Glyph drawn only in the default", "coverage", WARN, ("glyphName",)),
    (
        4,
        14,
        "CONTOUR_ORDER",
        "Contours in a different order",
        "interpolation",
        WARN,
        ("glyphName",),
        "interpolatable",
    ),
    (
        4,
        15,
        "WRONG_START_POINT",
        "Start point or direction differs",
        "interpolation",
        WARN,
        ("glyphName",),
        "interpolatable",
    ),
    (
        4,
        16,
        "UNDERWEIGHT",
        "Contour thins out halfway",
        "interpolation",
        WARN,
        ("glyphName",),
        "interpolatable",
    ),
    (
        4,
        17,
        "KINK",
        "Contour kinks halfway",
        "interpolation",
        INFO,
        ("glyphName",),
        "interpolatable",
    ),
    (
        4,
        18,
        "UNCHECKED_NO_SOLVER",
        "Glyphs not compared point by point",
        "interpolation",
        INFO,
        (),
        "interpolatable",
    ),
    # --- 5 Kerning ---
    (5, 0, "NO_KERNING_IN_SOURCE", "Master without kerning", "kerning", WARN, ()),
    (5, 1, "NO_KERNING_IN_DEFAULT", "Default without kerning", "kerning", WARN, ()),
    (5, 2, "KERNING_GROUP_DIFFERS", "Kerning group members differ", "kerning", WARN, ()),
    (5, 3, "KERNING_GROUP_MISSING", "Kerning group missing", "kerning", WARN, ()),
    (5, 5, "NO_KERNING_GROUPS_DEFAULT", "Default without kerning groups", "kerning", WARN, ()),
    (5, 6, "NO_KERNING_GROUPS_SOURCE", "Master without kerning groups", "kerning", ERR, ()),
    (
        5,
        7,
        "KERNING_GROUP_SORTED_DIFF",
        "Kerning group members in another order",
        "kerning",
        INFO,
        (),
    ),
    (
        5,
        8,
        "GLYPH_IN_TWO_KERN_GROUPS",
        "Glyph in two kerning groups of one side",
        "kerning",
        ERR,
        ("glyphName",),
    ),
    (5, 9, "KERNING_KEY_MALFORMED", "Unreadable kerning key", "kerning", ERR, ()),
    # --- 6 Font info ---
    (6, 0, "UNITS_PER_EM_DIFFERS", "unitsPerEm differs", "fontinfo", ERR, ()),
    (6, 1, "REQUIRED_FIELD_MISSING", "Required font info missing", "fontinfo", ERR, ()),
    (6, 2, "FIELD_DIFFERS", "Font info differs from the default", "fontinfo", WARN, ()),
    # --- 7 Rules ---
    (7, 0, "RULE_NO_CONDITIONS", "Rule that never applies", "rules", INFO, ("ruleName",)),
    (
        7,
        1,
        "RULE_UNDEFINED_AXIS",
        "Rule condition on an unknown axis",
        "rules",
        INFO,
        ("ruleName", "axisName"),
    ),
    (
        7,
        2,
        "RULE_INVALID_RANGE",
        "Rule condition range inverted",
        "rules",
        INFO,
        ("ruleName", "axisName"),
    ),
    (
        7,
        3,
        "RULE_RANGE_OUT_OF_BOUNDS",
        "Rule condition outside the axis",
        "rules",
        INFO,
        ("ruleName", "axisName"),
    ),
    (7, 4, "RULE_NO_SUBSTITUTIONS", "Rule without substitutions", "rules", INFO, ("ruleName",)),
    (
        7,
        5,
        "RULE_UNDEFINED_GLYPH",
        "Rule glyph missing from the default",
        "rules",
        ERR,
        ("ruleName", "glyphName"),
    ),
    (7, 6, "RULE_DUPLICATE_NAME", "Duplicate rule name", "rules", INFO, ("ruleName",)),
    (7, 7, "RULE_OVERLAP", "Overlapping rules on one glyph", "rules", WARN, ()),
    # --- 8 Features ---
    (8, 0, "FEATURE_FILE_CORRUPT", "features.fea cannot be read", "features", INFO, ()),
    (8, 1, "FEATURE_MISSING", "Feature missing in some masters", "features", INFO, ()),
    (
        8,
        3,
        "FEATURES_DIFFER_FROM_DEFAULT",
        "features.fea off the variable path",
        "features",
        ERR,
        (),
    ),
    # --- 9 Glyph order ---
    (
        9,
        0,
        "GLYPHORDER_EXTRA_GLYPH",
        "Glyph not in the default",
        "glyph-order",
        WARN,
        ("glyphName",),
    ),
    (
        9,
        1,
        "GLYPHORDER_MISSING_GLYPH",
        "Glyph missing from a master",
        "glyph-order",
        WARN,
        (),
        "retired",
    ),
    (
        9,
        2,
        "GLYPHORDER_NAMING_MISMATCH",
        "Glyph order naming mismatch",
        "glyph-order",
        WARN,
        (),
        "retired",
    ),
    (
        9,
        3,
        "GLYPHORDER_POSITION_MISMATCH",
        "Glyph order breaks the merge",
        "glyph-order",
        WARN,
        ("glyphName", "sourceName"),
    ),
    # --- 10 Labels ---
    (
        10,
        0,
        "INSTANCE_NAME_REPLACED",
        "Instance renamed in the variable font",
        "labels",
        (WARN, ERR),
        ("instanceName", "instanceIndex"),
    ),
    (10, 1, "VALUE_WITHOUT_LABEL", "Value no label covers", "labels", WARN, ("axisName",)),
    (10, 2, "ALL_ELIDED_NO_FALLBACK", "No elidedfallbackname", "labels", WARN, ()),
    (10, 3, "LABEL_OUTSIDE", "Label left out of STAT", "labels", (WARN, INFO), ()),
    (10, 4, "PARTIAL_LOCATION_LABEL", "Location label missing an axis", "labels", WARN, ()),
    (
        10,
        5,
        "RANGE_LABEL_MALFORMED",
        "Range label that does not hold",
        "labels",
        WARN,
        ("axisName",),
    ),
    (10, 6, "STYLE_LINK", "Style link missing or broken", "labels", (WARN, INFO), ("axisName",)),
    (10, 7, "LABEL_REDUNDANT", "Duplicate or missing label", "labels", INFO, ("axisName",)),
]


def _build() -> dict[tuple[int, int], CodeInfo]:
    codes = {}
    for row in _TABLE:
        category, code, const, title, group, severity, locators, *flags = row
        severities = severity if isinstance(severity, tuple) else (severity,)
        key = (category, code)
        assert key not in codes, key
        codes[key] = CodeInfo(
            category=category,
            code=code,
            const_name=const,
            title=title,
            group=group,
            group_title=GROUPS[group],
            default_severity=severities[0],
            phase="interpolation" if "interpolatable" in flags else _PHASE[category],
            severities=severities,
            interpolatable_only="interpolatable" in flags,
            locators=tuple(locators),
            retired="retired" in flags,
        )
    return codes


#: Every code, keyed by `(category, code)`.
CODES: dict[tuple[int, int], CodeInfo] = _build()


def code_info(problem) -> CodeInfo | None:
    """The catalogue entry for a finding, or None for a code this version does not know."""
    return CODES.get((problem.category, problem.code))


__all__ = ["CODES", "GROUPS", "CodeInfo", "code_info"]
