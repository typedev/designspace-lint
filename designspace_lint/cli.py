# Copyright 2024-2026 TypeDev
# Licensed under the Apache License, Version 2.0

"""
`designspace-lint` on the command line.

Exit codes are the point of it: 0 when the designspace is clean, 1 when there
are problems, 2 when the file could not be read at all. A build script can
therefore gate on it without parsing anything, while a person gets one line per
problem and `--json` when a machine wants the details.
"""

from __future__ import annotations

import argparse
import json
import sys

from .model import CATEGORY_NAMES, SEVERITY_DESIGN, SEVERITY_STRUCTURAL

SEVERITY_LABEL = {SEVERITY_STRUCTURAL: "error", SEVERITY_DESIGN: "warn"}


def _severity(problem) -> int:
    """Same rule the application shows: structural, design, or information."""
    from .model import (
        CATEGORY_FONTINFO,
        CATEGORY_GLYPHORDER,
        CATEGORY_GLYPHS,
        CATEGORY_KERNING,
        SEVERITY_INFO,
    )

    if problem.severity is not None:
        return problem.severity
    if problem.is_structural:
        return SEVERITY_STRUCTURAL
    if problem.category in (
        CATEGORY_GLYPHS,
        CATEGORY_KERNING,
        CATEGORY_FONTINFO,
        CATEGORY_GLYPHORDER,
    ):
        return SEVERITY_DESIGN
    return SEVERITY_INFO


def _as_dict(problem) -> dict:
    return {
        "severity": SEVERITY_LABEL.get(_severity(problem), "info"),
        "category": CATEGORY_NAMES.get(problem.category, str(problem.category)),
        "code": f"{problem.category}.{problem.code}",
        "description": problem.description,
        "location": problem.location,
        "glyph": problem.glyph_name,
        "details": problem.details,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="designspace-lint",
        description="Report what a designspace will do when it is built.",
    )
    parser.add_argument("path", help="Path to a .designspace file")
    parser.add_argument("-v", "--verbose", action="store_true", help="Include details")
    parser.add_argument("-q", "--quiet", action="store_true", help="Print only the tally")
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    args = parser.parse_args(argv)

    from . import lint_path

    try:
        problems = lint_path(args.path)
    except FileNotFoundError as exc:
        print(f"designspace-lint: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # a malformed document, an unreadable UFO
        print(f"designspace-lint: cannot read {args.path}: {exc}", file=sys.stderr)
        return 2

    if args.json:
        json.dump([_as_dict(p) for p in problems], sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 1 if problems else 0

    if not args.quiet:
        for problem in problems:
            label = SEVERITY_LABEL.get(_severity(problem), "info")
            where = f" {problem.location}" if problem.location else ""
            glyph = f" /{problem.glyph_name}" if problem.glyph_name else ""
            print(f"{label} {problem.category}.{problem.code}{glyph}{where}: {problem.description}")
            if args.verbose and problem.details:
                print(f"    {problem.details}")

    structural = sum(1 for p in problems if _severity(p) == SEVERITY_STRUCTURAL)
    if problems:
        print(f"{len(problems)} problem(s), {structural} structural", file=sys.stderr)
    else:
        print("no problems found", file=sys.stderr)

    return 1 if problems else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
