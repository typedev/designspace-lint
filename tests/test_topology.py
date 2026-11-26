# Copyright 2026 Alexander Lubovenko
# Licensed under the Apache License, Version 2.0

"""
Buried points that come out of the ink between the masters (4.27, 4.28).

The example is designspace-lint#5's: a stem whose top leans further right
with weight, and an arm whose tip sits 5 units inside the stem's right edge
in both masters. The tip moves linearly, and so does the edge's top; where
the edge lies at the tip's height is a product of the two, so halfway the
tip is 64 units out of the stem, and the instance there has a spike.
"""

import json
import sys

import pytest

from designspace_lint import cli, lint
from designspace_lint.checkers.topology import BURIED_POINT_SURFACES, BURIED_POINT_WANDERS
from designspace_lint.engine import Linter
from designspace_lint.model import CATEGORY_GLYPHS, SEVERITY_DESIGN, effective_severity
from fakes import FakeGlyph, build_designspace

np = pytest.importorskip("numpy")

from designspace_lint import topology  # noqa: E402

WEIGHT = {"name": "Weight", "tag": "wght", "minimum": 0, "default": 0, "maximum": 1000}


def _k(top, tip):
    """A stem `(0,0) (100,0) (top,700) (0,700)` and an arm pointing into it at `tip`."""
    x, y = tip
    stem = [(0, 0), (100, 0), (top, 700), (0, 700)]
    arm = [(x, y), (x + 300, y - 50), (x + 300, y + 50)]
    return FakeGlyph("K", contours=[stem, arm], unicodes=[0x4B])


LIGHT = _k(100, (95, 100))
BOLD = _k(500, (437.86, 600))


def _entry(*masters, axes=(WEIGHT,)):
    """`masters`: (name, weight, glyph or None) -- None leaves the glyph out."""
    sources = []
    for name, weight, glyph in masters:
        glyphs = {"space": FakeGlyph("space", unicodes=[0x20])}
        if glyph is not None:
            glyphs["K"] = glyph
        sources.append({"name": name, "location": {"Weight": weight}, "glyphs": glyphs})
    return build_designspace(axes=list(axes), sources=sources)


def _found(entry, **kwargs):
    return [
        r
        for r in lint(entry, topology=True, phases=["topology"], **kwargs)
        if r.category == CATEGORY_GLYPHS and r.code in (BURIED_POINT_SURFACES, BURIED_POINT_WANDERS)
    ]


def test_a_tip_hidden_in_both_masters_comes_out_halfway():
    (finding,) = _found(_entry(("Light", 0, LIGHT), ("Bold", 1000, BOLD)))

    assert finding.code == BURIED_POINT_SURFACES
    assert effective_severity(finding) == SEVERITY_DESIGN
    assert finding.glyph_name == "K"
    worst = finding.raw_data["points"][0]
    assert (worst["contour"], worst["point"]) == (1, 0)
    # 63.9 units out at weight 500, the sampled location nearest the peak
    assert finding.raw_data["location"] == {"Weight": 500.0}
    assert finding.raw_data["normalizedLocation"] == {"Weight": 0.5}
    assert worst["depth"] == pytest.approx(63.9, abs=0.2)
    assert sorted(worst["mastersBuried"]) == ["Bold", "Light"]
    assert worst["surfacing"] >= 1 and worst["checked"] >= worst["surfacing"]
    assert "Weight=500" in finding.location
    assert "correspondence" not in finding.raw_data


def test_a_master_at_the_peak_that_keeps_the_tip_inside_fixes_it():
    medium = _k(300, (195, 350))  # the tip 5 units inside the leaning stem
    found = _found(_entry(("Light", 0, LIGHT), ("Medium", 500, medium), ("Bold", 1000, BOLD)))
    # still out a little at the quarters, but far less than without it
    assert all(p["depth"] < 20 for r in found for p in r.raw_data["points"])


def test_a_master_without_the_glyph_is_left_out_as_varlib_does():
    found = _found(_entry(("Light", 0, LIGHT), ("Medium", 500, None), ("Bold", 1000, BOLD)))
    (finding,) = found
    assert finding.raw_data["points"][0]["depth"] == pytest.approx(63.9, abs=0.2)
    assert sorted(finding.raw_data["points"][0]["mastersBuried"]) == ["Bold", "Light"]


def test_an_upright_stem_keeps_the_tip_inside_everywhere():
    light = _k(100, (95, 100))
    bold = _k(100, (95, 600))
    assert _found(_entry(("Light", 0, light), ("Bold", 1000, bold))) == []


