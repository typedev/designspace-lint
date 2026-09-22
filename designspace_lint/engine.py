# Copyright 2024-2026 TypeDev
# Licensed under the Apache License, Version 2.0

"""
Running every check over a designspace, in the order that makes sense.

The order is not cosmetic. The first three phases -- the file, the axes, the
sources -- decide whether the document can be read at all, so a structural
problem there stops the run: there is no point comparing glyph contours across
masters that could not be opened.

Discrete axes split the run. A discrete axis does not interpolate, so each of
its values is a separate space with its own default master and its own
extremes, and every rule is a rule about one slice. Results are tagged with the
slice they came from.

Progress callbacks are ordinary callables invoked on the caller's own thread.
A GUI that needs them elsewhere marshals them itself -- that is font-rover's
`ValidatorRegistry`, which wraps this class in a thread and a main-loop hop.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Iterator


from .model import CheckResult

if TYPE_CHECKING:
    from fontTools.designspaceLib import DesignSpaceDocument

    from .loader import DesignSpace

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


class Linter:
    """
    Runs every check over one designspace.

    Example:
        linter = Linter(designspace=open_designspace(path))
        for problem in linter.run():
            print(problem.description)

    The designspace can be anything satisfying
    :class:`designspace_lint.protocols.DesignSpaceLike`: the loader's own
    object, or a host application's, with its fonts already open.
    """

    def __init__(
        self,
        designspace: "DesignSpace | None" = None,
        path: Path | None = None,
        cancel: Any = None,
    ):
        """
        Args:
            designspace: a DesignSpaceLike with its fonts already open. The
                checks that compare masters need this; given only a path, the
                document-level checks still run.
            path: Path to the .designspace file, when no designspace is given.
            cancel: Anything with ``is_set()`` -- a ``threading.Event``, say --
                polled between phases and between glyphs so a caller running
                this in a thread can stop it.
        """
        self._entry = designspace
        self._path = path or (designspace.path if designspace else None)
        self._cancel = cancel
        self._checkers: dict[str, type["BaseChecker"]] = {}
        self._structural_problem_found = False

        # Register all checkers
        self._register_checkers()

    @property
    def _cancelled(self) -> bool:
        """Whether the caller has asked us to stop."""
        return self._cancel is not None and self._cancel.is_set()

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

    def run(
        self,
        on_phase: Callable[[str, int, int], None] | None = None,
        on_progress: Callable[[int, int, str], None] | None = None,
    ) -> Iterator[CheckResult]:
        """Yield every problem found, in phase order.

        Blocks the calling thread; the callbacks fire on it too.
        """
        yield from self._run_checks(on_phase=on_phase, on_progress=on_progress)

    def check_sync(self) -> list[CheckResult]:
        """All problems as a list. Kept for callers that want them at once."""
        return list(self._run_checks(on_phase=None))

    def _run_checks(
        self,
        on_phase: Callable[[str, int, int], None] | None = None,
        on_progress: Callable[[int, int, str], None] | None = None,
    ) -> Iterator[CheckResult]:
        """
        Run all check phases.

        Args:
            on_phase: Optional phase callback (phase_name, current, total)
            on_progress: Optional granular progress callback (current, total, message)

        Yields:
            CheckResult for each problem found
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
    ) -> Iterator[CheckResult]:
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
                on_phase(phase_name, i + 1, total_phases)

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
                        on_progress(current, total_work, msg)

                    glyphs_checker = self._checkers["glyphs"](
                        entry=self._entry, path=self._path, on_glyph_progress=glyph_progress
                    )
                    for result in glyphs_checker.check():
                        if self._cancelled:
                            return
                        yield result
                        if result.is_structural:
                            self._structural_problem_found = True
                    current_work += glyph_count
                else:
                    for result in checker.check():
                        if self._cancelled:
                            return
                        yield result

                        # Track structural problems
                        if result.is_structural:
                            self._structural_problem_found = True

                    current_work += 1
                    if on_progress:
                        on_progress(current_work, total_work, phase_name)

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
    ) -> Iterator[CheckResult]:
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
                    on_phase(label, phase_num, total_phases * num_splits)

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

                        yield result

                        if result.is_structural:
                            self._structural_problem_found = True

                    # Update progress
                    current_work += 1 if phase_id != "glyphs" else glyph_count
                    if on_progress:
                        label = phase_name
                        if discrete_label:
                            label = f"{phase_name} [{discrete_label}]"
                        on_progress(current_work, total_work, label)

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

    def _filter_entry_for_subdoc(self, sub_doc: "DesignSpaceDocument") -> "DesignSpace | None":
        """
        Create a filtered DesignSpace with only sources from sub_doc.

        Args:
            sub_doc: Sub-designspace for a discrete location

        Returns:
            Filtered DesignSpace or None if no entry
        """
        if self._entry is None:
            return None

        from .loader import DesignSpace

        from .checkers.base import BaseChecker

        # Match on path *and* layer. In a layer-based designspace every master
        # of a UFO answers to the same path, so a path-only filter handed each
        # slice every layer of that UFO -- including layers belonging to
        # another discrete slice.
        filtered_sources = []
        for descriptor in sub_doc.sources:
            matched = BaseChecker._match_source(descriptor, self._entry.sources)
            if matched is not None and matched not in filtered_sources:
                filtered_sources.append(matched)

        # Create new entry with filtered sources
        return DesignSpace(
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
