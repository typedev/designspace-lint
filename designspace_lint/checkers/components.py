# Copyright 2026 Alexander Lubovenko
# Licensed under the Apache License, Version 2.0

"""
The component graph of one master, and its open contours.

Codes (category 4):
- 4.24: glyphs that use each other as components, or one that uses itself
- 4.25: a component whose base glyph the build cannot find
- 4.26: an open contour

Built with ufo2ft 3.9 (static TTF and OTF, variable TTF and CFF2):

- A ring stops every build with RecursionError, whichever master has it: the
  default, another, or a layer master. Every tool that decomposes or measures
  the composite recurses without end.
- A component whose base is not in the master stops a CFF or CFF2 build
  (MissingComponentError). A TrueType build drops the component with only a
  log line ("skipped non-existing component"), so the glyph ships without it;
  if other masters have that component, varLib then drops the glyph's
  variations too ("incompatible masters; skipping"). A base that a non-default
  master lacks but the default master has is not missing: the build treats it
  as sparse there, and it interpolates from the masters that have it.
- An open contour is closed by every build with a straight line from its last
  point to its first, so the glyph ships different from the drawing. (Open in
  some masters only, the point structure differs too: 4.5 reports that, and
  the variable TrueType build stops on it.)

`component_findings` works on a single layer and is public, so a host that
checks a standalone UFO runs the same rules the designspace run does.
"""

from __future__ import annotations

from typing import Any, Iterable, Iterator

from ..model import CATEGORY_GLYPHS, SEVERITY_DESIGN, SEVERITY_STRUCTURAL, CheckResult
from .base import BaseChecker
from .unicodes import _naked

COMPONENT_RING = 24  # glyphs that use each other as components
MISSING_COMPONENT_BASE = 25  # a component's base is in no master the build reads it from
OPEN_CONTOUR = 26  # a contour that is not closed


def component_graph(layer: Any) -> dict[str, list[str]]:
    """Glyph name -> the base glyphs of its components, for every composite.

    defcon reads this from the glif files without loading a glyph
    (`componentReferences`); any other layer is read glyph by glyph.
    """
    references = getattr(_naked(layer), "componentReferences", None)
    if references is not None:
        graph: dict[str, list[str]] = {}
        try:
            for base, users in references.items():
                for user in users:
                    graph.setdefault(user, []).append(base)
        except Exception:  # pragma: no cover - defensive, fall through to the glyphs
            graph = None
        if graph is not None:
            return {name: sorted(set(bases)) for name, bases in graph.items()}
    graph = {}
    for glyph in layer:
        bases = [c.baseGlyph for c in getattr(glyph, "components", None) or ()]
        if bases:
            graph[glyph.name] = sorted(set(bases))
    return graph


def component_rings(
    graph: dict[str, list[str]], start: Iterable[str] | None = None
) -> list[list[str]]:
    """The rings in a component graph, each as its sorted glyph names.

    A ring is a set of glyphs each reachable from the others through their
    components (a strongly connected component of more than one glyph), or a
    glyph among its own components. `start` limits the search to what those
    glyphs reach. Tarjan's algorithm, iterative, so a long chain of nested
    composites cannot hit the recursion limit.
    """
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    rings: list[list[str]] = []
    counter = 0

    roots = sorted(graph) if start is None else sorted(set(start))
    for root in roots:
        if root in index:
            continue
        work = [(root, iter(graph.get(root, ())))]
        index[root] = low[root] = counter
        counter += 1
        stack.append(root)
        on_stack.add(root)
        while work:
            node, children = work[-1]
            advanced = False
            for child in children:
                if child not in index:
                    index[child] = low[child] = counter
                    counter += 1
                    stack.append(child)
                    on_stack.add(child)
                    work.append((child, iter(graph.get(child, ()))))
                    advanced = True
                    break
                if child in on_stack:
                    low[node] = min(low[node], index[child])
            if advanced:
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
            if low[node] == index[node]:
                members = []
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    members.append(member)
                    if member == node:
                        break
                if len(members) > 1 or node in graph.get(node, ()):
                    rings.append(sorted(members))
    return sorted(rings)


def reaching_rings(graph: dict[str, list[str]], rings: list[list[str]]) -> set[str]:
    """Every glyph whose components lead into a ring, the ring's own included.

    Such a glyph cannot be decomposed or measured, so the checks that draw
    composites leave it to 4.24.
    """
    users: dict[str, set[str]] = {}
    for name, bases in graph.items():
        for base in bases:
            users.setdefault(base, set()).add(name)
    found = {member for ring in rings for member in ring}
    queue = list(found)
    while queue:
        for user in users.get(queue.pop(), ()):
            if user not in found:
                found.add(user)
                queue.append(user)
    return found


def _contours(glyph: Any) -> Iterable[Any]:
    contours = getattr(glyph, "contours", None)
    return contours if contours is not None else glyph  # a defcon glyph iterates its contours


def _is_open(contour: Any) -> bool:
    is_open = getattr(contour, "open", None)
    if is_open is not None and not callable(is_open):
        return bool(is_open)
    points = getattr(contour, "points", None)
    if points is None:
        points = list(contour)
    if not points:
        return False
    first = points[0]
    kind = getattr(first, "type", None) or getattr(first, "segmentType", None)
    return kind == "move"


