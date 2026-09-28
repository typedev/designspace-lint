# Copyright 2026 Alexander Lubovenko
# Licensed under the Apache License, Version 2.0

"""
The public surface consumers build on: the code catalogue, explicit severity,
locators, scoped runs, and the helpers that used to be private.

Font-Rover derives its filter groups from `CODES` and locates what a finding is
about from `raw_data`; these tests are what makes that safe to rely on. The
conftest fixture checks every result the suite produces against the catalogue;
here the catalogue is checked against the source, and a run over the audit's
probe designspaces makes sure most codes are exercised for real.
"""

import ast
import logging
from pathlib import Path

import pytest

import designspace_lint
from designspace_lint import CODES, lint
from designspace_lint.codes import GROUPS
from designspace_lint.engine import INTERPOLATION_PHASE, PHASES
from designspace_lint.model import SEVERITY_DESIGN, SEVERITY_INFO, SEVERITY_STRUCTURAL
from fakes import FakeGlyph, build_designspace

PACKAGE = Path(designspace_lint.__file__).parent
PROBES = PACKAGE.parent / "docs" / "audit" / "2026-09-coverage" / "probes"

# Module -> category, for the modules whose integer constants are codes.
CODE_MODULES = {
    "checkers/file.py": 0,
    "engine.py": 0,
    "checkers/axes.py": 1,
    "checkers/avar2.py": 1,
    "checkers/sources.py": 2,
    "checkers/instances.py": 3,
    "checkers/glyphs.py": 4,
    "checkers/interpolation.py": 4,
    "checkers/kerning.py": 5,
    "checkers/fontinfo.py": 6,
    "checkers/rules.py": 7,
    "checkers/features.py": 8,
    "checkers/glyphorder.py": 9,
    "checkers/labels.py": 10,
}
NOT_CODES = {"TOLERANCE", "EPSILON", "MIN_AREA_THRESHOLD"}


def _constants(path: Path) -> dict[str, int]:
    tree = ast.parse(path.read_text())
    found = {}
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id.isupper()
            and node.targets[0].id not in NOT_CODES
            and isinstance(node.value, ast.Constant)
            and type(node.value.value) is int
        ):
            found[node.targets[0].id] = node.value.value
    return found


def _is_used(name: str) -> bool:
    """Whether a code constant is read anywhere, so it can be reported."""
    for path in PACKAGE.rglob("*.py"):
        if path.name == "codes.py":
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Name) and node.id == name and isinstance(node.ctx, ast.Load):
                return True
    return False


def test_every_code_constant_is_in_the_catalogue():
    by_const = {(info.category, info.const_name): info for info in CODES.values()}
    for module, category in CODE_MODULES.items():
        for name, value in _constants(PACKAGE / module).items():
            info = by_const.get((category, name))
            assert info is not None, f"{module}: {name} = {value} is not in CODES"
            assert info.code == value, f"{name}: CODES says {info.code}, source says {value}"


def test_retired_means_never_reported():
    by_const = {(info.category, info.const_name): info for info in CODES.values()}
    for module, category in CODE_MODULES.items():
        for name in _constants(PACKAGE / module):
            info = by_const[(category, name)]
            assert info.retired == (not _is_used(name)), name


def test_catalogue_entries_are_well_formed():
    phases = {p[0] for p in PHASES} | {INTERPOLATION_PHASE[0]}
    for (category, code), info in CODES.items():
        assert (info.category, info.code) == (category, code)
        assert info.group in GROUPS and info.group_title == GROUPS[info.group]
        assert info.phase in phases, info
        assert info.default_severity == info.severities[0]
        assert set(info.severities) <= {SEVERITY_STRUCTURAL, SEVERITY_DESIGN, SEVERITY_INFO}
        assert info.interpolatable_only == (info.phase == "interpolation")


@pytest.mark.skipif(not PROBES.is_dir(), reason="the audit probes ship with the repository only")
def test_the_audit_probes_produce_only_catalogued_findings():
    """The conftest fixture checks each result; this just makes a lot of them."""
    logging.disable(logging.CRITICAL)
    try:
        seen = set()
        for path in sorted(PROBES.rglob("*.designspace")):
            try:
                results = designspace_lint.lint_path(path, interpolatable=True)
            except Exception:
                continue  # unreadable on purpose: that is the probe
            seen |= {(r.category, r.code) for r in results}
    finally:
        logging.disable(logging.NOTSET)
    assert len(seen) >= 50


# --- explicit severity -------------------------------------------------------


def _entry(glyphs_light, glyphs_bold):
    return build_designspace(
        axes=[{"name": "Weight", "tag": "wght", "minimum": 0, "default": 0, "maximum": 100}],
        sources=[
            {"name": "Light", "location": {"Weight": 0}, "glyphs": glyphs_light},
            {"name": "Bold", "location": {"Weight": 100}, "glyphs": glyphs_bold},
        ],
    )


def _square(name, size=100):
    return FakeGlyph(name, contours=[[(0, 0), (size, 0), (size, size), (0, size)]])


def test_every_result_from_the_engine_carries_its_severity():
    entry = _entry({"A": _square("A")}, {"A": _square("A", 150), "B": _square("B")})
    results = lint(entry)
    assert results
    assert all(r.severity is not None for r in results)


# --- scoped runs -------------------------------------------------------------


def test_a_scoped_run_checks_only_the_named_glyphs():
    light = {"A": _square("A"), "B": _square("B")}
    bold = {"A": FakeGlyph("A", contours=[]), "B": FakeGlyph("B", contours=[])}
    entry = _entry(light, bold)

    everything = {r.glyph_name for r in lint(entry, phases=["glyphs"]) if r.glyph_name}
    scoped = {r.glyph_name for r in lint(entry, phases=["glyphs"], glyphs=["A"]) if r.glyph_name}

    assert everything == {"A", "B"}
    assert scoped == {"A"}


def test_a_scoped_run_skips_the_other_phases_but_not_the_file_checks():
    entry = _entry({"A": _square("A")}, {"A": _square("A", 150)})
    categories = {r.category for r in lint(entry, phases=["glyphs"])}
    assert 2 not in categories  # sources (2.1 for the fake paths) did not run
    assert 3 not in categories  # nor instances


def test_an_unknown_phase_is_an_error():
    with pytest.raises(ValueError, match="unknown phase"):
        lint(_entry({}, {}), phases=["glyps"])


# --- public helpers, and the names they had -----------------------------------


def test_the_old_private_names_still_work_for_one_release():
    from designspace_lint import glyph_order
    from designspace_lint.checkers.base import BaseChecker

    assert glyph_order._first_wins is glyph_order.dedupe_glyph_order
    assert glyph_order._raw_glyph_order is glyph_order.raw_glyph_order
    entry = _entry({"A": _square("A")}, {"A": _square("A")})
    source = entry.sources[0]
    assert designspace_lint.label_for_source(source) == BaseChecker._source_label(source)