def test_a_point_outside_in_one_master_is_reported_by_master_and_not_between():
    bold = _k(500, (445.86, 600))  # 3 units right of the edge: outside in Bold
    (finding,) = _found(_entry(("Light", 0, LIGHT), ("Bold", 1000, bold)))

    assert finding.code == BURIED_POINT_WANDERS
    assert finding.raw_data["sourceName"] == "Bold"
    assert finding.raw_data["location"] == {"Weight": 1000.0}
    (point,) = finding.raw_data["points"]
    assert point["mastersBuried"] == ["Light"]
    assert [m["sourceName"] for m in point["mastersOutside"]] == ["Bold"]
    assert point["depth"] == pytest.approx(2.6, abs=0.2)  # 3 units across, along the slant
    assert "Bold.ufo (Bold)" in finding.location


def test_the_tolerance_decides_what_counts_as_out():
    # the arm tip half a unit inside the edge in both masters
    light = _k(100, (99.5, 100))
    bold = _k(100, (99.5, 600))
    entry = _entry(("Light", 0, light), ("Bold", 1000, bold))
    assert _found(entry) == []  # not buried by more than the default unit
    # with zero tolerance it is buried, and stays inside: still nothing
    assert _found(entry, topology_tolerance=0) == []


def test_points_that_do_not_correspond_say_so():
    x, y = 437.86, 600
    turned = FakeGlyph(
        "K",
        contours=[
            [(0, 0), (100, 0), (500, 700), (0, 700)],
            [(x + 300, y - 50), (x + 300, y + 50), (x, y)],  # the tip drawn last
        ],
    )
    found = _found(_entry(("Light", 0, LIGHT), ("Bold", 1000, turned)))

    assert found
    for finding in found:
        (problem,) = finding.raw_data["correspondence"]
        assert problem["type"] == "wrong_start_point"
        assert problem["contour"] == 1
        assert "do not correspond" in finding.details


def test_the_phase_needs_asking_for():
    entry = _entry(("Light", 0, LIGHT), ("Bold", 1000, BOLD))
    assert not [r for r in lint(entry) if r.code in (BURIED_POINT_SURFACES, BURIED_POINT_WANDERS)]


def test_without_numpy_the_phase_refuses_to_start(monkeypatch):
    monkeypatch.setitem(sys.modules, "numpy", None)
    with pytest.raises(ImportError, match="designspace-lint\\[topology\\]"):
        Linter(designspace=_entry(("Light", 0, LIGHT), ("Bold", 1000, BOLD)), topology=True)


def test_each_glyph_is_reported_to_the_progress_bar():
    ticks = []
    linter = Linter(designspace=_entry(("Light", 0, LIGHT), ("Bold", 1000, BOLD)), topology=True)
    list(linter.run(on_progress=lambda done, total, message: ticks.append(message)))
    assert "Checking outlines between masters (2/2)" in ticks


def test_the_command_line_runs_it(monkeypatch, capsys):
    entry = _entry(("Light", 0, LIGHT), ("Bold", 1000, BOLD))
    monkeypatch.setattr("designspace_lint.lint_path", lambda path, **kwargs: lint(entry, **kwargs))
    assert cli.main(["x.designspace", "--topology", "--json"]) == 1
    rows = json.loads(capsys.readouterr().out)
    (row,) = [r for r in rows if r["code"] == f"4.{BURIED_POINT_SURFACES}"]
    assert row["raw_data"]["points"][0]["contour"] == 1


def test_point_tags_follow_the_ufo_segment_types():
    contour = [
        (0, 0, "line"),
        (0, 50, None),
        (50, 100, None),
        (100, 100, "curve"),
        (120, 80, None),
        (100, 0, "qcurve"),
    ]
    tags = topology.point_tags(contour)
    assert tags == [
        topology.TAG_ON,
        topology.TAG_CUBIC,
        topology.TAG_CUBIC,
        topology.TAG_ON,
        topology.TAG_CONIC,
        topology.TAG_ON,
    ]
    assert topology.point_tags([(0, 0, None), (10, 0, None)]) == [topology.TAG_CONIC] * 2


