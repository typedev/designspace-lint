# Copyright 2024-2026 TypeDev
# Licensed under the Apache License, Version 2.0

"""
What the checks need a designspace and its masters to look like.

This is the seam. A caller that already has its fonts open -- a font editor,
a build script -- passes its own objects straight in, and the checks never
know the difference; a caller with only a path gets the concrete `DesignSpace`
that :mod:`designspace_lint.loader` builds. Both satisfy the protocols below,
which spell out exactly the surface the checkers touch and nothing more.

`SourceLike` is deliberately layer-aware. In a layer-based designspace several
masters share one UFO and are told apart by their layer alone, so "the glyph
this master draws" is not "the glyph in this UFO" -- reading the latter makes
one master answer with another's outline. `own_glyph()` is the accessor that
never falls back.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class SourceLike(Protocol):
    """One master: a UFO, or one layer of a UFO."""

    #: The opened font (fontParts RFont, or anything with the same surface).
    font: Any
    #: Path to the UFO on disk.
    path: Path
    #: The name the designspace gives this source.
    name: str | None
    #: Design-space location, axis name -> value.
    location: dict[str, float]
    #: Layer this master is, or None when it is the UFO's default layer.
    layer_name: str | None

    def master_layer_name(self) -> str | None:
        """The layer this master *is*; None means the UFO's default layer."""
        ...

    def resolve_layer_name(self, layer_name: str | None) -> str | None:
        """Normalize a layer name, collapsing both spellings of the default."""
        ...

    def own_glyph(self, name: str) -> Any:
        """The glyph this master draws, or None -- never another layer's."""
        ...

    def get_layer(self) -> Any:
        """The layer object this master draws from."""
        ...


@runtime_checkable
class DesignSpaceLike(Protocol):
    """A designspace document with its masters opened."""

    #: Path to the .designspace file.
    path: Path
    #: The fontTools DesignSpaceDocument.
    doc: Any
    #: The masters, in document order.
    sources: list


__all__ = ["SourceLike", "DesignSpaceLike"]
