# Copyright 2026 Alexander Lubovenko
# Licensed under the Apache License, Version 2.0

"""
The seam that lets the checks leave this repository.

These checks were lifted out of a GTK font editor, and the habits of that
code are easy to bring along — an event constant here, a toolkit enum there.
Any of them would make this package unusable in the build script or the CI job
it exists for. These tests are the boundary: they read the package as text, so
they fail the moment such an import is written, not when somebody installs it.

The AST walk is deliberately stricter than the usual tier check: an import
inside a function, inside `try`, or under `TYPE_CHECKING` counts too. A
forbidden import does not become acceptable by being lazy.
"""

import ast
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parent.parent / "designspace_lint"

# A library of checks must not need a UI toolkit, and must not reach back into
# the application it was extracted from.
FORBIDDEN_ROOTS = {"gi", "gtk", "adw", "font_rover"}


def _python_files():
    return sorted(PACKAGE.rglob("*.py"))


def _imported_roots(tree: ast.AST):
    """Every module root this file imports, however it imports it."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # a relative import stays inside the package
                continue
            if node.module:
                yield node.lineno, node.module.split(".")[0]


def test_the_package_has_files_to_check():
    """A typo in the path would make every other test here vacuously pass."""
    assert len(_python_files()) > 10


@pytest.mark.parametrize("path", _python_files(), ids=lambda p: p.name)
def test_no_toolkit_and_no_application_imports(path):
    tree = ast.parse(path.read_text(), filename=str(path))

    offenders = [
        f"{path.relative_to(PACKAGE)}:{lineno} imports {root}"
        for lineno, root in _imported_roots(tree)
        if root in FORBIDDEN_ROOTS
    ]

    assert not offenders, "designspace_lint must stand alone: " + "; ".join(offenders)


def test_the_package_imports_without_a_toolkit():
    """Importing it must not drag in gi, even transitively."""
    import subprocess
    import sys

    code = (
        "import sys;"
        "import designspace_lint;"
        "bad = [m for m in sys.modules if m.split('.')[0] in ('gi', 'font_rover')];"
        "print(','.join(bad))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(PACKAGE.parent),
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "", f"importing designspace_lint pulled in: {out.stdout.strip()}"
