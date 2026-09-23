# Copyright 2024-2026 TypeDev
# Licensed under the Apache License, Version 2.0

"""
designspace-lint — what a designspace will do when it is built.

The checks here are not opinions about style. Each one describes something
fontTools, varLib or ufo2ft actually does with a designspace, usually without
saying so: a glyph missing from the master at the end of an axis reverts to the
default's shape past that point; a master with no kerning drags the family's
kerning toward zero around it; a `features.fea` that differs from the default's
pushes the whole build onto a path where varLib fails somewhere else entirely.
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
from .protocols import DesignSpaceLike, SourceLike

__version__ = "0.1.1"

#: A problem found in a designspace. The name the checks use internally is
#: `CheckResult`; this is the same class, named for the reader.
Problem = CheckResult


def iter_lint(designspace, *, on_phase=None, on_progress=None, cancel=None):
    """Yield problems one at a time, as they are found.

    Args:
        designspace: Anything satisfying :class:`DesignSpaceLike` — fonts open.
        on_phase: ``(phase_name, current, total)``, called as each phase starts.
        on_progress: ``(current, total, message)`` for finer-grained progress.
        cancel: Anything with ``is_set()``; polled so a caller running this in
            a thread can stop it.

    Yields:
        :class:`CheckResult`, in phase order.
    """
    linter = Linter(designspace=designspace, cancel=cancel)
    yield from linter.run(on_phase=on_phase, on_progress=on_progress)


def lint(designspace, *, on_phase=None, on_progress=None, cancel=None) -> list[CheckResult]:
    """Every problem in a designspace whose fonts are already open."""
    return list(iter_lint(designspace, on_phase=on_phase, on_progress=on_progress, cancel=cancel))


def lint_path(path, *, on_phase=None, on_progress=None, cancel=None) -> list[CheckResult]:
    """Open a .designspace file and check it.

    Raises:
        FileNotFoundError: the designspace file does not exist.
    """
    return lint(open_designspace(path), on_phase=on_phase, on_progress=on_progress, cancel=cancel)


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
    "CATEGORY_NAMES",
    "SEVERITY_STRUCTURAL",
    "SEVERITY_DESIGN",
    "SEVERITY_INFO",
]
