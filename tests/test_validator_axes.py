# Copyright 2026 Alexander Lubovenko
# Licensed under the Apache License, Version 2.0

"""
Axis checks that follow what varLib does with the axes and their mappings.

Each rule was checked against fontTools 4.65 (see
`docs/audit/2026-09-coverage/VERIFICATION.md`): a map without the default is a
build error, a discrete default outside its values drops the default masters
from every slice, and an avar2 mapping from the default location is discarded
while every other mapping shifts.
"""

from designspace_lint.checkers.axes import (
    AVAR2_MAPPING_FROM_DEFAULT,
    AXIS_MAP_NO_DEFAULT,
    DISCRETE_DEFAULT_NOT_IN_VALUES,
    NO_AXES,
    NO_CONTINUOUS_AXIS,
    VF_RANGE_ON_DISCRETE_AXIS,
    VF_SUBSET_SELECTS_NOTHING,
    VF_UNKNOWN_AXIS,
    VF_ZERO_DEFAULT_IGNORED,
    AxesChecker,
)
from designspace_lint.model import SEVERITY_STRUCTURAL
from dsxml import ITALIC, WEIGHT, ds


def _results(doc):
    return list(AxesChecker(doc=doc).check())


def _codes(doc):
    return [r.code for r in _results(doc)]


def test_a_map_without_the_default_is_reported():
    """AXIS-04: varLib refuses "there must be a mapping for the axis default"."""
    axis = (
        '<axis tag="wght" name="Weight" minimum="100" default="400" maximum="900">'
        '<map input="100" output="20"/><map input="900" output="200"/></axis>'
    )
    results = [r for r in _results(ds(axis)) if r.code == AXIS_MAP_NO_DEFAULT]

    assert len(results) == 1
    assert results[0].severity == SEVERITY_STRUCTURAL
    assert "400" in results[0].description


def test_a_map_through_the_default_is_fine():
    axis = (
        '<axis tag="wght" name="Weight" minimum="100" default="400" maximum="900">'
        '<map input="100" output="20"/><map input="400" output="80"/>'
        '<map input="900" output="200"/></axis>'
    )
    assert _codes(ds(axis)) == []


def test_discrete_axes_are_checked_without_a_range():
    """A discrete axis has no minimum or maximum; asking for one used to raise."""
    assert _codes(ds(WEIGHT + ITALIC)) == []


def test_a_discrete_default_outside_its_values_is_reported():
    """AXIS-13 / DISC-06: splitInterpolable builds slices from the values only."""
    axis = '<axis tag="ital" name="Italic" values="0 1" default="0.5"/>'
    results = _results(ds(WEIGHT + axis))

    assert [r.code for r in results] == [DISCRETE_DEFAULT_NOT_IN_VALUES]
    assert results[0].severity == SEVERITY_STRUCTURAL


def test_a_document_with_only_discrete_axes_has_nothing_to_interpolate():
    """Reported once, on the document -- not as "no axes" once per slice."""
    codes = _codes(ds(ITALIC))

    assert codes == [NO_CONTINUOUS_AXIS]
    assert NO_AXES not in codes


def _mapping(inputs, outputs):
    def dims(loc):
        return "".join(f'<dimension name="{k}" xvalue="{v}"/>' for k, v in loc.items())

    return f"<mapping><input>{dims(inputs)}</input><output>{dims(outputs)}</output></mapping>"


WIDTH = '<axis tag="wdth" name="Width" minimum="50" default="100" maximum="200"/>'


def _avar2(*mappings):
    return ds(WEIGHT + WIDTH, mappings="<mappings>" + "".join(mappings) + "</mappings>")


def test_an_avar2_mapping_from_the_default_is_reported():
    """AVAR2-01: varLib keeps it only as the discarded base of its VarStore.

    Built with wght 100/400/900: `900 -> 700` alone maps normalized 1.0 to
    0.6; adding `400 -> 650` leaves the default where it was and brings 1.0
    down to 0.1.
    """
    doc = _avar2(
        _mapping({"Weight": 400}, {"Weight": 650}),
        _mapping({"Weight": 900}, {"Weight": 700}),
    )
    results = [r for r in _results(doc) if r.code == AVAR2_MAPPING_FROM_DEFAULT]

    assert len(results) == 1
    assert results[0].location == "mapping 1"
    assert "Weight 400 -> 650" in results[0].description


def test_an_input_that_omits_every_axis_is_at_the_default_too():
    doc = _avar2(_mapping({}, {"Width": 120}))
    assert AVAR2_MAPPING_FROM_DEFAULT in _codes(doc)


def test_a_default_mapping_that_moves_nothing_is_harmless():
    doc = _avar2(
        _mapping({"Weight": 400}, {"Weight": 400, "Width": 100}),
        _mapping({"Weight": 900}, {"Width": 150}),
    )
    assert AVAR2_MAPPING_FROM_DEFAULT not in _codes(doc)


# --- <variable-fonts> -------------------------------------------------------


def _vf(name, *subsets):
    return f'<variable-font name="{name}"><axis-subsets>{"".join(subsets)}</axis-subsets></variable-font>'


def _range(axis, lo=None, default=None, hi=None):
    if lo is None:
        return f'<axis-subset name="{axis}"/>'
    return (
        f'<axis-subset name="{axis}" userminimum="{lo}" userdefault="{default}" '
        f'usermaximum="{hi}"/>'
    )


def _value(axis, value):
    return f'<axis-subset name="{axis}" uservalue="{value}"/>'


def _vf_codes(*fonts, axes=WEIGHT + ITALIC):
    return [r.code for r in _results(ds(axes, variable_fonts="".join(fonts)))]


def test_well_formed_variable_fonts_are_fine():
    assert _vf_codes(_vf("Upright", _range("Weight"), _value("Italic", 0))) == []


def test_no_variable_fonts_element_is_fine():
    """fontTools derives the fonts itself then; nothing to check."""
    assert _results(ds(WEIGHT + ITALIC)) == []


def test_a_subset_on_an_unknown_axis_is_reported():
    """Splitting raises "Cannot find axis named ..." on it."""
    assert _vf_codes(_vf("A", _range("Wieght"))) == [VF_UNKNOWN_AXIS]


def test_a_range_over_a_discrete_axis_is_reported():
    """Splitting raises "Cannot select a range over ...": use a uservalue."""
    assert _vf_codes(_vf("A", _range("Weight"), _range("Italic"))) == [VF_RANGE_ON_DISCRETE_AXIS]


def test_a_subset_that_selects_nothing_is_reported():
    """The variable font falls out of the split and is never built, silently."""
    codes = _vf_codes(
        _vf("OffValues", _range("Weight"), _value("Italic", 2)),
        _vf("OffRange", _range("Weight", 950, 950, 1000), _value("Italic", 0)),
    )
    assert codes == [VF_SUBSET_SELECTS_NOTHING, VF_SUBSET_SELECTS_NOTHING]


def test_a_zero_userdefault_is_read_as_not_set():
    """`userDefault or axis.default` in getVFUserRegion: 0 falls through."""
    axis = '<axis tag="slnt" name="Slant" minimum="-12" default="-6" maximum="0"/>'
    codes = _vf_codes(_vf("A", _range("Slant", -12, 0, 0)), axes=axis)
    assert codes == [VF_ZERO_DEFAULT_IGNORED]