def open_contour_indices(glyph: Any) -> list[int]:
    """Indexes of the glyph's open contours (those starting with a "move" point)."""
    return [i for i, contour in enumerate(_contours(glyph)) if _is_open(contour)]


class _ComponentResults(BaseChecker):
    """Makes the results, so they carry category 4 like the rest of the phase."""

    CATEGORY = CATEGORY_GLYPHS

    def check(self) -> Iterator[CheckResult]:  # pragma: no cover - not a phase
        return iter(())


def component_findings(
    layer: Any,
    *,
    source_name: str,
    layer_name: str | None = None,
    location: str = "",
    glyphs: Iterable[str] | None = None,
    fallback: Iterable[str] = (),
    build_layer: bool = True,
) -> Iterator[CheckResult]:
    """4.24, 4.25 and 4.26 for one layer.

    Args:
        layer: a fontParts, defcon or similar layer (iterable of glyphs with
            `name`, `components` and `contours`, supporting `in`).
        source_name: the `sourceName` locator.
        layer_name: the `layerName` locator; None for a UFO's default layer.
        location: the human-readable location of the findings.
        glyphs: check only these glyphs, and only the rings they reach. None
            checks everything.
        fallback: glyphs the build takes from elsewhere when this layer lacks
            them. In a designspace, a non-default master's sparse glyphs come
            from the default master, so pass the default master's glyph names;
            for the default master and a standalone UFO, nothing.
        build_layer: whether a build reads this layer. A layer no build reads
            (a background, say) cannot break one: its rings and missing bases
            are reported as warnings, and its open contours not at all, since
            guide strokes there are open on purpose.
    """
    maker = _ComponentResults()
    locators = {"sourceName": source_name, "layerName": layer_name}
    severity = SEVERITY_STRUCTURAL if build_layer else SEVERITY_DESIGN
    wanted = set(glyphs) if glyphs is not None else None
    graph = component_graph(layer)
    present = set(layer.keys()) if hasattr(layer, "keys") else {g.name for g in layer}
    available = present | set(fallback or ())

    start = None if wanted is None else [name for name in wanted if name in graph]
    for ring in component_rings(graph, start):
        ring_set = set(ring)
        links = {name: [b for b in graph.get(name, ()) if b in ring_set] for name in ring}
        shown = ", ".join(f"{name} -> {' + '.join(bases)}" for name, bases in links.items())
        yield maker._make_result(
            code=COMPONENT_RING,
            description=(
                f"'{ring[0]}' uses itself as a component"
                if len(ring) == 1
                else f"{len(ring)} glyphs use each other as components: {', '.join(ring)}"
            ),
            glyph_name=ring[0],
            location=location,
            details=(
                f"Components in a ring ({shown}) never end: every build stops with "
                f"RecursionError, and every tool that decomposes or measures these glyphs "
                f"recurses without end. Remove or decompose one of the components."
            ),
            severity=severity,
            raw_data={"glyphName": ring[0], "glyphNames": ring, "links": links, **locators},
        )

    for name in sorted(graph if wanted is None else wanted & set(graph)):
        missing = [base for base in graph[name] if base not in available]
        if not missing:
            continue
        shown = ", ".join(f"'{base}'" for base in missing)
        yield maker._make_result(
            code=MISSING_COMPONENT_BASE,
            description=f"component of a glyph that is not there: {shown}",
            glyph_name=name,
            location=location,
            details=(
                f"Glyph '{name}' has a component of {shown}, which the build cannot find. "
                f"A CFF or CFF2 build stops (MissingComponentError); a TrueType build drops "
                f"the component with only a log line, so the glyph ships without it."
            ),
            severity=severity,
            raw_data={"glyphName": name, "missingBases": missing, **locators},
        )

    if not build_layer:
        return
    # Read through defcon when there is one: a fontParts glyph lookup lists
    # every name in the layer to test membership, every time.
    source = _naked(layer)
    names = sorted(present if wanted is None else wanted & present)
    for name in names:
        try:
            indices = open_contour_indices(source[name])
        except Exception:  # pragma: no cover - defensive
            continue
        if not indices:
            continue
        which = ", ".join(str(i) for i in indices)
        yield maker._make_result(
            code=OPEN_CONTOUR,
            description=(
                f"contour {which} is open" if len(indices) == 1 else f"contours {which} are open"
            ),
            glyph_name=name,
            location=location,
            details=(
                f"Glyph '{name}': every build closes an open contour with a straight line "
                f"from its last point to its first, so the glyph ships different from the "
                f"drawing. Close the contour where it should end."
            ),
            severity=SEVERITY_DESIGN,
            raw_data={"glyphName": name, "contours": indices, **locators},
        )


__all__ = [
    "COMPONENT_RING",
    "MISSING_COMPONENT_BASE",
    "OPEN_CONTOUR",
    "component_findings",
    "component_graph",
    "component_rings",
    "open_contour_indices",
    "reaching_rings",
]