def test_a_host_can_check_one_location_with_the_same_rule():
    from fontTools.varLib.models import VariationModel

    masters = topology.GlyphMasters(
        name="K",
        sources=("Light", "Bold"),
        model=VariationModel([{"Weight": 0.0}, {"Weight": 1.0}], axisOrder=["Weight"]),
        points=np.array(
            [
                [(0, 0), (100, 0), (100, 700), (0, 700), (95, 100), (395, 50), (395, 150)],
                [
                    (0, 0),
                    (100, 0),
                    (500, 700),
                    (0, 700),
                    (437.86, 600),
                    (737.86, 550),
                    (737.86, 650),
                ],
            ],
            dtype=float,
        ),
        contours=np.array([3, 6]),
        tags=np.array([topology.TAG_ON] * 7, dtype=np.int8),
        design_axes={"Weight": (0, 0, 1000)},
    )
    checker = topology.BuriedPointChecker(masters)
    assert checker.at({"Weight": 0.0}) == []
    ((contour, point, depth, (x, y)),) = checker.at({"Weight": 0.5})
    assert (contour, point) == (1, 0)
    assert depth == pytest.approx(63.9, abs=0.2)
    assert (x, y) == pytest.approx(topology.point_at(masters, {"Weight": 0.5}, 1, 0))


def test_a_sparse_layer_master_that_keeps_the_tip_inside_fixes_it():
    medium = _k(300, (195, 350))
    entry = build_designspace(
        axes=[WEIGHT],
        sources=[
            {
                "name": "Light",
                "location": {"Weight": 0},
                "glyphs": {"K": LIGHT, "space": FakeGlyph("space", unicodes=[0x20])},
                "layers": {"medium": {"K": medium}},
            },
            {
                "name": "Medium",
                "path": "/tmp/fake/Light.ufo",
                "layer_name": "medium",
                "location": {"Weight": 500},
            },
            {
                "name": "Bold",
                "location": {"Weight": 1000},
                "glyphs": {"K": BOLD, "space": FakeGlyph("space", unicodes=[0x20])},
            },
        ],
    )
    found = _found(entry)
    assert all(p["depth"] < 20 for r in found for p in r.raw_data["points"])
    assert all("Medium" in p["mastersBuried"] for r in found for p in r.raw_data["points"])


def test_each_discrete_slice_is_its_own_space():
    italic = {"name": "Italic", "tag": "ital", "values": [0, 1], "default": 0}
    upright = _k(100, (95, 600))  # an upright stem: nothing comes out
    sources = []
    for name, weight, ital, glyph in (
        ("Light", 0, 0, upright),
        ("Bold", 1000, 0, upright),
        ("LightItalic", 0, 1, LIGHT),
        ("BoldItalic", 1000, 1, BOLD),
    ):
        sources.append(
            {"name": name, "location": {"Weight": weight, "Italic": ital}, "glyphs": {"K": glyph}}
        )
    (finding,) = _found(build_designspace(axes=[WEIGHT, italic], sources=sources))
    assert finding.code == BURIED_POINT_SURFACES
    assert finding.raw_data["discreteLocation"] == {"Italic": 1}
    assert finding.raw_data["location"] == {"Weight": 500.0}


def test_the_weights_at_many_locations_are_fonttools_own():
    import itertools

    from fontTools.varLib.models import VariationModel

    axes = ["A", "B", "C"]
    masters = [
        {},
        {"A": 1},
        {"A": -1},
        {"B": 1},
        {"A": 1, "B": 1},
        {"C": 0.4},
        {"A": 0.5, "C": 1},
        {"B": -0.6, "C": -1},
    ]
    model = VariationModel(masters, axisOrder=axes)
    grid = [-1, -0.7, -0.25, 0, 0.15, 0.4, 0.6, 1]
    locations = [dict(zip(axes, c, strict=True)) for c in itertools.product(grid, repeat=3)]
    fast = topology.master_scalars_at(model, locations)
    slow = np.array([model.getMasterScalars(location) for location in locations])
    assert np.abs(fast - slow).max() < 1e-12


def test_at_most_two_axes_sit_between_masters_at_once():
    from fontTools.varLib.models import VariationModel

    axes = ["A", "B", "C"]
    corners = [{}, {"A": 1}, {"B": 1}, {"C": 1}]
    masters = topology.GlyphMasters(
        "x",
        (),
        VariationModel(corners, axisOrder=axes),
        np.zeros((4, 0, 2)),
        [],
        [],
        {name: (0, 0, 1) for name in axes},
    )
    whole = topology.sample_locations(masters, axes_between=None)
    two = topology.sample_locations(masters, axes_between=2)
    assert len(whole) == 5**3  # 0, the quarters, 1 on each axis
    # 2^3 corners, 3·3·2^2 with one axis between, 3·3^2·2 with two
    assert len(two) == 8 + 36 + 54
    key = lambda loc: tuple(loc[name] for name in axes)  # noqa: E731
    assert {key(loc) for loc in two} <= {key(loc) for loc in whole}
    assert all(sum(loc[name] not in (0.0, 1.0) for name in axes) <= 2 for loc in two)


