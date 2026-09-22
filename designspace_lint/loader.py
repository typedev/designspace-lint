# Copyright 2024-2026 TypeDev
# Licensed under the Apache License, Version 2.0

"""
Opening a designspace when the caller has nothing but a path.

A caller that already holds its fonts -- an editor, a build script -- passes
its own objects and never comes here; this is for the command line and for
anyone who just wants the answer about a file on disk.

The masters are read with fontParts, the same object model the checks are
written against and the one both known consumers already use. A faster, lazier
backend (ufoLib2) is a possible option later, but it would have to be re-tested
against every duck-typed access in the checkers rather than assumed.

Layer-based designspaces are why the fonts are cached by path: several masters
share one UFO there and are told apart by their layer, so opening the file once
per source would give each of them a private copy of the same data.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_LAYER_NAME = "public.default"


@dataclass
class Source:
    """One master of a designspace: a UFO, or one layer of a UFO."""

    font: Any
    path: Path
    name: str | None = None
    location: dict[str, float] = field(default_factory=dict)
    layer_name: str | None = None
    style_name: str | None = None

    def master_layer_name(self) -> str | None:
        """The layer this master *is*; None means the UFO's default layer."""
        return self.layer_name

    def default_layer_name(self) -> str:
        """What this UFO calls its default layer."""
        try:
            return self.font.defaultLayer.name or DEFAULT_LAYER_NAME
        except Exception:  # pragma: no cover - defensive
            return DEFAULT_LAYER_NAME

    def resolve_layer_name(self, layer_name: str | None) -> str | None:
        """Collapse both spellings of the default layer to None."""
        if not layer_name:
            return None
        if layer_name == DEFAULT_LAYER_NAME or layer_name == self.default_layer_name():
            return None
        return layer_name

    def get_layer(self) -> Any:
        """The layer object this master draws from."""
        layer = self.resolve_layer_name(self.layer_name)
        if layer is None:
            return self.font.defaultLayer
        return self.font.getLayer(layer)

    def own_glyph(self, name: str) -> Any:
        """The glyph this master draws, or None -- never another layer's."""
        try:
            layer = self.get_layer()
        except Exception:
            return None
        return layer[name] if name in layer else None

    def get_location_label(self) -> str:
        """Human-readable location, e.g. ``wght:400 wdth:100``."""
        return " ".join(f"{axis}:{value:g}" for axis, value in sorted(self.location.items()))


@dataclass
class DesignSpace:
    """A designspace document with its masters opened."""

    path: Path
    doc: Any
    sources: list[Source] = field(default_factory=list)


def open_designspace(path: str | Path, font_opener=None) -> DesignSpace:
    """Read a .designspace file and open the UFOs it names.

    Args:
        path: Path to the .designspace file.
        font_opener: Optional callable taking a path and returning a font, for
            callers who want another object model or their own cache.

    Returns:
        A DesignSpace whose sources are in document order. Sources whose UFO is
        missing are left out with a warning -- the file and sources checks are
        what report them, from the document itself.

    Raises:
        FileNotFoundError: the designspace file itself does not exist.
    """
    from fontTools.designspaceLib import DesignSpaceDocument

    ds_path = Path(path).resolve()
    if not ds_path.exists():
        raise FileNotFoundError(f"No such designspace: {ds_path}")

    doc = DesignSpaceDocument.fromfile(str(ds_path))

    if font_opener is None:
        from fontParts.world import OpenFont

        def font_opener(ufo_path):  # noqa: F811 - a default, not a redefinition
            return OpenFont(str(ufo_path), showInterface=False)

    cache: dict[Path, Any] = {}
    sources: list[Source] = []

    for descriptor in doc.sources:
        if not descriptor.path:
            logger.warning("Source %r has no path; skipped", descriptor.name)
            continue
        ufo_path = Path(descriptor.path).resolve()
        if ufo_path not in cache:
            if not ufo_path.exists():
                logger.warning("Source UFO not found: %s", ufo_path)
                continue
            try:
                cache[ufo_path] = font_opener(ufo_path)
            except Exception as exc:
                logger.warning("Could not open %s: %s", ufo_path, exc)
                continue
        sources.append(
            Source(
                font=cache[ufo_path],
                path=ufo_path,
                name=descriptor.name,
                location=dict(descriptor.location or {}),
                layer_name=getattr(descriptor, "layerName", None),
                style_name=getattr(descriptor, "styleName", None),
            )
        )

    return DesignSpace(path=ds_path, doc=doc, sources=sources)


__all__ = ["Source", "DesignSpace", "open_designspace"]
