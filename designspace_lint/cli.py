# Copyright 2024-2026 TypeDev
# Licensed under the Apache License, Version 2.0

"""
`designspace-lint` on the command line.

Exit codes are the point of it: 0 when the designspace is clean, 1 when there
are problems, 2 when the file could not be read at all. A build script can
therefore gate on it without parsing anything, while a person gets one line per
problem and `--json` when a machine wants the details: with `raw_data`, the
same data a fixer acts on.
"""

from __future__ import annotations

import argparse
import json
import sys

from .model import CATEGORY_NAMES, SEVERITY_DESIGN, SEVERITY_STRUCTURAL, effective_severity

SEVERITY_LABEL = {SEVERITY_STRUCTURAL: "error", SEVERITY_DESIGN: "warn"}


def _severity(problem) -> int:
    """Same rule the application shows: structural, design, or information."""
    return effective_severity(problem)


def _as_dict(problem) -> dict:
    return {
        "severity": SEVERITY_LABEL.get(_severity(problem), "info"),
        "category": CATEGORY_NAMES.get(problem.category, str(problem.category)),
        "code": f"{problem.category}.{problem.code}",
        "description": problem.description,
        "location": problem.location,
        "glyph": problem.glyph_name,
        "details": problem.details,
        "raw_data": problem.raw_data,
    }


def _jsonable(value):
    """What json cannot write as is: sets as sorted lists, anything else as text."""
    if isinstance(value, (set, frozenset)):
        return sorted(value, key=str)
    return str(value)


def _axes_between(value: str):
    if value == "all":
        return None
    if value == "auto":
        return "auto"
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected a number, all or auto, not {value!r}") from None
    if number < 0:
        raise argparse.ArgumentTypeError("expected a number of axes, 0 or more")
    return number


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="designspace-lint",
        description="Report what a designspace will do when it is built.",
    )
    parser.add_argument("path", help="Path to a .designspace file")
    parser.add_argument("-v", "--verbose", action="store_true", help="Include details")
    parser.add_argument("-q", "--quiet", action="store_true", help="Print only the tally")
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    parser.add_argument(
        "--interpolatable",
        action="store_true",
        help="Also compare masters point by point (slower; start points, contour order)",
    )
    parser.add_argument(
        "--construction",
        action="store_true",
        help="Also check that composites list bases first, then marks bottom up",
    )
    parser.add_argument(
        "--topology",
        action="store_true",
        help="Also sample the outlines between masters for buried points that come out "
        "(slower; needs NumPy)",
    )
    parser.add_argument(
        "--topology-tolerance",
        type=float,
        default=None,
        metavar="UNITS",
        help="Units a buried point may come out and still count as on the edge (default 1)",
    )
    parser.add_argument(
        "--topology-axes-between",
        type=_axes_between,
        default="auto",
        metavar="N|all|auto",
        help="How many axes sit between master values at once in the --topology samples: "
        "all (the whole product), a number, or auto (all while that stays small, 2 above; "
        "the default)",
    )
    args = parser.parse_args(argv)

    from . import lint_path

    try:
        problems = lint_path(
            args.path,
            interpolatable=args.interpolatable,
            construction=args.construction,
            topology=args.topology,
            topology_tolerance=args.topology_tolerance,
            topology_axes_between=args.topology_axes_between,
        )
    except (FileNotFoundError, ImportError) as exc:
        print(f"designspace-lint: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # a malformed document, an unreadable UFO
        print(f"designspace-lint: cannot read {args.path}: {exc}", file=sys.stderr)
        return 2

    if args.json:
        json.dump([_as_dict(p) for p in problems], sys.stdout, indent=2, default=_jsonable)
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