def test_auto_takes_the_whole_product_while_it_stays_small(monkeypatch):
    from fontTools.varLib.models import VariationModel

    axes = ["A", "B", "C"]
    masters = topology.GlyphMasters(
        "x",
        (),
        VariationModel([{}, {"A": 1}, {"B": 1}, {"C": 1}], axisOrder=axes),
        np.zeros((4, 0, 2)),
        [],
        [],
        {name: (0, 0, 1) for name in axes},
    )
    assert topology.resolve_axes_between(masters) is None  # 125 locations
    assert len(topology.sample_locations(masters)) == 5**3
    monkeypatch.setattr(topology, "AUTO_LIMIT", 100)
    assert topology.resolve_axes_between(masters) == topology.AXES_BETWEEN
    assert len(topology.sample_locations(masters)) == 8 + 36 + 54
    assert topology.resolve_axes_between(masters, 1) == 1
    assert topology.resolve_axes_between(masters, None) is None


def test_the_findings_say_how_the_outlines_were_sampled():
    entry = _entry(("Light", 0, LIGHT), ("Bold", 1000, BOLD))
    (whole,) = _found(entry)
    assert whole.raw_data["axesBetween"] is None  # one axis: the whole product is small
    (one,) = _found(entry, topology_axes_between=1)
    assert one.raw_data["axesBetween"] == 1
    # no axis between master values: only the masters are looked at, where it hides
    assert _found(entry, topology_axes_between=0) == []


def test_the_command_line_takes_the_sampling(monkeypatch, capsys):
    entry = _entry(("Light", 0, LIGHT), ("Bold", 1000, BOLD))
    seen = {}

    def fake(path, **kwargs):
        seen.update(kwargs)
        return lint(entry, **kwargs)

    monkeypatch.setattr("designspace_lint.lint_path", fake)
    for flag, value in (("all", None), ("2", 2), ("auto", "auto")):
        cli.main(["x.designspace", "--topology", "--json", "--topology-axes-between", flag])
        assert seen["topology_axes_between"] == value
    capsys.readouterr()
    with pytest.raises(SystemExit):
        cli.main(["x.designspace", "--topology-axes-between", "many"])


# --- designspace-lint#2: segments that turn over, curves that loop -----------

from designspace_lint.checkers.topology import CURVE_LOOPS, SEGMENT_TURNS_OVER  # noqa: E402
from fakes import FakeContour, FakePoint  # noqa: E402


def _bowl(h1, h2, name="D"):
    """A stem and a bowl drawn as one cubic: (0,0) (0,700) h1 h2, back to the start."""
    points = [
        FakePoint(0, 0, "curve"),
        FakePoint(0, 700, "line"),
        FakePoint(*h1, "offcurve"),
        FakePoint(*h2, "offcurve"),
    ]
    return FakeGlyph(name, contours=[FakeContour(points)])


def _two(light, bold):
    return _entry(("Light", 0, light), ("Bold", 1000, bold))


def _codes(entry, code):
    return [r for r in lint(entry, topology=True, phases=["topology"]) if r.code == code]


def test_a_clean_bowl_neither_turns_over_nor_loops():
    entry = _two(_bowl((400, 700), (400, 0)), _bowl((600, 750), (600, -50)))
    assert _codes(entry, SEGMENT_TURNS_OVER) == []
    assert _codes(entry, CURVE_LOOPS) == []


def test_a_handle_turned_through_its_point_turns_over():
    # in Bold the first handle points back, behind the stem's top
    (finding,) = _codes(
        _two(_bowl((400, 700), (400, 0)), _bowl((-400, 700), (400, 0))), SEGMENT_TURNS_OVER
    )
    (segment,) = [s for s in finding.raw_data["segments"] if s["kind"] == "handle"]
    assert (segment["contour"], segment["point"], segment["nextPoint"]) == (0, 1, 2)
    assert 0 < segment["normalizedLocation"]["Weight"] < 1
    assert effective_severity(finding) == SEVERITY_DESIGN


def test_two_handles_swapped_turn_the_span_between_them_over():
    (finding,) = _codes(
        _two(_bowl((400, 700), (400, 0)), _bowl((400, 0), (400, 700))), SEGMENT_TURNS_OVER
    )
    kinds = {s["kind"] for s in finding.raw_data["segments"]}
    assert "betweenHandles" in kinds


