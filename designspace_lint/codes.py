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
in the document), `instanceIndices` (several of them, for a finding about a
group), `sourceName`, `layerName`, `axisName`, `ruleName`, `glyphName`,
`mappingIndex`, and for the unicode checks `glyphNames`, `codepoint`,
`codepoints`. A code with no locators promises none yet; they
are added as checks are revisited, never removed.

`raw_keys` lists every key a code's findings *may* carry, and `RAW_KEYS` says
what each key means, so a fixer -- a person's script or an AI assistant --
can act on documented data instead of the wording. A test fails any finding
that carries a key its code does not list.
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
    #: Reported only by `lint(..., construction=True)`.
    construction_only: bool = False
    #: Reported only by `lint(..., topology=True)`.
    topology_only: bool = False
    #: `raw_data` keys guaranteed on every finding with this code.
    locators: tuple[str, ...] = ()
    #: Every `raw_data` key a finding with this code may carry, the locators
    #: first; `RAW_KEYS[key]` says what each means.
    raw_keys: tuple[str, ...] = ()
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
    "topology": "Outlines between masters",
    "construction": "Composite construction",
    "unicodes": "Unicodes",
    "components": "Components and contours",
    "direction": "Contour direction",
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
# fmt: off
_TABLE = [
    # --- 0 File and run ---
    (0, 0, "FILE_CANNOT_READ", "Designspace cannot be read", "run", ERR, ()),
    (0, 1, "PHASE_FAILED", "A check stopped early", "run", ERR, ()),
    # --- 1 Axes ---
    (1, 0, "NO_AXES", "No axes", "axes", ERR, ()),
    (1, 1, "AXIS_MIN_EQUALS_MAX", "Axis minimum equals maximum", "axes", ERR, ("axisName",)),
    (1, 2, "AXIS_DEFAULT_OUT_OF_RANGE", "Axis default outside its range", "axes", ERR, ("axisName",)),
    (1, 3, "AXIS_MAP_ONE_PAIR", "Axis map with a single pair", "axes", ERR, ("axisName",)),
    (1, 4, "AXIS_MAP_INPUT_OUT_OF_RANGE", "Axis map input outside the axis", "axes", ERR, ("axisName",)),
    (1, 5, "AXIS_MAP_OUTPUT_OUT_OF_RANGE", "Axis map output outside its range", "axes", ERR, (), "retired"),
    (1, 6, "AXIS_MAP_MIN_NOT_AT_MIN", "Axis map misses the minimum", "axes", ERR, ("axisName",)),
    (1, 7, "AXIS_MAP_MAX_NOT_AT_MAX", "Axis map misses the maximum", "axes", ERR, ("axisName",)),
    (1, 8, "AXIS_MAP_INPUT_NOT_INCREASING", "Axis map inputs not increasing", "axes", ERR, ("axisName",)),
    (1, 9, "AXIS_MAP_OUTPUT_NOT_INCREASING", "Axis map outputs not increasing", "axes", ERR, ("axisName",)),
    (1, 10, "AXIS_NO_MAP_MIN_MISMATCH", "Unmapped axis minimum mismatch", "axes", INFO, (), "retired"),
    (1, 11, "AXIS_NO_MAP_MAX_MISMATCH", "Unmapped axis maximum mismatch", "axes", INFO, (), "retired"),
    (1, 12, "AXIS_NO_MAP_DEFAULT_MISMATCH", "Unmapped axis default mismatch", "axes", INFO, (), "retired"),
    (1, 13, "DUPLICATE_AXIS_NAME", "Duplicate axis name", "axes", ERR, ("axisName",)),
    (1, 14, "DUPLICATE_AXIS_TAG", "Duplicate axis tag", "axes", ERR, ("axisName",)),
    (1, 15, "AXIS_MAP_NO_DEFAULT", "Axis map misses the default", "axes", ERR, ("axisName",)),
    (1, 16, "DISCRETE_DEFAULT_NOT_IN_VALUES", "Discrete default not among its values", "axes", ERR, ("axisName",)),
    (1, 17, "NO_CONTINUOUS_AXIS", "No continuous axis", "axes", INFO, ()),
    (1, 18, "AVAR2_MAPPING_FROM_DEFAULT", "avar2 mapping from the default is dropped", "avar2", ERR, ("mappingIndex",)),
    (1, 19, "VF_UNKNOWN_AXIS", "Variable font subsets an unknown axis", "variable-fonts", ERR, ("axisName",)),
    (1, 20, "VF_RANGE_ON_DISCRETE_AXIS", "Variable font range over a discrete axis", "variable-fonts", ERR, ("axisName",)),
    (1, 21, "VF_SUBSET_SELECTS_NOTHING", "Variable font subset selects nothing", "variable-fonts", ERR, ("axisName",)),
    (1, 22, "VF_ZERO_DEFAULT_IGNORED", "Variable font default of 0 ignored", "variable-fonts", ERR, ("axisName",)),
    (1, 23, "AVAR2_DUPLICATE_INPUT", "avar2 mappings with one input", "avar2", ERR, ("mappingIndex",)),
    (1, 24, "AVAR2_UNKNOWN_AXIS", "avar2 mapping names an unknown axis", "avar2", ERR, ("mappingIndex", "axisName")),
    (1, 25, "AVAR2_VALUE_CLAMPED", "avar2 value past the axis end", "avar2", WARN, ("mappingIndex",)),
    (1, 26, "AVAR2_PAST_THE_MASTERS", "avar2 output past the outermost master", "avar2", WARN, ("mappingIndex",)),
    (1, 27, "AVAR2_CHAINED", "avar2 mappings chained", "avar2", WARN, ("mappingIndex", "axisName")),
    (1, 28, "AVAR2_UNDRIVEN_HIDDEN_AXIS", "Hidden axis no mapping moves", "avar2", INFO, ("axisName",)),
    (1, 29, "AVAR2_NOT_MONOTONIC", "avar2 runs a visible axis backwards", "avar2", WARN, ("axisName",)),
    # --- 2 Sources ---
    (2, 0, "NO_SOURCES", "No sources", "sources", ERR, ()),
    (2, 1, "SOURCE_FILE_NOT_FOUND", "Source UFO not found", "sources", ERR, ("sourceName",)),
    (2, 2, "SOURCE_NOT_VALID_UFO", "Source is not a UFO", "sources", ERR, ("sourceName",)),
    (2, 3, "SOURCE_LOCATION_MISSING_AXIS", "Source location on an undeclared axis", "sources", ERR, ("sourceName", "axisName")),
    (2, 4, "SOURCE_LOCATION_OUT_OF_RANGE", "Source location outside the axis", "sources", ERR, ("axisName",)),
    (2, 5, "NO_DEFAULT_SOURCE", "No default source", "sources", ERR, ()),
    (2, 6, "DUPLICATE_SOURCE_LOCATION", "Two sources at one location", "sources", ERR, ("sourceName",)),
    (2, 7, "SOURCE_LAYER_NOT_FOUND", "Source layer not found", "sources", ERR, ("layerName",)),
    (2, 8, "SOURCE_NO_FONT", "Source has no font", "sources", ERR, (), "retired"),
    (2, 9, "DEFAULT_LOCATION_MISMATCH", "Default source location mismatch", "sources", ERR, (), "retired"),
    (2, 10, "SOURCE_OFF_DISCRETE_VALUES", "Source off a discrete axis' values", "sources", ERR, ("sourceName", "axisName")),
    # --- 3 Instances ---
    (3, 1, "INSTANCE_LOCATION_MISSING", "Instance has no location", "instances", INFO, ("instanceIndex",)),
    (3, 2, "INSTANCE_UNDEFINED_AXIS", "Instance location on an undeclared axis", "instances", INFO, ("axisName",)),
    (3, 3, "INSTANCE_OUT_OF_BOUNDS", "Instance outside the axes", "instances", INFO, ("axisName",)),
    (3, 4, "INSTANCE_MULTIPLE_ON_LOCATION", "Two instances at one location", "instances", INFO, ()),
    (3, 5, "INSTANCE_REQUIRES_EXTRAPOLATION", "Instance needs extrapolation", "instances", INFO, ("axisName",)),
    (3, 6, "INSTANCE_MISSING_FAMILY_NAME", "Instance without a family name", "instances", INFO, ("instanceIndex",)),
    (3, 7, "INSTANCE_MISSING_STYLE_NAME", "Instance without a style name", "instances", INFO, ("instanceIndex",)),
    (3, 8, "INSTANCE_MISSING_FILENAME", "Instance without a file name", "instances", INFO, ("instanceIndex",)),
    (3, 10, "INSTANCE_NONE_DEFINED", "No instances", "instances", INFO, ()),
    (3, 11, "INSTANCE_OFF_DISCRETE_VALUES", "Instance off a discrete axis' values", "instances", WARN, ("axisName",)),
    (3, 12, "INSTANCE_UNKNOWN_LOCATION_LABEL", "Instance names an unknown location label", "instances", ERR, ("instanceIndex", "instanceName")),
    (3, 13, "INSTANCE_NAME_REUSED", "One instance name at two locations", "instances", WARN, ()),
    # --- 4 Glyphs ---
    (4, 0, "DIFFERENT_CONTOUR_COUNT", "Different contour counts", "compatibility", ERR, ("glyphName",)),
    (4, 1, "DIFFERENT_COMPONENTS", "Different components", "compatibility", ERR, ("glyphName",)),
    (4, 2, "DIFFERENT_ANCHORS", "Different anchors", "compatibility", WARN, ("glyphName",)),
    (4, 3, "DIFFERENT_ON_CURVES", "Different on-curve points", "compatibility", ERR, ("glyphName",)),
    (4, 4, "DIFFERENT_OFF_CURVES", "Different off-curve points", "compatibility", ERR, ("glyphName",)),
    (4, 5, "WRONG_CURVE_TYPE", "Different curve types", "compatibility", ERR, ("glyphName",)),
    (4, 7, "DEFAULT_GLYPH_EMPTY", "Glyph missing from the default", "coverage", ERR, ("glyphName",)),
    (4, 8, "WRONG_CONTOUR_DIRECTION", "Different contour directions", "compatibility", WARN, ("glyphName",)),
    (4, 9, "INCOMPATIBLE_GLYPH", "Incompatible structures", "compatibility", ERR, ("glyphName",)),
    (4, 10, "DIFFERENT_UNICODES", "Different unicodes", "compatibility", WARN, ("glyphName",)),
    (4, 11, "GLYPH_AXIS_SPAN_GAP", "Glyph does not reach an axis end", "coverage", ERR, ("glyphName", "axisName")),
    (4, 12, "GLYPH_EMPTY_IN_SOURCE", "Glyph empty in a master", "coverage", WARN, ("glyphName",)),
    (4, 13, "GLYPH_STATIC", "Glyph drawn only in the default", "coverage", WARN, ("glyphName",)),
    (4, 14, "CONTOUR_ORDER", "Contours in a different order", "interpolation", WARN, ("glyphName",), "interpolatable"),
    (4, 15, "WRONG_START_POINT", "Start point or direction differs", "interpolation", WARN, ("glyphName",), "interpolatable"),
    (4, 16, "UNDERWEIGHT", "Contour thins out halfway", "interpolation", WARN, ("glyphName",), "interpolatable"),
    (4, 17, "KINK", "Contour kinks halfway", "interpolation", INFO, ("glyphName",), "interpolatable"),
    (4, 18, "UNCHECKED_NO_SOLVER", "Glyphs not compared point by point", "interpolation", INFO, (), "interpolatable"),
    (4, 19, "COMPONENT_ORDER", "Components in a different order", "compatibility", ERR, ("glyphName",)),
    (4, 20, "COMPONENT_ORDER_CANONICAL", "Components out of the house order", "construction", WARN, ("glyphName",), "construction"),
    (4, 21, "COMPONENT_ROLE_UNKNOWN", "Component placed without a unicode", "construction", INFO, ("glyphName",), "construction"),
    (4, 22, "DUPLICATE_UNICODE", "Codepoint given to several glyphs", "unicodes", ERR, ("glyphName", "glyphNames", "codepoint", "sourceName", "layerName")),
    (4, 23, "MULTIPLE_UNICODES", "Glyph with several codepoints", "unicodes", INFO, ("glyphName", "codepoints", "sourceName", "layerName")),
    (4, 24, "COMPONENT_RING", "Components in a ring", "components", (ERR, WARN), ("glyphName", "glyphNames", "sourceName", "layerName")),
    (4, 25, "MISSING_COMPONENT_BASE", "Component of a missing glyph", "components", (ERR, WARN), ("glyphName", "sourceName", "layerName")),
    (4, 26, "OPEN_CONTOUR", "Open contour", "components", WARN, ("glyphName", "sourceName", "layerName")),
    (4, 27, "BURIED_POINT_SURFACES", "Buried point comes out between masters", "topology", WARN, ("glyphName",), "topology"),
    (4, 32, "SEGMENT_TURNS_OVER", "Segment turns over between masters", "topology", WARN, ("glyphName",), "topology"),
    (4, 33, "CURVE_LOOPS", "Curve loops between masters", "topology", WARN, ("glyphName",), "topology"),
    (4, 29, "PARTS_CANCEL", "Overlapping component cuts a hole", "direction", WARN, ("glyphName", "componentIndex", "baseGlyph")),
    (4, 30, "CONTOUR_DIRECTION", "Contour runs the wrong way", "direction", WARN, ("glyphName",)),
    (4, 31, "TRUETYPE_DIRECTION", "Master drawn in TrueType direction", "direction", WARN, ("sourceName",)),
    (4, 28, "BURIED_POINT_WANDERS", "Buried point is outside in some masters", "topology", WARN, ("glyphName", "sourceName"), "topology"),
    # --- 5 Kerning ---
    (5, 0, "NO_KERNING_IN_SOURCE", "Master without kerning", "kerning", WARN, ("sourceName",)),
    (5, 1, "NO_KERNING_IN_DEFAULT", "Default without kerning", "kerning", WARN, ("sourceName",)),
    (5, 2, "KERNING_GROUP_DIFFERS", "Kerning group members differ", "kerning", WARN, ("sourceName",)),
    (5, 3, "KERNING_GROUP_MISSING", "Kerning group missing", "kerning", WARN, ("sourceName",)),
    (5, 5, "NO_KERNING_GROUPS_DEFAULT", "Default without kerning groups", "kerning", WARN, ("sourceName",)),
    (5, 6, "NO_KERNING_GROUPS_SOURCE", "Master without kerning groups", "kerning", ERR, ("sourceName",)),
    (5, 7, "KERNING_GROUP_SORTED_DIFF", "Kerning group members in another order", "kerning", INFO, ("sourceName",)),
    (5, 8, "GLYPH_IN_TWO_KERN_GROUPS", "Glyph in two kerning groups of one side", "kerning", ERR, ("glyphName", "sourceName")),
    (5, 9, "KERNING_KEY_MALFORMED", "Unreadable kerning key", "kerning", ERR, ("sourceName",)),
    # --- 6 Font info ---
    (6, 0, "UNITS_PER_EM_DIFFERS", "unitsPerEm differs", "fontinfo", ERR, ("sourceName",)),
    (6, 1, "REQUIRED_FIELD_MISSING", "Required font info missing", "fontinfo", ERR, ("sourceName",)),
    (6, 2, "FIELD_DIFFERS", "Font info differs from the default", "fontinfo", WARN, ("sourceName",)),
    # --- 7 Rules ---
    (7, 0, "RULE_NO_CONDITIONS", "Rule that never applies", "rules", INFO, ("ruleName",)),
    (7, 1, "RULE_UNDEFINED_AXIS", "Rule condition on an unknown axis", "rules", INFO, ("ruleName", "axisName")),
    (7, 2, "RULE_INVALID_RANGE", "Rule condition range inverted", "rules", INFO, ("ruleName", "axisName")),
    (7, 3, "RULE_RANGE_OUT_OF_BOUNDS", "Rule condition outside the axis", "rules", INFO, ("ruleName", "axisName")),
    (7, 4, "RULE_NO_SUBSTITUTIONS", "Rule without substitutions", "rules", INFO, ("ruleName",)),
    (7, 5, "RULE_UNDEFINED_GLYPH", "Rule glyph missing from the default", "rules", ERR, ("ruleName", "glyphName")),
    (7, 6, "RULE_DUPLICATE_NAME", "Duplicate rule name", "rules", INFO, ("ruleName",)),
    (7, 7, "RULE_OVERLAP", "Overlapping rules on one glyph", "rules", WARN, ()),
    # --- 8 Features ---
    (8, 0, "FEATURE_FILE_CORRUPT", "features.fea cannot be read", "features", INFO, ("sourceName",)),
    (8, 1, "FEATURE_MISSING", "Feature missing in some masters", "features", INFO, ()),
    (8, 3, "FEATURES_DIFFER_FROM_DEFAULT", "features.fea off the variable path", "features", ERR, ()),
    # --- 9 Glyph order ---
    (9, 0, "GLYPHORDER_EXTRA_GLYPH", "Glyph not in the default", "glyph-order", WARN, ("glyphName",)),
    (9, 1, "GLYPHORDER_MISSING_GLYPH", "Glyph missing from a master", "glyph-order", WARN, (), "retired"),
    (9, 2, "GLYPHORDER_NAMING_MISMATCH", "Glyph order naming mismatch", "glyph-order", WARN, (), "retired"),
    (9, 3, "GLYPHORDER_POSITION_MISMATCH", "Glyph order breaks the merge", "glyph-order", WARN, ("glyphName", "sourceName")),
    # --- 10 Labels ---
    (10, 0, "INSTANCE_NAME_REPLACED", "Instance renamed in the variable font", "labels", (WARN, ERR), ("instanceName", "instanceIndex")),
    (10, 1, "VALUE_WITHOUT_LABEL", "Value no label covers", "labels", WARN, ("axisName",)),
    (10, 2, "ALL_ELIDED_NO_FALLBACK", "No elidedfallbackname", "labels", WARN, ("instanceIndices",)),
    (10, 3, "LABEL_OUTSIDE", "Label left out of STAT", "labels", (WARN, INFO), ()),
    (10, 4, "PARTIAL_LOCATION_LABEL", "Location label missing an axis", "labels", WARN, ()),
    (10, 5, "RANGE_LABEL_MALFORMED", "Range label that does not hold", "labels", WARN, ("axisName",)),
    (10, 6, "STYLE_LINK", "Style link missing or broken", "labels", (WARN, INFO), ("axisName",)),
    (10, 7, "LABEL_REDUNDANT", "Duplicate or missing label", "labels", INFO, ("axisName",)),
]
# fmt: on


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
            phase=(
                "interpolation"
                if "interpolatable" in flags
                else "construction"
                if "construction" in flags
                else "topology"
                if "topology" in flags
                else _PHASE[category]
            ),
            severities=severities,
            interpolatable_only="interpolatable" in flags,
            construction_only="construction" in flags,
            topology_only="topology" in flags,
            locators=tuple(locators),
            raw_keys=_raw_keys(key, locators),
            retired="retired" in flags,
        )
    return codes


