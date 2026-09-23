# Copyright 2024-2026 TypeDev
# Licensed under the Apache License, Version 2.0

"""
Which masters a glyph is allowed to skip, derived from what varLib does.

varLib builds a *per-glyph* model out of the masters that actually have the
glyph (``VariationModel.getSubModel``). A glyph missing from a master between
two others therefore interpolates from its neighbours and nothing is lost --
that is what a sparse master is for.

A glyph missing from a master at the *end* of an axis is a different story. The
glyph's own model stops at its last master, and past that point the variation
scalar falls to zero, so the glyph goes back to the **default master's shape**
while everything around it keeps changing. Measured on a three-master axis
(0 / 0.5 / 1.0 with values 100 / 150 / 300) with the 1.0 master lacking the
glyph: 0.75 gives 125 and 1.0 gives 100, instead of 225 and 300. Nothing warns;
the font builds.

So a glyph has to reach as far along every axis as the designspace itself does.
That is a property of the *span* the glyph covers, not of which master is
"extreme": axes are independent here, exactly as they are in varLib, so a
missing corner master in a two-axis space is fine (the axis deltas simply add)
and is never demanded.

This module is deliberately free of GTK and of font_rover imports: it takes a
fontTools ``DesignSpaceDocument`` and source descriptors and returns plain data.
"""

from dataclasses import dataclass


# Design coordinates are written by hand into a .designspace file, so two
# sources meant to sit at the same end of an axis can differ in the last bits.
DEFAULT_TOLERANCE = 1e-6


@dataclass(frozen=True)
class AxisGap:
    """One end of one axis that a glyph does not reach.

    Attributes:
        axis: Axis name, as the designspace spells it.
        side: ``"minimum"`` or ``"maximum"`` -- which end is not covered.
        required: The design coordinate the designspace's masters reach.
        covered: The design coordinate the glyph's masters reach.
    """

    axis: str
    side: str
    required: float
    covered: float


def continuous_axes(doc) -> list:
    """Axes that interpolate.

    A discrete axis does not interpolate at all: fontTools splits the
    designspace on it and each slice has its own default and its own extremes.
    Callers run per slice, so discrete axes are not this module's business.
    """
    return [axis for axis in doc.axes if not getattr(axis, "values", None)]


def design_location(descriptor, doc) -> dict:
    """The source's full location in design coordinates.

    A source may name only the axes it is not default on;
    ``getFullDesignLocation`` fills in the rest, which is also how
    ``findDefault`` reads a document.
    """
    try:
        return descriptor.getFullDesignLocation(doc)
    except Exception:  # pragma: no cover - old descriptors without the method
        return dict(getattr(descriptor, "designLocation", None) or descriptor.location or {})


def axis_span_gaps(doc, all_descriptors, covering_descriptors, tol: float = DEFAULT_TOLERANCE):
    """Ends of axes the covering sources fail to reach.

    Args:
        doc: The DesignSpaceDocument (one discrete slice of it, if it has
            discrete axes).
        all_descriptors: Every source descriptor of that slice.
        covering_descriptors: Those that have the glyph.
        tol: How close two design coordinates count as the same end.

    Returns:
        One AxisGap per unreached end. Empty when the glyph spans the space,
        which includes the case of a glyph missing only from masters in the
        middle.
    """
    if not covering_descriptors:
        return []

    gaps: list[AxisGap] = []
    all_locations = [design_location(d, doc) for d in all_descriptors]
    covering_locations = [design_location(d, doc) for d in covering_descriptors]

    for axis in continuous_axes(doc):
        name = axis.name
        full = [loc[name] for loc in all_locations if name in loc]
        covered = [loc[name] for loc in covering_locations if name in loc]
        if not full or not covered:
            continue

        # The glyph has to *vary* on this axis for a gap to mean anything.
        # When all its masters sit at one coordinate, the glyph carries no
        # delta along the axis and simply stays as it is -- there is nothing
        # to fade out and nothing to revert to. It is the glyph that varies
        # and then stops short whose deltas ramp back down to zero, taking it
        # to the default master's shape.
        #
        # This is also what makes the check usable on a parametric family.
        # Amstelvar's italic designspace has 91 axes, one per master, and each
        # master redraws only the glyphs it needs; reading every untouched
        # glyph as a gap produced 18609 findings that all meant "this master
        # does not change this glyph", which is the entire point of the
        # arrangement.
        if max(covered) - min(covered) <= tol:
            continue

        if min(covered) > min(full) + tol:
            gaps.append(AxisGap(name, "minimum", min(full), min(covered)))
        if max(covered) < max(full) - tol:
            gaps.append(AxisGap(name, "maximum", max(full), max(covered)))

    return gaps