def test_a_curve_that_crosses_itself_loops():
    # crossed handles alone do not loop; these reach out and back past each other
    assert _codes(_two(_bowl((400, 700), (400, 0)), _bowl((700, 0), (700, 700))), CURVE_LOOPS) == []
    looping = _bowl((900, -300), (900, 1000))
    (finding,) = _codes(_two(_bowl((400, 700), (400, 0)), looping), CURVE_LOOPS)
    (curve,) = finding.raw_data["curves"]
    assert (curve["contour"], curve["point"]) == (0, 1)
    assert curve["mastersLooping"] == ["Bold"]
    assert 0 < curve["looping"] <= curve["checked"]
    assert finding.raw_data["axesBetween"] is None


def test_a_full_turn_inside_a_face_is_seen_though_no_edge_shows_it():
    # the vector of the first two points at the four corners: right, up, left,
    # down -- a quarter turn along each edge, a full turn around the face
    corners = {(0, 0): (100, 0), (1000, 0): (0, 100), (1000, 1000): (-100, 0), (0, 1000): (0, -100)}
    axes = [
        {"name": "Weight", "tag": "wght", "minimum": 0, "default": 0, "maximum": 1000},
        {"name": "Width", "tag": "wdth", "minimum": 0, "default": 0, "maximum": 1000},
    ]
    sources = []
    for (w, x), (dx, dy) in corners.items():
        glyph = FakeGlyph("x", contours=[[(300, 300), (300 + dx, 300 + dy), (300, 900)]])
        sources.append(
            {"name": f"m{w}_{x}", "location": {"Weight": w, "Width": x}, "glyphs": {"x": glyph}}
        )
    found = _codes(build_designspace(axes=axes, sources=sources), SEGMENT_TURNS_OVER)
    (segment,) = [s for r in found for s in r.raw_data["segments"] if s["point"] == 0]
    assert segment["normalizedLocation"] == pytest.approx({"Weight": 0.5, "Width": 0.5})


def test_the_loop_formula_agrees_with_a_polyline():
    rng = np.random.default_rng(7)
    for _ in range(60):
        p = rng.uniform(-300, 300, (4, 2))
        t = np.linspace(0, 1, 301)[:, None]
        pts = (
            (1 - t) ** 3 * p[0]
            + 3 * (1 - t) ** 2 * t * p[1]
            + 3 * (1 - t) * t * t * p[2]
            + t**3 * p[3]
        )
        a, b = pts[:-1], pts[1:]

        def orient(p, q, r):
            return (q[..., 0] - p[..., 0]) * (r[..., 1] - p[..., 1]) - (q[..., 1] - p[..., 1]) * (
                r[..., 0] - p[..., 0]
            )

        crossing = False
        for i in range(len(a)):
            j = slice(i + 2, len(a))
            if (
                (orient(a[i], b[i], a[j]) * orient(a[i], b[i], b[j]) < 0)
                & (orient(a[j], b[j], a[i]) * orient(a[j], b[j], b[i]) < 0)
            ).any():
                crossing = True
                break
        assert (topology._loop_span(*(q[None] for q in p))[0] > 0) == crossing


def test_inside_a_cell_points_blend_their_corners_exactly():
    from fontTools.varLib.models import VariationModel

    locations = [
        {},
        {"A": 1},
        {"B": 1},
        {"A": 1, "B": 1},
        {"A": 0.4},
        {"B": -1},
        {"A": 0.4, "B": 0.6},
    ]
    model = VariationModel(locations, axisOrder=["A", "B"])
    points = np.random.default_rng(0).uniform(-100, 100, (len(locations), 5, 2))
    masters = topology.GlyphMasters(
        "x",
        tuple(f"m{i}" for i in range(len(locations))),
        model,
        points,
        np.array([4]),
        np.array([topology.TAG_ON] * 5, dtype=np.int8),
        {"A": (0, 0, 1), "B": (-1, 0, 1)},
    )
    sampling = topology.Sampling(masters, None)
    flat = sampling.positions(points).reshape(-1, 5, 2)
    for lower, frac, linear, weight in sampling.groups():
        blended = sum(weight[:, c, None, None] * flat[linear[:, c]] for c in range(linear.shape[1]))
        where = [sampling.location(lo, fr) for lo, fr in zip(lower, frac, strict=True)]
        exact = np.einsum("lm,mpk->lpk", topology.master_scalars_at(model, where), points)
        assert np.abs(blended - exact).max() < 1e-9