def _raw_keys(key: tuple[int, int], locators) -> tuple[str, ...]:
    keys = list(locators) + [k for k in _RAW_KEYS.get(key, ()) if k not in locators]
    # The engine tags every finding of a phase it runs per discrete slice,
    # a phase that failed there included.
    if _PHASE.get(key[0]) not in ("file", "geometry", "labels") or key == (0, 1):
        keys.append("discreteLocation")
    return tuple(keys)


#: What every `raw_data` key means. One meaning per key; where codes read a
#: key differently, the text says which code reads it how. Master labels are
#: what `label_for_source` gives ("Bold.ufo (Bold)", "Light.ufo [mid]").
RAW_KEYS: dict[str, str] = {
    # --- locators (see the module docstring) ---
    "axisName": "The axis' name, as the designspace declares it (for 1.19-1.22 and 2.3/3.2, as written, which may be no axis at all).",
    "codepoint": "The codepoint, an int.",
    "codepoints": "The glyph's codepoints, ints, in the order the glyph lists them.",
    "glyphName": "The glyph the finding is about; for a group of glyphs (4.22, 4.24), the first of `glyphNames`.",
    "glyphNames": "Every glyph the finding is about: 4.22 those claiming the codepoint in build order, 4.24 the ring's glyphs, sorted.",
    "instanceIndex": "The instance's position in the document, from 0.",
    "instanceIndices": "Positions of the instances the finding is about, from 0.",
    "instanceName": "The instance's `name` attribute, or None when it has none.",
    "layerName": "The UFO layer the finding is in; None for the UFO's default layer.",
    "mappingIndex": "The avar2 mapping's position in the document, from 0.",
    "ruleName": "The rule's name (or a generated one when it has none).",
    "sourceName": "The source's `name` attribute in the designspace (its filename when it has none).",
    # --- where a finding's masters stand ---
    "locationType": 'How the masters of a finding are given: "groups" (`groups`: label -> masters) or "binary" (`presentIn` / `missingIn`).',
    "groups": 'Masters grouped by what they have, label -> master labels. The label is the value itself where it is short (4.0, 4.3, 4.4: the count; 4.8: "CW"/"CCW"; 4.10: the unicodes) and a placeholder otherwise ("pattern1", "type1", "order1"), most masters first.',
    "presentIn": "Labels of the masters that have it.",
    "missingIn": "Labels of the masters that lack it (4.12: the master where the glyph is empty).",
    "masters": "1.28: how many masters sit off the hidden axis' default. 4.14-4.17: the pair compared, [reference, other], master labels; the reference is the one on the default's side of the neighbour tree.",
    "pairs": "Every pair of neighbouring masters the same problem was found between, each [reference, other]; `masters` is the surest of them.",
    "discreteLocation": "The discrete slice the finding came from (axis name -> value), on designspaces with discrete axes; {} for the slice at the defaults.",
    "reference": "Label of the master the contours are read against: the default master of the slice.",
    "realign": 'For 4.5 and 4.8: master label -> {"proposedStart", "reversed"}; for 4.9: master label -> [{"contour", "proposedStart", "reversed"}]. The master\'s contour is the reference\'s points drawn from another start or the other way: `proposedStart` is the index, in the master\'s contour as drawn in the UFO, of the point that should come first; with `reversed` true the contour reads proposedStart, proposedStart-1, ... (see `designspace_lint.contours.align_contour`).',
    # --- run ---
    "phase": "The phase that raised.",
    "exception": "repr() of the exception it raised.",
    # --- axes and mappings ---
    "value": "The value the finding is about: 1.1 the axis' minimum (= its maximum); 2.4, 2.10, 3.3, 3.5, 3.11 the location's value on `axisName`, as the location gives it; 10.1 the value no label covers and 10.7 the value two labels share or none names (user coordinates).",
    "values": "The discrete axis' declared values.",
    "default": "1.2, 1.15, 1.16: the axis' default. 8.3: label of the default master.",
    "minimum": "Lower bound: of the axis (1.2, 1.4, 2.4), or of the rule's condition box (7.2).",
    "maximum": "Upper bound: of the axis (1.2, 1.4, 2.4), or of the rule's condition box (7.2).",
    "min": "The lower bound the instance's value is compared with.",
    "max": "The upper bound the instance's value is compared with.",
    "axisMin": "The axis' minimum (user coordinates).",
    "axisMax": "The axis' maximum (user coordinates).",
    "mapMin": "The smallest input of the axis' map.",
    "mapMax": "The largest input of the axis' map.",
    "input": "1.4: the map input outside the axis. 1.18: the mapping's input location, axis name -> value.",
    "output": "The mapping's output location, axis name -> value.",
    "inputs": "The axis map's inputs, in document order.",
    "outputs": "The axis map's outputs, in document order.",
    "axisIndex": "Position of the second axis of that name in the document, from 0.",
    "axisTag": "The tag both axes carry.",
    "side": 'Which side: 1.24 "input"/"output" of the mapping; 4.11 "minimum"/"maximum" of the axis; 5.8 "first"/"second" kerning side.',
    "clamped": 'Each clamped value: {"side": "input"|"output", "axisName", "value" as written, "usedValue" the axis end it is clamped to}.',
    "axes": 'Each output past the masters: {"axisName", "value", "masterExtent": [lowest, highest] master value on that axis}.',
    "writers": "Positions of the mappings that write the axis this mapping reads, from 0.",
    "from": "Normalized coordinate where the axis starts running backwards.",
    "to": "Normalized coordinate where it stops.",
    "duplicateOf": "What this repeats: 1.23 the earlier mapping's position; 2.6 the name of the source already at this location; 7.6 the earlier rule's position.",
    "variableFont": "The `<variable-font>`'s name.",
    # --- sources and instances ---
    "path": "Path of the UFO (2.x) or of the instance's file, None when it has none (3.1).",
    "location": "2.3 and 2.6: the source's location as written, axis name -> design value. 3.4: the location the instances share. 4.27: the worst sampled location, 4.28: the location of the master the point is furthest out in; axis name -> user value, continuous axes only (see `discreteLocation`).",
    "source": "The source's name (kept for older consumers; same as `sourceName`).",
    "availableLayers": "The layers the UFO does have.",
    "instance": "The instance's position in the document (kept for older consumers; same as `instanceIndex`).",
    "instances": 'Family and style of each instance at the location ("unnamed" for one with neither).',
    "kind": 'What carries the undeclared axis: "instance" or "label" (a location label).',
    "locationLabel": "The location label the instance names.",
    "familyName": "The instance's familyName.",
    "styleName": "The instance's styleName as written.",
    "statStyleName": "The style name the build derives from the axis and location labels instead.",
    # --- glyphs ---
    "baseGlyph": "The component's base glyph.",
    "anchorName": "The anchor's name.",
    "contourIndex": "Index of the contour in the glyph, from 0.",
    "contour": "Index of the contour, from 0, in interpolatable's list: the glyph's own contours (in UFO order), then one item per component.",
    "contours": 'For 4.26: indexes of the open contours, from 0. For 4.30: each contour that runs the wrong way, a dict: `contourIndex` (the UFO\'s, from 0), `role` ("outer", "counter", "island"), `depth` (how many contours it lies entirely inside, components\' included), `expected` and `actual` ("ccw" or "cw"; no `expected` when `ambiguous`), `container` (the contour it lies directly in: `{"contourIndex"}` for the glyph\'s own, `{"component", "contourIndex", "componentPath"}` for a component\'s, None for an outer contour), `consequence` ("filledCounter": a counter running like the contour it lies in, so filled; "cutsInk": it cuts holes where it overlaps; "againstConvention": it looks as meant -- alone, as a knockout, or reversed together with the contour it lies in -- but a TrueType build turns it the wrong way), `holes` (as for 4.29), and for a pair of contours that cross inside one contour and run the same way, `ambiguous: true` and `crosses` (the other\'s index): one of the two is reversed, which the finding cannot tell.',
    "componentIndex": "Index of the composite's component the finding is about, from 0.",
    "componentPath": "The glyphs from the composite down to the one whose contours are reversed: [composite, component's base, ...].",
    "cause": '"baseReversed": the component\'s base glyph runs the wrong way (4.30 on it), so reversing it fixes every composite that uses it; "mirrored": the component is mirrored here (`determinant` < 0) and its base runs the right way.',
    "holes": 'Masters where the hole shows, `sourceName` -> `{"area": square units, "point": [x, y] inside it, "bbox": [xMin, yMin, xMax, yMax]}`, in font units of that master.',
    "determinant": "`sourceName` -> the determinant of the component's whole transformation in that master; below 0 when mirrored.",
    "reverse": "Indexes of the base glyph's contours that run the wrong way: the ones to reverse, in every master, keeping their start points.",
    "usedBy": 'What reversing the glyph\'s wrong contours does to each composite that draws it, nested ones included (4.29: of the base glyph; 4.30: of the glyph itself, when it is used as a component): `{"fixes", "unaffected", "breaks"}`, each a list of `{"glyphName", "componentIndex", "componentPath"}`. "fixes" adds `masters`, where it cuts a hole now. "breaks" adds `masters` and `reason`: "mirrored" (mirrored there, so right only because of the flip: reversed, it would cut) or "knockout" (what lies inside it shows through it on purpose, a white digit in a black circle: reversed, it would be filled).',
    "convention": 'The direction the glyph is judged by: "postscript" (outer contours counter-clockwise, what ufo2ft expects) or "truetype" (when 4.31 found the default master drawn the other way).',
    "clockwiseGlyphs": "How many of the voted glyphs run their largest contour clockwise in the default master.",
    "votedGlyphs": "How many glyphs of the default master were counted (spread over the glyph list, at most 400).",
    "point": "Index of the point within the contour, as interpolatable counts them.",
    "type": 'fontTools interpolatable\'s problem type ("contour_order", "wrong_start_point", "underweight", "kink").',
    "tolerance": "4.14-4.17: interpolatable's score for the pair, 0..1: the lower, the surer the problem. 4.27/4.28: the units a buried point may come out of the ink and still count as on the edge.",
    "points": 'Every point of the glyph the finding is about, worst first, each a dict: `contour` and `point` (indexes from 0, the UFO\'s order), `depth` (units out of the ink, > 0), `location` (user values), `mastersBuried` (the `sourceName`s of the masters that keep it inside the ink); 4.27 adds `normalizedLocation` (where it is worst), `surfacing` and `checked` (at how many sampled locations it is out, of how many it was checked at); 4.28 adds `mastersOutside` (`{"sourceName", "depth"}` per master leaving it outside, worst first) and gives in `location` the worst of those masters\' location.',
    "segments": 'Each pair of consecutive points whose vector turns over, a dict: `contour`, `point` and `nextPoint` (indexes from 0, the UFO\'s order: the pair is a point and the next one, the last point\'s next being the first), `kind` ("handle": an on-curve point and its off-curve one; "betweenHandles": two off-curve points; "line": two on-curve points), `location` (user values) and `normalizedLocation` where it is shortest, `places` (grid edges and faces between masters it turns over on).',
    "curves": "Each cubic curve that crosses itself, a dict: `contour`, `point` (the curve's first on-curve point, UFO order), `location` (user values) and `normalizedLocation` where the loop is widest, `looping` and `checked` (at how many sampled locations it loops, of how many), `mastersLooping` (`sourceName`s of the masters that draw the loop already).",
    "axesBetween": "How the glyph's outlines were sampled between the masters: at most this many axes between master values at once, or None for every combination (the whole product). With 2, a point that comes out only where three axes are halfway at once goes unseen, and the worst depth can come out lower.",
    "normalizedLocation": "The worst sampled location, axis name -> normalized value (-1..1), as varLib's model reads it.",
    "correspondence": 'Present when the glyph\'s points do not correspond across the masters: interpolatable\'s problems between neighbouring masters, each `{"type": "contour_order" or "wrong_start_point", "masters": [reference, other] master labels, "contour"}`. Point by point the build pairs a point with another master\'s other point, which can make the finding by itself; the 4.14/4.15 of `--interpolatable` say more.',
    "proposedOrder": "fontTools' matching: for each item of the pair's reference (`masters[0]`), the index of the other master's item that matches it. Items as interpolatable lists them: the glyph's own contours (in UFO order), then one item per component, measured on its decomposed outline.",
    "proposedStart": "fontTools' proposed start point for the other master's contour: an index into the contour as interpolatable reads it (from its first on-curve point), which can differ from the UFO's point order. 4.5/4.8/4.9 give a UFO index in `realign`.",
    "reversed": "Whether the other master's contour runs the other way.",
    "axis": "The axis' name (kept for older consumers; same as `axisName`).",
    "required": "The axis value the masters reach on that side (design coordinates).",
    "covered": "The last value along the axis where the glyph is drawn (design coordinates).",
    "width": "The empty glyph's advance width in that master.",
    "orders": "Placeholder label -> the component base names in that order.",
    "current": "Placeholder label (as in `groups`) -> the components in their current order.",
    "expected": "Placeholder label -> the components in the expected order.",
    "expectedDiffers": "Whether the expected order differs between masters (the marks stack differently).",
    "components": 'Each component placed without a unicode: {"index", "baseGlyph", "reason", "sources": master labels}.',
    "glyphs": "4.18: the glyphs left unchecked. 7.7: the glyphs both rules substitute.",
    "links": "Each glyph of the ring -> its component bases that are in the ring: the components a fix chooses from.",
    "missingBases": "The component bases the build cannot find.",
    # --- kerning ---
    "font": "Label of the master.",
    "hasGroups": "Whether the master has kerning groups.",
    "groupName": "The kerning group.",
    "otherGroup": "The group of the same side that claimed the glyph first, and is kept.",
    "defaultMembers": "The group's members in the default master.",
    "sourceMembers": "The group's members in this master.",
    "keys": "The kerning keys a UFO reader refuses, each [first, second], at most 20.",
    # --- font info ---
    "field": "The fontinfo attribute.",
    "defaultValue": "Its value in the default master.",
    "sourceValue": "Its value in this master.",
    # --- rules ---
    "ruleIndex": "The rule's position in the document, from 0.",
    "axisMinimum": "The axis' minimum.",
    "axisMaximum": "The axis' maximum.",
    "conditionMinimum": "The condition's minimum as written.",
    "conditionMaximum": "The condition's maximum as written.",
    "substitution": 'Which side of the substitution names the missing glyph: "source" or "target".',
    "rules": "The names of the overlapping rules, in document order.",
    "declarationOrderRule": "The rule that wins by document order (what a reader of the file expects).",
    "variableFontRule": "The rule the variable font applies (its substitutions sort first).",
    # --- features ---
    "error": "The feature file's parse error, as the parser gives it.",
    "feature": "The feature's tag.",
    "count": "How many masters have it.",
    "total": "How many masters there are.",
    "matching": "Labels of the masters whose features.fea matches the default's.",
    "empty": "Labels of the masters with no features.fea.",
    "differing": "Labels of the masters whose features.fea differs from the default's.",
    # --- glyph order ---
    "sources": "Labels of the masters that have the glyph.",
    "defaultSourceIndex": "The default master's position among the sources, from 0.",
    "defaultSourcePath": "Path of the default master's UFO.",
    "defaultPosition": "The glyph's position in the default master's glyph order, from 0.",
    "sourceIndex": "The other master's position among the sources, from 0.",
    "sourcePath": "Path of the other master's UFO.",
    "sourcePosition": "The glyph's position in the other master's glyph order, from 0.",
    # --- labels ---
    "label": "The label's name.",
    "labels": "10.3: the labels the variable font's subset drops. 10.5: the two overlapping range labels. 10.7: the two labels at one value.",
    "linked": "The label's linked value (user coordinates).",
    "missingAxes": "The axes the location label leaves out.",
    "locations": "The locations, described, where every label is elided.",
}

