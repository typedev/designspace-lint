"""
Base class for DesignSpace checkers.

Copyright 2024-2026 TypeDev
Licensed under the Apache License, Version 2.0
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Iterator

from ..model import CheckResult


@lru_cache(maxsize=4096)
def _resolve_cached(raw: str) -> Path:
    """Resolve a path string once. A designspace names few distinct paths."""
    try:
        return Path(raw).resolve()
    except OSError:  # pragma: no cover - defensive
        return Path(raw)


if TYPE_CHECKING:
    from fontTools.designspaceLib import DesignSpaceDocument

    from ..protocols import DesignSpaceLike as DesignSpaceEntry


class BaseChecker(ABC):
    """
    Base class for DesignSpace validation checkers.

    Each checker validates a specific category of problems.
    Checkers produce CheckResult items that are later converted
    to ProblemItem for display.

    Subclasses must define:
    - CATEGORY: int - the category number (0-9)
    - check() -> Iterator[CheckResult]

    Usage:
        checker = SourcesChecker(entry)
        for result in checker.check():
            print(result.description)
    """

    # Subclasses must set this
    CATEGORY: int = -1

    def __init__(
        self,
        entry: "DesignSpaceEntry | None" = None,
        doc: "DesignSpaceDocument | None" = None,
        path: Path | None = None,
    ):
        """
        Initialize checker.

        Can be initialized with either:
        - entry: DesignSpaceEntry (preferred, has loaded fonts)
        - doc: DesignSpaceDocument (for lighter checks without fonts)
        - path: Path to .designspace file (will load doc on demand)

        Args:
            entry: DesignSpaceEntry with loaded fonts
            doc: DesignSpaceDocument
            path: Path to .designspace file
        """
        self._entry = entry
        self._doc = doc
        self._path = path
        self._doc_loaded = False
        self._label_memo: dict[int, str] = {}

    @property
    def entry(self) -> "DesignSpaceEntry | None":
        """Get DesignSpaceEntry if available."""
        return self._entry

    @property
    def doc(self) -> "DesignSpaceDocument":
        """
        Get DesignSpaceDocument.

        Loads from path if not already loaded.
        """
        if self._doc is not None:
            return self._doc

        if self._entry is not None:
            return self._entry.doc

        if self._path is not None and not self._doc_loaded:
            from fontTools.designspaceLib import DesignSpaceDocument

            self._doc = DesignSpaceDocument.fromfile(str(self._path))
            self._doc_loaded = True
            return self._doc

        raise ValueError("No DesignSpaceDocument available")

    @property
    def path(self) -> Path | None:
        """Get path to .designspace file."""
        if self._path is not None:
            return self._path
        if self._entry is not None:
            return self._entry.path
        return None

    @property
    def ds_dir(self) -> Path | None:
        """Get directory containing .designspace file."""
        path = self.path
        if path is not None:
            return path.parent
        return None

    @abstractmethod
    def check(self) -> Iterator[CheckResult]:
        """
        Run validation checks.

        Yields:
            CheckResult for each problem found
        """
        pass

    def _make_result(
        self,
        code: int,
        description: str,
        location: str = "",
        glyph_name: str | None = None,
        group_name: str | None = None,
        details: str = "",
        is_structural: bool = False,
        raw_data: dict | None = None,
        **kwargs,
    ) -> CheckResult:
        """
        Create a CheckResult with this checker's category.

        This is a convenience method to avoid repeating the category.

        Args:
            code: Error code within category
            description: Human-readable problem description
            location: Master name, path, or discrete location
            glyph_name: Affected glyph name (if applicable)
            group_name: Affected kerning group name (if applicable)
            details: Additional details
            is_structural: True if problem prevents designspace usage
            raw_data: Additional data for actions
            **kwargs: Additional fields for CheckResult

        Returns:
            CheckResult instance
        """
        return CheckResult(
            category=self.CATEGORY,
            code=code,
            description=description,
            location=location,
            glyph_name=glyph_name,
            group_name=group_name,
            details=details,
            is_structural=is_structural,
            raw_data=raw_data or {},
            **kwargs,
        )

    def _format_location(
        self, path: str | Path | None = None, discrete_loc: dict | None = None
    ) -> str:
        """
        Format location string for display.

        Args:
            path: Source UFO path
            discrete_loc: Discrete axis location dict

        Returns:
            Formatted location string
        """
        parts = []

        if path:
            parts.append(Path(path).name)

        if discrete_loc:
            loc_str = self._format_discrete_location(discrete_loc)
            if loc_str:
                parts.append(f"[{loc_str}]")

        return " ".join(parts)

    # --- source identity -------------------------------------------------
    #
    # There used to be an _is_sparse_source() here that looked for the
    # substring "sparse" in a source's name. That is a house convention: it
    # means nothing in a designspace somebody else wrote, and it decided real
    # checks. What actually matters is spelled out in two places instead --
    # `axis_span.py` for which masters a glyph may skip, and the layer/path
    # distinction below for which sources carry kerning, features and a glyph
    # order of their own.

    @staticmethod
    def _resolve_path(value) -> Path | None:
        """Resolve a path from a descriptor or a FontSource, if it has one.

        Cached: resolving hits the filesystem (``lstat`` per path segment), and
        a checker asks about the same handful of source paths over and over.
        """
        if value is None:
            return None
        return _resolve_cached(str(value))

    @classmethod
    def _match_source(cls, descriptor, sources):
        """The loaded FontSource a designspace source descriptor stands for.

        In a layer-based designspace several masters share one UFO path and
        differ only by layer, so a path-only match hands back an arbitrary one
        of them.
        """
        wanted_path = cls._resolve_path(getattr(descriptor, "path", None))
        if wanted_path is None:
            return None
        same_path = [s for s in sources if cls._resolve_path(s.path) == wanted_path]
        if len(same_path) <= 1:
            return same_path[0] if same_path else None

        layer = getattr(descriptor, "layerName", None)
        for source in same_path:
            if source.resolve_layer_name(layer) == source.master_layer_name():
                return source
        return same_path[0]

    def _default_font_source(self, doc=None, sources=None):
        """The FontSource the document calls default, layer included."""
        doc = doc if doc is not None else self.doc
        if sources is None:
            sources = self.entry.sources if self.entry is not None else []
        if not sources:
            return None
        try:
            descriptor = doc.findDefault()
        except Exception:  # pragma: no cover - defensive
            descriptor = None
        if descriptor is not None:
            matched = self._match_source(descriptor, sources)
            if matched is not None:
                return matched
        return sources[0]

    @staticmethod
    def _source_label(source) -> str:
        """Name a source so that two layers of one UFO read differently."""
        if source is None:
            return ""
        name = Path(str(source.path)).name if getattr(source, "path", None) else ""
        layer = None
        if hasattr(source, "master_layer_name"):
            layer = source.master_layer_name()
        else:
            layer = getattr(source, "layerName", None)
        if layer:
            return f"{name} [{layer}]" if name else str(layer)
        style = getattr(source, "style_name", None) or getattr(source, "styleName", None)
        if style:
            return f"{name} ({style})" if name else str(style)
        return name or str(getattr(source, "name", "") or "")

    def _label(self, source) -> str:
        """`_source_label`, remembered per run.

        The label parses a path and asks the master for its layer; in the glyph
        loop that happens once per glyph per master, for a label that cannot
        change while the check runs.
        """
        key = id(source)
        label = self._label_memo.get(key)
        if label is None:
            label = self._source_label(source)
            self._label_memo[key] = label
        return label

    @staticmethod
    def _is_layer_source(source) -> bool:
        """Whether this master is a layer inside a UFO rather than a UFO.

        ufo2ft skips layer sources for kerning and never compiles their
        features; their glyph order is their parent UFO's. So every check about
        a UFO's own data has to leave them out -- not because they are
        "sparse", but because they are not separate UFOs.
        """
        if source is None:
            return False
        if hasattr(source, "master_layer_name"):
            return bool(source.master_layer_name())
        return bool(getattr(source, "layerName", None))

    @classmethod
    def _own_keys(cls, source) -> set[str]:
        """Glyph names this master actually draws, without a layer fallback."""
        if source is None:
            return set()
        try:
            if cls._is_layer_source(source):
                return set(source.get_layer().keys())
            return set(source.font.keys())
        except Exception:  # pragma: no cover - defensive
            return set()

    @classmethod
    def _own_glyph(cls, source, name: str):
        """The glyph this master draws, or None -- never another layer's.

        A master that is a whole UFO goes straight to the font: building a
        layer view for it means asking fontParts for the default layer's name
        on every glyph of every master, which is most of the cost of a run.
        """
        if source is None:
            return None
        try:
            if cls._is_layer_source(source):
                return source.own_glyph(name)
            font = source.font
            return font[name] if name in font else None
        except Exception:  # pragma: no cover - defensive
            return None

    @staticmethod
    def _format_discrete_location(loc: dict[str, float] | None) -> str:
        """
        Format discrete location dict as human-readable string.

        Args:
            loc: Discrete location dict (e.g., {"italic": 1.0})

        Returns:
            Formatted string (e.g., "italic:1")
        """
        if not loc:
            return ""
        parts = []
        for axis, value in sorted(loc.items()):
            if value == int(value):
                parts.append(f"{axis}:{int(value)}")
            else:
                parts.append(f"{axis}:{value:.1f}")
        return ", ".join(parts)
