# Copyright 2024-2026 TypeDev
# Licensed under the Apache License, Version 2.0

"""
Bringing a designspace's ``features.fea`` files back to a compilable state.

ufo2ft builds one variable feature file out of the default master's features,
but only when every other master's file tokenizes the same as the default's, or
all of them are empty (`featureCompiler._featuresCompatible`). Anything in
between -- including a mix of "identical" and "empty" -- drops the build to
compiling features in each master and merging the results, which is where
varLib raises ``InconsistentGlyphOrder`` or ``ShouldBeConstant``, pointing at
something that is not the cause.

Both compatible states are reachable mechanically, and which one a designer
wants is a real choice:

- ``STRATEGY_CLEAR`` leaves the features with the default master alone. The
  other masters lose their copy, which is usually a stale duplicate.
- ``STRATEGY_COPY`` gives every master the default's text. Nothing is lost,
  but the same file now lives in every UFO.

The planning is kept here, apart from the dialog, so that it can be tested
without a display and read without GTK in the way.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

STRATEGY_CLEAR = "clear"  # features only in the default master
STRATEGY_COPY = "copy"  # the same features in every master

# `include(path);` -- feaLib allows whitespace around the path and the
# semicolon is optional at end of file.
_INCLUDE_RE = re.compile(r"include\s*\(\s*([^)]+?)\s*\)", re.IGNORECASE)


@dataclass(frozen=True)
class FeaturePlan:
    """What a feature sync would write, before anything is written.

    Attributes:
        writes: UFO path -> new features text, only where it actually changes.
        default_path: The master whose features the build will use.
        seeded_from: Where the default's text came from, when the default had
            none of its own and a reference master was picked.
        cleared: Masters whose features text is emptied.
        copied: Masters that receive the default's text.
        skipped_layers: Layer sources left alone -- a layer shares its parent
            UFO's features, so writing "its" features would write the parent's.
    """

    writes: dict[Path, str] = field(default_factory=dict)
    default_path: Path | None = None
    seeded_from: Path | None = None
    cleared: list[Path] = field(default_factory=list)
    copied: list[Path] = field(default_factory=list)
    skipped_layers: list[Path] = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.writes)


def relative_includes(text: str) -> list[str]:
    """The relative paths a features file includes, in order.

    An absolute include resolves the same wherever the file is copied; a
    relative one is resolved against the UFO that holds it, so copying the text
    into a UFO in another directory silently breaks it.
    """
    found = []
    for raw in _INCLUDE_RE.findall(text or ""):
        path = raw.strip().strip("\"'")
        if path and not Path(path).is_absolute():
            found.append(path)
    return found


def features_text(source) -> str:
    """A master's features text, tolerating a font object without one."""
    features = getattr(source.font, "features", None)
    return (getattr(features, "text", None) or "") if features is not None else ""


def _is_layer(source) -> bool:
    if hasattr(source, "master_layer_name"):
        return bool(source.master_layer_name())
    return bool(getattr(source, "layerName", None))


def ufo_sources(sources) -> list:
    """One source per UFO: layer masters share their parent's features."""
    seen: set[Path] = set()
    out = []
    for source in sources:
        if _is_layer(source):
            continue
        key = Path(str(source.path)).resolve()
        if key in seen:
            continue
        seen.add(key)
        out.append(source)
    return out


def plan_feature_sync(sources, default_source, strategy: str, seed_source=None) -> FeaturePlan:
    """Work out which masters get which features text.

    Args:
        sources: The masters of one interpolable slice.
        default_source: The master the build takes features from.
        strategy: ``STRATEGY_CLEAR`` or ``STRATEGY_COPY``.
        seed_source: Where to take the default's text from when the default has
            none. Ignored when the default already has features.

    Returns:
        A FeaturePlan. Empty (falsy) when nothing needs writing.
    """
    if default_source is None:
        return FeaturePlan()

    skipped = [Path(str(s.path)).resolve() for s in sources if _is_layer(s)]
    masters = ufo_sources(sources)
    default_path = Path(str(default_source.path)).resolve()

    writes: dict[Path, str] = {}
    cleared: list[Path] = []
    copied: list[Path] = []

    default_text = features_text(default_source)
    seeded_from = None
    if not default_text.strip() and seed_source is not None:
        default_text = features_text(seed_source)
        if default_text.strip():
            seeded_from = Path(str(seed_source.path)).resolve()
            writes[default_path] = default_text

    target = "" if strategy == STRATEGY_CLEAR else default_text

    for source in masters:
        path = Path(str(source.path)).resolve()
        if path == default_path:
            continue
        current = features_text(source)
        if current == target:
            continue
        writes[path] = target
        (cleared if target == "" else copied).append(path)

    return FeaturePlan(
        writes=writes,
        default_path=default_path,
        seeded_from=seeded_from,
        cleared=cleared,
        copied=copied,
        skipped_layers=skipped,
    )


def broken_includes(plan: FeaturePlan) -> list[Path]:
    """Masters that would receive a relative include from another directory.

    Copying the default's text into a UFO that does not sit beside it leaves
    the include pointing at nothing -- feaLib fails at compile time, long after
    this fix ran.
    """
    if plan.default_path is None:
        return []
    default_dir = plan.default_path.parent
    at_risk = []
    for path, text in plan.writes.items():
        if path == plan.default_path or not text.strip():
            continue
        if relative_includes(text) and path.parent != default_dir:
            at_risk.append(path)
    return at_risk
