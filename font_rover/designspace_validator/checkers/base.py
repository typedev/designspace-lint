"""
Base class for DesignSpace checkers.

Copyright 2024-2026 TypeDev
Licensed under the Apache License, Version 2.0
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Iterator

from ..model import CheckResult

if TYPE_CHECKING:
    from fontTools.designspaceLib import DesignSpaceDocument

    from font_rover.designspace import DesignSpaceEntry


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

    @staticmethod
    def _is_sparse_source(source) -> bool:
        """Detect sparse masters by "sparse" substring in source name or filename.

        Sparse masters contain only a handful of glyph corrections relative
        to full masters and are expected to be incomplete. Validation checks
        that assume full glyph/feature coverage should skip them.

        Accepts either a fontTools SourceDescriptor or a FontSource.
        """
        if source is None:
            return False
        name = getattr(source, "name", "") or ""
        if "sparse" in name.lower():
            return True
        filename = getattr(source, "filename", None)
        if filename and "sparse" in Path(filename).name.lower():
            return True
        path = getattr(source, "path", None)
        if path is not None and "sparse" in Path(str(path)).name.lower():
            return True
        return False

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
