# Copyright 2024-2026 TypeDev
# Licensed under the Apache License, Version 2.0

"""
designspace-lint — what a designspace will do when it is built.

The checks here are not opinions about style. Each one describes something
fontTools, varLib or ufo2ft actually does with a designspace, usually without
saying so: a glyph missing from the master at the end of an axis reverts to the
default's shape past that point; an avar2 mapping written at the default is
discarded and every other mapping shifts; a `features.fea` that differs from
the default's pushes the whole build onto a path where varLib fails somewhere
else entirely.
Each result names the consequence, not just the discrepancy.

Two ways in::

    from designspace_lint import lint_path
    for problem in lint_path("Family.designspace"):
        print(problem.category, problem.code, problem.description)

or, when the fonts are already open (a font editor, a build script)::

    from designspace_lint import lint
    problems = lint(my_designspace)   # anything matching DesignSpaceLike

The `(category, code)` pairs are a **public contract**: other projects key on
them, so a retired check keeps its number and new checks only get new ones.
"""

from __future__ import annotations

from .axis_span import AxisGap, axis_span_gaps
from .engine import PHASES, Linter
from .loader import DesignSpace, Source, open_designspace
from .model import (
    CATEGORY_FEATURES,
    CATEGORY_FILE,
    CATEGORY_FONTINFO,
    CATEGORY_GEOMETRY,
    CATEGORY_GLYPHORDER,
    CATEGORY_GLYPHS,
    CATEGORY_INSTANCES,
    CATEGORY_KERNING,
    CATEGORY_LABELS,
    CATEGORY_NAMES,
    CATEGORY_RULES,
    CATEGORY_SOURCES,
    SEVERITY_DESIGN,
    SEVERITY_INFO,
    SEVERITY_STRUCTURAL,
    AnchorDifference,
    CheckResult,
    ContourDifference,
    GlyphProblemType,
    PointDifference,
    SourceInfo,
    StartPointDifference,
)
from .checkers.base import label_for_source
from .codes import CODES, CodeInfo, code_info
from .glyph_order import dedupe_glyph_order, raw_glyph_order
from .model import effective_severity
from .protocols import DesignSpaceLike, SourceLike
from .raw_xml import (
    StrayDimension,
    undeclared_axis_dimensions,
    undeclared_axis_dimensions_from_string,
)

__version__ = "0.6.0"

#: A problem found in a designspace. The name the checks use internally is
#: `CheckResult`; this is the same class, named for the reader.
Problem = CheckResult


def iter_lint(
    designspace,
    *,
    on_phase=None,
    on_progress=None,
    cancel=None,
    interpolatable=False,
    phases=None,
    glyphs=None,
):
    """Yield problems one at a time, as they are found.

    Args:
        designspace: Anything satisfying :class:`DesignSpaceLike` — fonts open.
        on_phase: ``(phase_name, current, total)``, called as each phase starts.
        on_progress: ``(current, total, message)`` for finer-grained progress.
        cancel: Anything with ``is_set()``; polled so a caller running this in
            a thread can stop it.
        interpolatable: also compare the masters point by point with
            fontTools' ``varLib.interpolatable`` (4.14-4.18). Slower; install
            ``designspace-lint[interpolatable]`` for glyphs of 7+ contours.
        phases: run only these phases (ids from :data:`PHASES`); "file" and
            "geometry" always run.
        glyphs: check only these glyphs in the glyph phases.

    Yields:
        :class:`CheckResult`, in phase order.
    """
    linter = Linter(
        designspace=designspace,
        cancel=cancel,
        interpolatable=interpolatable,
        phases=phases,
        glyphs=glyphs,
    )
    yield from linter.run(on_phase=on_phase, on_progress=on_progress)


def lint(
    designspace,
    *,
    on_phase=None,
    on_progress=None,
    cancel=None,
    interpolatable=False,
    phases=None,
    glyphs=None,
) -> list[CheckResult]:
    """Every problem in a designspace whose fonts are already open."""
    return list(
        iter_lint(
            designspace,
            on_phase=on_phase,
            on_progress=on_progress,
            cancel=cancel,
            interpolatable=interpolatable,
            phases=phases,
            glyphs=glyphs,
        )
    )


def lint_path(
    path,
    *,
    on_phase=None,
    on_progress=None,
    cancel=None,
    interpolatable=False,
    phases=None,
    glyphs=None,
) -> list[CheckResult]:
    """Open a .designspace file and check it.

    Raises:
        FileNotFoundError: the designspace file does not exist.
    """
    return lint(
        open_designspace(path),
        on_phase=on_phase,
        on_progress=on_progress,
        cancel=cancel,
        interpolatable=interpolatable,
        phases=phases,
        glyphs=glyphs,
    )


__all__ = [
    "__version__",
    # Entry points
    "lint",
    "lint_path",
    "iter_lint",
    "Linter",
    "open_designspace",
    "PHASES",
    # Input types
    "DesignSpace",
    "Source",
    "DesignSpaceLike",
    "SourceLike",
    # Results
    "Problem",
    "CheckResult",
    "GlyphProblemType",
    "SourceInfo",
    "PointDifference",
    "ContourDifference",
    "StartPointDifference",
    "AnchorDifference",
    "AxisGap",
    "axis_span_gaps",
    # For consumers
    "CODES",
    "CodeInfo",
    "code_info",
    "effective_severity",
    "label_for_source",
    "raw_glyph_order",
    "dedupe_glyph_order",
    "undeclared_axis_dimensions",
    "undeclared_axis_dimensions_from_string",
    "StrayDimension",
    # Vocabulary
    "CATEGORY_FILE",
    "CATEGORY_GEOMETRY",
    "CATEGORY_SOURCES",
    "CATEGORY_INSTANCES",
    "CATEGORY_GLYPHS",
    "CATEGORY_KERNING",
    "CATEGORY_FONTINFO",
    "CATEGORY_RULES",
    "CATEGORY_FEATURES",
    "CATEGORY_GLYPHORDER",
    "CATEGORY_LABELS",
    "CATEGORY_NAMES",
    "SEVERITY_STRUCTURAL",
    "SEVERITY_DESIGN",
    "SEVERITY_INFO",
]
