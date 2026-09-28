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
from designspace_lint.checkers.avar2 import (
    AVAR2_CHAINED,
    AVAR2_DUPLICATE_INPUT,
    AVAR2_PAST_THE_MASTERS,
    AVAR2_UNDRIVEN_HIDDEN_AXIS,
    AVAR2_UNKNOWN_AXIS,
    AVAR2_VALUE_CLAMPED,
)
from designspace_lint.model import SEVERITY_STRUCTURAL
from dsxml import ITALIC, WEIGHT, ds, source


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


# --- avar2 mappings, 1.23-1.28 ------------------------------------------------

HIDDEN = '<axis tag="XHID" name="Hid" minimum="0" default="0" maximum="100" hidden="1"/>'


WIDE_AND_HIDDEN = source("Default.ufo") + source("Wide.ufo", Width=200) + source("Hid.ufo", Hid=100)


def _avar2_doc(*mappings, sources=None, axes=WEIGHT + WIDTH + HIDDEN):
    if sources is None:
        sources = source("Default.ufo") + source("Hid.ufo", Hid=100)
    return ds(axes, sources, mappings="<mappings>" + "".join(mappings) + "</mappings>")


def _avar2_codes(*mappings, **kwargs):
    return [r.code for r in _results(_avar2_doc(*mappings, **kwargs)) if 23 <= r.code <= 28]


def test_a_clean_avar2_document_has_nothing_to_report():
    assert _avar2_codes(_mapping({"Weight": 900}, {"Hid": 100})) == []


def test_two_mappings_with_one_input_stop_the_build():
    """VariationModel: "Locations must be unique." -- after zeros drop out."""
    for first, second in (
        ({"Weight": 900}, {"Weight": 900}),
        ({"Weight": 900}, {"Weight": 900, "Hid": 0}),
        ({"Weight": 900}, {"Weight": 1200}),  # clamped to the end first
        ({"Weight": 400}, {"Width": 100}),  # both are the default location
    ):
        codes = _avar2_codes(_mapping(first, {"Hid": 10}), _mapping(second, {"Hid": 20}))
        assert codes.count(AVAR2_DUPLICATE_INPUT) == 1, (first, second)


def test_a_mapping_naming_an_axis_the_font_does_not_have_is_dropped():
    results = [
        r
        for r in _results(
            _avar2_doc(
                _mapping({"wght": 900}, {"Hid": 50}),  # a tag, not a name
                _mapping({"Weight": 900}, {"Nope": 5}),
            )
        )
        if r.code == AVAR2_UNKNOWN_AXIS
    ]
    assert [r.raw_data["axisName"] for r in results] == ["wght", "Nope"]
    assert "did you mean Weight" in results[0].details


def test_a_value_past_the_axis_end_is_clamped_once_per_mapping():
    results = [
        r
        for r in _results(_avar2_doc(_mapping({"Weight": 900}, {"Hid": 500, "Width": 20})))
        if r.code == AVAR2_VALUE_CLAMPED
    ]
    assert len(results) == 1
    assert len(results[0].raw_data["clamped"]) == 2


def test_an_output_past_the_outermost_master_is_reported():
    """Masters reach Hid 50 only: an output of 100 tapers back toward the default."""
    codes = _avar2_codes(
        _mapping({"Weight": 900}, {"Hid": 100}),
        sources=source("Default.ufo") + source("Hid.ufo", Hid=50),
    )
    assert codes == [AVAR2_PAST_THE_MASTERS]


def test_a_chain_of_mappings_is_reported():
    """Deltas are evaluated before avar2 applies, so Width never feeds the second."""
    codes = _avar2_codes(
        _mapping({"Weight": 900}, {"Width": 150}),
        _mapping({"Width": 150}, {"Hid": 50}),
        sources=WIDE_AND_HIDDEN,
    )
    assert codes == [AVAR2_CHAINED]


def test_a_hidden_axis_no_mapping_touches_is_noted():
    codes = _avar2_codes(_mapping({"Weight": 900}, {"Width": 150}), sources=WIDE_AND_HIDDEN)
    assert codes == [AVAR2_UNDRIVEN_HIDDEN_AXIS]