#: Every `raw_data` key each live code's findings may carry, besides
#: `discreteLocation` (added by `_raw_keys`). Locators come first.
# fmt: off
_RAW_KEYS: dict[tuple[int, int], tuple[str, ...]] = {
    (0, 0): (),
    (0, 1): ('exception', 'phase'),
    (1, 0): (),
    (1, 1): ('axisName', 'value'),
    (1, 2): ('axisName', 'default', 'maximum', 'minimum'),
    (1, 3): ('axisName',),
    (1, 4): ('axisName', 'input', 'maximum', 'minimum'),
    (1, 6): ('axisName', 'axisMin', 'mapMin'),
    (1, 7): ('axisName', 'axisMax', 'mapMax'),
    (1, 8): ('axisName', 'inputs'),
    (1, 9): ('axisName', 'outputs'),
    (1, 13): ('axisName', 'axisIndex'),
    (1, 14): ('axisName', 'axisTag'),
    (1, 15): ('axisName', 'default', 'inputs'),
    (1, 16): ('axisName', 'default', 'values'),
    (1, 17): (),
    (1, 18): ('mappingIndex', 'input', 'output'),
    (1, 19): ('axisName', 'variableFont'),
    (1, 20): ('axisName', 'variableFont'),
    (1, 21): ('axisName', 'variableFont'),
    (1, 22): ('axisName', 'variableFont'),
    (1, 23): ('mappingIndex', 'duplicateOf'),
    (1, 24): ('mappingIndex', 'axisName', 'side'),
    (1, 25): ('mappingIndex', 'clamped'),
    (1, 26): ('mappingIndex', 'axes'),
    (1, 27): ('mappingIndex', 'axisName', 'writers'),
    (1, 28): ('axisName', 'masters'),
    (1, 29): ('axisName', 'from', 'to'),
    (2, 0): (),
    (2, 1): ('sourceName', 'path'),
    (2, 2): ('sourceName', 'path'),
    (2, 3): ('sourceName', 'axisName', 'location', 'path', 'source'),
    (2, 4): ('axisName', 'maximum', 'minimum', 'path', 'value'),
    (2, 5): (),
    (2, 6): ('sourceName', 'duplicateOf', 'location', 'path'),
    (2, 7): ('layerName', 'availableLayers', 'path'),
    (2, 10): ('sourceName', 'axisName', 'path', 'value'),
    (3, 1): ('instanceIndex', 'instance', 'path'),
    (3, 2): ('axisName', 'kind'),
    (3, 3): ('axisName', 'max', 'min', 'value'),
    (3, 4): ('instances', 'location'),
    (3, 5): ('axisName', 'max', 'min', 'value'),
    (3, 6): ('instanceIndex', 'instance', 'instanceName'),
    (3, 7): ('instanceIndex', 'instance', 'instanceName'),
    (3, 8): ('instanceIndex', 'instance', 'instanceName'),
    (3, 10): (),
    (3, 11): ('axisName', 'value'),
    (3, 12): ('instanceIndex', 'instanceName', 'instance', 'locationLabel'),
    (3, 13): ('familyName', 'styleName'),
    (4, 0): ('glyphName', 'groups', 'locationType'),
    (4, 1): ('glyphName', 'baseGlyph', 'locationType', 'missingIn', 'presentIn'),
    (4, 2): ('glyphName', 'anchorName', 'locationType', 'missingIn', 'presentIn'),
    (4, 3): ('glyphName', 'contourIndex', 'groups', 'locationType'),
    (4, 4): ('glyphName', 'contourIndex', 'groups', 'locationType'),
    (4, 5): ('glyphName', 'contourIndex', 'groups', 'locationType', 'realign', 'reference'),
    (4, 7): ('glyphName', 'locationType', 'missingIn', 'presentIn'),
    (4, 8): ('glyphName', 'contourIndex', 'groups', 'locationType', 'realign', 'reference'),
    (4, 9): ('glyphName', 'groups', 'locationType', 'realign', 'reference'),
    (4, 10): ('glyphName', 'groups', 'locationType'),
    (4, 11): ('glyphName', 'axisName', 'axis', 'covered', 'locationType', 'missingIn', 'required', 'side'),
    (4, 12): ('glyphName', 'locationType', 'missingIn', 'presentIn', 'width'),
    (4, 13): ('glyphName', 'locationType', 'presentIn'),
    (4, 14): ('glyphName', 'masters', 'pairs', 'proposedOrder', 'tolerance', 'type'),
    (4, 15): ('glyphName', 'contour', 'masters', 'pairs', 'proposedStart', 'reversed', 'tolerance', 'type'),
    (4, 16): ('glyphName', 'contour', 'masters', 'pairs', 'tolerance', 'type'),
    (4, 17): ('glyphName', 'contour', 'masters', 'pairs', 'point', 'tolerance', 'type'),
    (4, 18): ('glyphs',),
    (4, 19): ('glyphName', 'groups', 'locationType', 'orders'),
    (4, 20): ('glyphName', 'current', 'expected', 'expectedDiffers', 'groups', 'locationType'),
    (4, 21): ('glyphName', 'components'),
    (4, 22): ('glyphName', 'glyphNames', 'codepoint', 'sourceName', 'layerName'),
    (4, 32): ('glyphName', 'correspondence', 'segments'),
    (4, 33): ('glyphName', 'axesBetween', 'correspondence', 'curves'),
    (4, 29): ('glyphName', 'componentIndex', 'baseGlyph', 'cause', 'componentPath', 'determinant', 'holes', 'reverse', 'usedBy'),
    (4, 30): ('glyphName', 'contours', 'convention', 'usedBy'),
    (4, 31): ('sourceName', 'clockwiseGlyphs', 'convention', 'votedGlyphs'),
    (4, 27): ('glyphName', 'axesBetween', 'correspondence', 'location', 'normalizedLocation', 'points', 'tolerance'),
    (4, 28): ('glyphName', 'sourceName', 'axesBetween', 'correspondence', 'location', 'points', 'tolerance'),
    (4, 23): ('glyphName', 'codepoints', 'sourceName', 'layerName'),
    (4, 24): ('glyphName', 'glyphNames', 'sourceName', 'layerName', 'links'),
    (4, 25): ('glyphName', 'sourceName', 'layerName', 'missingBases'),
    (4, 26): ('glyphName', 'sourceName', 'layerName', 'contours'),
    (5, 0): ('sourceName', 'font', 'hasGroups'),
    (5, 1): ('sourceName', 'font'),
    (5, 2): ('sourceName', 'defaultMembers', 'font', 'groupName', 'sourceMembers'),
    (5, 3): ('sourceName', 'font', 'groupName'),
    (5, 5): ('sourceName', 'font'),
    (5, 6): ('sourceName', 'font'),
    (5, 7): ('sourceName', 'defaultMembers', 'font', 'groupName', 'sourceMembers'),
    (5, 8): ('glyphName', 'sourceName', 'font', 'groupName', 'otherGroup', 'side'),
    (5, 9): ('sourceName', 'font', 'keys'),
    (6, 0): ('sourceName', 'defaultValue', 'field', 'sourceValue'),
    (6, 1): ('sourceName', 'field'),
    (6, 2): ('sourceName', 'defaultValue', 'field', 'sourceValue'),
    (7, 0): ('ruleName', 'ruleIndex'),
    (7, 1): ('ruleName', 'axisName'),
    (7, 2): ('ruleName', 'axisName', 'maximum', 'minimum'),
    (7, 3): ('ruleName', 'axisName', 'axisMaximum', 'axisMinimum', 'conditionMaximum', 'conditionMinimum'),
    (7, 4): ('ruleName', 'ruleIndex'),
    (7, 5): ('ruleName', 'glyphName', 'substitution'),
    (7, 6): ('ruleName', 'duplicateOf', 'ruleIndex'),
    (7, 7): ('declarationOrderRule', 'glyphs', 'rules', 'variableFontRule'),
    (8, 0): ('sourceName', 'error'),
    (8, 1): ('count', 'feature', 'total'),
    (8, 3): ('default', 'differing', 'empty', 'matching'),
    (9, 0): ('glyphName', 'sources'),
    (9, 3): ('glyphName', 'sourceName', 'defaultPosition', 'defaultSourceIndex', 'defaultSourcePath', 'sourceIndex', 'sourcePath', 'sourcePosition'),
    (10, 0): ('instanceName', 'instanceIndex', 'statStyleName', 'styleName'),
    (10, 1): ('axisName', 'instanceIndex', 'instanceName', 'value'),
    (10, 2): ('instanceIndices', 'locations'),
    (10, 3): ('axisName', 'label', 'labels', 'variableFont'),
    (10, 4): ('label', 'missingAxes'),
    (10, 5): ('axisName', 'label', 'labels'),
    (10, 6): ('axisName', 'label', 'linked'),
    (10, 7): ('axisName', 'labels', 'value'),
}
# fmt: on


#: Every code, keyed by `(category, code)`.
CODES: dict[tuple[int, int], CodeInfo] = _build()


def code_info(problem) -> CodeInfo | None:
    """The catalogue entry for a finding, or None for a code this version does not know."""
    return CODES.get((problem.category, problem.code))


__all__ = ["CODES", "GROUPS", "RAW_KEYS", "CodeInfo", "code_info"]
