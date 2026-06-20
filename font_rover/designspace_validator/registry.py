"""
ValidatorRegistry - orchestrates all DesignSpace validation checkers.

Provides both sync and async checking with progress callbacks.

Copyright 2024-2026 TypeDev
Licensed under the Apache License, Version 2.0
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Iterator

from gi.repository import GLib

from .model import ProblemItem

if TYPE_CHECKING:
    from fontTools.designspaceLib import DesignSpaceDocument

    from font_rover.designspace import DesignSpaceEntry

    from .checkers.base import BaseChecker

logger = logging.getLogger(__name__)

# Check phases with display names
# Order matters: structural checks first, then design checks
PHASES = [
    ("file", "Checking file..."),
    ("geometry", "Checking geometry..."),
    ("sources", "Checking sources..."),
    ("instances", "Checking instances..."),
    ("glyphs", "Checking glyphs..."),
    ("kerning", "Checking kerning..."),
    ("fontinfo", "Checking font info..."),
    ("rules", "Checking rules..."),
    ("features", "Checking features..."),
    ("glyphorder", "Checking glyph order..."),
]


class ValidatorRegistry:
    """
    Orchestrates all DesignSpace validation checkers.

    Provides:
    - check_async(): Background thread checking with progress callbacks
    - check_sync(): Blocking synchronous checking
    - Per-phase progress reporting
    - Automatic handling of discrete axes (splits designspace)

    Example (async):
        registry = ValidatorRegistry(designspace_entry=entry)
        registry.check_async(
            on_phase=lambda name, cur, total: print(f"{name} ({cur}/{total})"),
            on_complete=lambda items: print(f"Found {len(items)} problems"),
            on_error=lambda msg: print(f"Error: {msg}"),
        )

    Example (sync):
        registry = ValidatorRegistry(path=designspace_path)
        items = registry.check_sync()
        for item in items:
            print(item)
    """

    def __init__(
        self,
        designspace_entry: "DesignSpaceEntry | None" = None,
        path: Path | None = None,
    ):
        """
        Initialize registry.

        Args:
            designspace_entry: DesignSpaceEntry with loaded fonts (preferred)
            path: Path to .designspace file (fallback, will read from disk)
        """
        self._entry = designspace_entry
        self._path = path or (designspace_entry.path if designspace_entry else None)
        self._is_running = False
        self._cancelled = False
        self._checkers: dict[str, type["BaseChecker"]] = {}
        self._structural_problem_found = False

        # Register all checkers
        self._register_checkers()

    @property
    def is_running(self) -> bool:
        """True if async check is currently running."""
        return self._is_running

    def cancel(self) -> None:
        """Request cancellation of running check."""
        self._cancelled = True

    def _register_checkers(self) -> None:
        """Register all available checkers."""
        # Import checkers lazily to avoid circular imports
        # Checkers will be registered as they are implemented
        try:
            from .checkers.file import FileChecker

            self._checkers["file"] = FileChecker
        except ImportError:
            pass

        try:
            from .checkers.axes import AxesChecker

            self._checkers["geometry"] = AxesChecker
        except ImportError:
            pass

        try:
            from .checkers.sources import SourcesChecker

            self._checkers["sources"] = SourcesChecker
        except ImportError:
            pass

        try:
            from .checkers.instances import InstancesChecker

            self._checkers["instances"] = InstancesChecker
        except ImportError:
            pass

        try:
            from .checkers.glyphs import GlyphsChecker

            self._checkers["glyphs"] = GlyphsChecker
        except ImportError:
            pass

        try:
            from .checkers.kerning import KerningChecker

            self._checkers["kerning"] = KerningChecker
        except ImportError:
            pass

        try:
            from .checkers.fontinfo import FontInfoChecker

            self._checkers["fontinfo"] = FontInfoChecker
        except ImportError:
            pass

        try:
            from .checkers.rules import RulesChecker

            self._checkers["rules"] = RulesChecker
        except ImportError:
            pass

        try:
            from .checkers.features import FeaturesChecker

            self._checkers["features"] = FeaturesChecker
        except ImportError:
            pass

        try:
            from .checkers.glyphorder import GlyphOrderChecker

            self._checkers["glyphorder"] = GlyphOrderChecker
        except ImportError:
            pass

    def _get_checker(self, phase_id: str) -> "BaseChecker | None":
        """
        Get checker instance for phase.

        Args:
            phase_id: Phase identifier (e.g., "sources", "glyphs")

        Returns:
            Checker instance or None if not available
        """
        checker_cls = self._checkers.get(phase_id)
        if checker_cls is None:
            return None

        return checker_cls(entry=self._entry, path=self._path)

    def check_async(
        self,
        on_phase: Callable[[str, int, int], None] | None = None,
        on_progress: Callable[[int, int, str], None] | None = None,
        on_complete: Callable[[list[ProblemItem]], None] | None = None,
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        """
        Run checks asynchronously with progress callbacks.

        Args:
            on_phase: Called for each phase (phase_name, current_phase, total_phases)
            on_progress: Called for granular progress (current, total, message)
            on_complete: Called when complete with list of ProblemItem
            on_error: Called on error with error message

        Note:
            All callbacks are called on the main GTK thread via GLib.idle_add.
        """
        if self._is_running:
            logger.warning("Check already running")
            return

        self._is_running = True
        self._cancelled = False

        def worker():
            try:
                items = list(self._run_checks(on_phase, on_progress))

                # Don't call callback if cancelled
                if on_complete and not self._cancelled:
                    GLib.idle_add(on_complete, items)

            except Exception as e:
                if not self._cancelled:
                    logger.exception(f"Check failed: {e}")
                    if on_error:
                        GLib.idle_add(on_error, str(e))
            finally:
                self._is_running = False

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def check_sync(self) -> list[ProblemItem]:
        """
        Run checks synchronously.

        Returns:
            List of ProblemItem

        Note:
            This blocks the current thread. Use check_async for UI.
        """
        return list(self._run_checks(on_phase=None))

    def _run_checks(
        self,
        on_phase: Callable[[str, int, int], None] | None = None,
        on_progress: Callable[[int, int, str], None] | None = None,
    ) -> Iterator[ProblemItem]:
        """
        Run all check phases.

        Args:
            on_phase: Optional phase callback (phase_name, current, total)
            on_progress: Optional granular progress callback (current, total, message)

        Yields:
            ProblemItem for each problem found
        """
        self._structural_problem_found = False
        total_phases = len(PHASES)

        # Check if we have discrete axes
        has_discrete = self._has_discrete_axes()

        if has_discrete:
            # Split designspace and check each discrete location separately
            yield from self._run_checks_split(on_phase, on_progress, total_phases)
        else:
            # Standard check
            yield from self._run_checks_standard(on_phase, on_progress, total_phases)

    def _run_checks_standard(
        self,
        on_phase: Callable[[str, int, int], None] | None,
        on_progress: Callable[[int, int, str], None] | None,
        total_phases: int,
    ) -> Iterator[ProblemItem]:
        """Run checks on a single designspace (no discrete axes)."""
        # Estimate total work: other phases + glyphs
        # Each non-glyph phase counts as 1 unit
        # Glyphs phase: 1 unit per glyph
        glyph_count = self._estimate_glyph_count()
        total_work = (total_phases - 1) + glyph_count  # -1 because glyphs counted separately
        current_work = 0

        for i, (phase_id, phase_name) in enumerate(PHASES):
            # Check for cancellation
            if self._cancelled:
                logger.info("Check cancelled")
                return

            # Report phase start
            if on_phase:
                GLib.idle_add(on_phase, phase_name, i + 1, total_phases)

            # Get checker
            checker = self._get_checker(phase_id)
            if checker is None:
                logger.debug(f"No checker for phase: {phase_id}")
                current_work += 1 if phase_id != "glyphs" else glyph_count
                continue

            # Run phase
            try:
                if phase_id == "glyphs" and on_progress:
                    # Special handling for glyphs - create checker with progress callback
                    def glyph_progress(checked, total):
                        current = current_work + checked
                        msg = f"Checking glyphs ({checked}/{total})"
                        GLib.idle_add(on_progress, current, total_work, msg)

                    glyphs_checker = self._checkers["glyphs"](
                        entry=self._entry, path=self._path, on_glyph_progress=glyph_progress
                    )
                    for result in glyphs_checker.check():
                        if self._cancelled:
                            return
                        item = ProblemItem.from_check_result(result)
                        yield item
                        if result.is_structural:
                            self._structural_problem_found = True
                    current_work += glyph_count
                else:
                    for result in checker.check():
                        if self._cancelled:
                            return
                        item = ProblemItem.from_check_result(result)
                        yield item

                        # Track structural problems
                        if result.is_structural:
                            self._structural_problem_found = True

                    current_work += 1
                    if on_progress:
                        GLib.idle_add(on_progress, current_work, total_work, phase_name)

            except Exception as e:
                logger.warning(f"Phase {phase_id} failed: {e}")
                current_work += 1 if phase_id != "glyphs" else glyph_count

            # Stop after structural problems in early phases
            if phase_id in ("file", "geometry", "sources"):
                if self._structural_problem_found:
                    logger.info(f"Stopping after {phase_id}: structural problems")
                    break

    def _estimate_glyph_count(self) -> int:
        """Estimate number of glyphs to check."""
        if self._entry is None:
            return 100  # Default estimate

        all_glyphs: set[str] = set()
        for source in self._entry.sources:
            all_glyphs.update(source.font.keys())
        return len(all_glyphs) or 100

    def _run_checks_split(
        self,
        on_phase: Callable[[str, int, int], None] | None,
        on_progress: Callable[[int, int, str], None] | None,
        total_phases: int,
    ) -> Iterator[ProblemItem]:
        """
        Run checks on a designspace with discrete axes.

        Splits by discrete locations and checks each separately.
        """
        from fontTools.designspaceLib.split import splitInterpolable

        doc = self._get_doc()
        if doc is None:
            return

        sub_docs = list(splitInterpolable(doc))
        num_splits = len(sub_docs)

        # Estimate total work for all splits
        glyph_count = self._estimate_glyph_count()
        work_per_split = (total_phases - 1) + glyph_count
        total_work = work_per_split * num_splits
        current_work = 0

        for split_idx, (discrete_loc, sub_doc) in enumerate(sub_docs):
            # Check for cancellation
            if self._cancelled:
                logger.info("Check cancelled")
                return

            discrete_label = self._format_discrete_location(discrete_loc)
            logger.info(f"Checking discrete location: {discrete_label or 'default'}")

            for phase_id, phase_name in PHASES:
                # Check for cancellation
                if self._cancelled:
                    return

                # Report phase
                if on_phase:
                    label = phase_name
                    if discrete_label:
                        label = f"{phase_name} [{discrete_label}]"
                    phase_num = split_idx * total_phases + PHASES.index((phase_id, phase_name)) + 1
                    GLib.idle_add(on_phase, label, phase_num, total_phases * num_splits)

                # Get checker for sub-doc
                checker = self._get_checker_for_subdoc(phase_id, sub_doc)
                if checker is None:
                    current_work += 1 if phase_id != "glyphs" else glyph_count
                    continue

                # Run phase
                try:
                    for result in checker.check():
                        if self._cancelled:
                            return
                        # Add discrete location to result
                        if discrete_label:
                            result.raw_data["discreteLocation"] = discrete_loc
                            if result.location:
                                result.location = f"{result.location} [{discrete_label}]"
                            else:
                                result.location = f"[{discrete_label}]"

                        item = ProblemItem.from_check_result(result)
                        yield item

                        if result.is_structural:
                            self._structural_problem_found = True

                    # Update progress
                    current_work += 1 if phase_id != "glyphs" else glyph_count
                    if on_progress:
                        label = phase_name
                        if discrete_label:
                            label = f"{phase_name} [{discrete_label}]"
                        GLib.idle_add(on_progress, current_work, total_work, label)

                except Exception as e:
                    logger.warning(f"Phase {phase_id} failed for {discrete_label}: {e}")
                    current_work += 1 if phase_id != "glyphs" else glyph_count

                # Stop on structural problems
                if phase_id in ("file", "geometry", "sources"):
                    if self._structural_problem_found:
                        logger.info(
                            f"Stopping {discrete_label} after {phase_id}: structural problems"
                        )
                        break

    def _get_checker_for_subdoc(
        self, phase_id: str, sub_doc: "DesignSpaceDocument"
    ) -> "BaseChecker | None":
        """Get checker for a split sub-document."""
        checker_cls = self._checkers.get(phase_id)
        if checker_cls is None:
            return None

        # Create filtered entry with only sources from sub_doc
        filtered_entry = self._filter_entry_for_subdoc(sub_doc)

        # Create checker with filtered entry and sub-doc
        return checker_cls(entry=filtered_entry, doc=sub_doc)

    def _filter_entry_for_subdoc(self, sub_doc: "DesignSpaceDocument") -> "DesignSpaceEntry | None":
        """
        Create a filtered DesignSpaceEntry with only sources from sub_doc.

        Args:
            sub_doc: Sub-designspace for a discrete location

        Returns:
            Filtered DesignSpaceEntry or None if no entry
        """
        if self._entry is None:
            return None

        from pathlib import Path

        from font_rover.designspace import DesignSpaceEntry

        # Build set of paths in sub_doc
        sub_doc_paths = set()
        for source in sub_doc.sources:
            if source.path:
                sub_doc_paths.add(Path(source.path).resolve())

        # Filter entry sources
        filtered_sources = []
        for font_source in self._entry.sources:
            if font_source.path.resolve() in sub_doc_paths:
                filtered_sources.append(font_source)

        # Create new entry with filtered sources
        return DesignSpaceEntry(
            path=self._entry.path,
            doc=sub_doc,
            sources=filtered_sources,
        )

    def _has_discrete_axes(self) -> bool:
        """Check if the designspace has discrete axes."""
        try:
            doc = self._get_doc()
            if doc is None:
                return False

            for axis in doc.axes:
                if hasattr(axis, "values") and axis.values:
                    return True
            return False
        except Exception as e:
            logger.warning(f"Failed to check for discrete axes: {e}")
            return False

    def _get_doc(self) -> "DesignSpaceDocument | None":
        """Get DesignSpaceDocument."""
        if self._entry is not None:
            return self._entry.doc

        if self._path is not None:
            from fontTools.designspaceLib import DesignSpaceDocument

            return DesignSpaceDocument.fromfile(str(self._path))

        return None

    @staticmethod
    def _format_discrete_location(loc: dict[str, float] | None) -> str:
        """Format discrete location dict as string."""
        if not loc:
            return ""
        parts = []
        for axis, value in sorted(loc.items()):
            if value == int(value):
                parts.append(f"{axis}:{int(value)}")
            else:
                parts.append(f"{axis}:{value:.1f}")
        return ", ".join(parts)
