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

A check that raises does not take the run down, and it does not vanish into a
log line either: it becomes a finding of its own (0.1), so the exit code says
that part of the document went unchecked. Before 0.2 such a crash was only
logged, and three of them -- a rule without a conditionset, an unnamed
duplicate instance, an unknown location label -- each silently dropped the
rest of a phase.

Progress callbacks are ordinary callables invoked on the caller's own thread.
A GUI that needs them elsewhere marshals them itself -- that is font-rover's
`ValidatorRegistry`, which wraps this class in a thread and a main-loop hop.
"""

from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Iterator

from .model import CATEGORY_FILE, SEVERITY_STRUCTURAL, CheckResult

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
    ("labels", "Checking labels..."),
    ("glyphs", "Checking glyphs..."),
    ("kerning", "Checking kerning..."),
    ("fontinfo", "Checking font info..."),
    ("rules", "Checking rules..."),
    ("features", "Checking features..."),
    ("glyphorder", "Checking glyph order..."),
]

# Opt-in: fontTools' varLib.interpolatable over the masters already open. It
# finds what a structural comparison cannot -- start points, contour order,
# shapes that thin out or kink halfway -- and costs about as much again as
# the rest of the run, so it runs only when asked for.
INTERPOLATION_PHASE = ("interpolation", "Checking point correspondence...")

# 0.1: a check raised and the rest of its phase went unchecked. The file
# category is where problems with the run itself live.
PHASE_FAILED = 1

# Phases that look at the whole document. With discrete axes they run once,
# on the document itself: a slice has lost its discrete axes by construction,
# so asking a slice whether it has axes answers a different question.
DOCUMENT_PHASES = ("file", "geometry", "labels")


def phase_failed(phase_id: str, exc: Exception, where: str = "") -> CheckResult:
    """The finding for a check that raised instead of finishing."""
    return CheckResult(
        category=CATEGORY_FILE,
        code=PHASE_FAILED,
        description=f"the {phase_id} checks stopped early: {type(exc).__name__}: {exc}",
        location=where,
        details=(
            "Everything this phase would have reported after the failure is missing, so "
            "a clean result here does not mean a clean designspace."
        ),
        severity=SEVERITY_STRUCTURAL,
        raw_data={"phase": phase_id, "exception": repr(exc)},
    )


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
        interpolatable: bool = False,
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
            interpolatable: also run the point-correspondence phase (4.14 to
                4.18), right after the glyph checks.
        """
        self._entry = designspace
        self._path = path or (designspace.path if designspace else None)
        self._cancel = cancel
        self._checkers: dict[str, type["BaseChecker"]] = {}
        self._structural_problem_found = False
        self._phases = list(PHASES)
        if interpolatable:
            glyphs_at = [p[0] for p in self._phases].index("glyphs")
            self._phases.insert(glyphs_at + 1, INTERPOLATION_PHASE)

        # Register all checkers
        self._register_checkers()
        if interpolatable:
            from .checkers.interpolation import InterpolationChecker

            self._checkers["interpolation"] = InterpolationChecker

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
            from .checkers.labels import LabelsChecker

            self._checkers["labels"] = LabelsChecker
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
        total_phases = len(self._phases)

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

        for i, (phase_id, phase_name) in enumerate(self._phases):
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
                    # `done_so_far` is bound now, not when the callback runs:
                    # the loop keeps moving current_work, and a late-bound
                    # closure would report progress from the wrong phase.
                    def glyph_progress(checked, total, done_so_far=current_work):
                        current = done_so_far + checked
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
                yield phase_failed(phase_id, e)

            # Stop after structural problems in early phases
            if phase_id in ("file", "geometry", "sources"):
                if self._structural_problem_found:
                    logger.info(f"Stopping after {phase_id}: structural problems")
                    break

            # The checks that read the whole document run once, here, as they
            # do before a split -- so each is reported once in either mode.
            if phase_id == "geometry":
                doc = self._get_doc()
                if doc is not None:
                    yield from self._run_document_checks(doc)

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

        doc_phases = [p for p in self._phases if p[0] in DOCUMENT_PHASES]
        slice_phases = [p for p in self._phases if p[0] not in DOCUMENT_PHASES]

        # The document-level phases run once, on the whole document.
        self._structural_problem_found = False
        for i, (phase_id, phase_name) in enumerate(doc_phases):
            if self._cancelled:
                logger.info("Check cancelled")
                return
            if on_phase:
                on_phase(phase_name, i + 1, total_phases)
            checker = self._get_checker(phase_id)
            if checker is None:
                continue
            try:
                for result in checker.check():
                    if self._cancelled:
                        return
                    yield result
                    if result.is_structural:
                        self._structural_problem_found = True
            except Exception as e:
                logger.warning(f"Phase {phase_id} failed: {e}")
                yield phase_failed(phase_id, e)
            if self._structural_problem_found:
                logger.info(f"Stopping after {phase_id}: structural problems")
                return

        # What the split would hide: sources and instances that fall into no
        # slice, and instances whose location cannot be resolved at all.
        yield from self._run_document_checks(doc)

        # Slicing needs only the discrete axes. The declared variable fonts
        # are resolved during the split as well, and one that names an unknown
        # axis or a range over a discrete one makes it raise (1.19 / 1.20,
        # already reported) -- so split a copy that declares none.
        to_split = doc
        if getattr(doc, "variableFonts", None):
            to_split = copy.copy(doc)
            to_split.variableFonts = []

        try:
            sub_docs = list(splitInterpolable(to_split))
        except Exception as e:
            # An instance naming an unknown location label makes the split
            # itself raise; without it there are no slices to check.
            logger.warning(f"Splitting by discrete axes failed: {e}")
            yield phase_failed("discrete split", e)
            return
        num_splits = len(sub_docs)
        total_steps = len(doc_phases) + len(slice_phases) * num_splits

        # Estimate total work for all splits
        glyph_count = self._estimate_glyph_count()
        work_per_split = (len(slice_phases) - 1) + glyph_count
        total_work = work_per_split * num_splits
        current_work = 0

        for split_idx, (discrete_loc, sub_doc) in enumerate(sub_docs):
            # Check for cancellation
            if self._cancelled:
                logger.info("Check cancelled")
                return

            discrete_label = self._format_discrete_location(discrete_loc)
            logger.info(f"Checking discrete location: {discrete_label or 'default'}")

            # Each slice stops on its own structural problems, not on an
            # earlier slice's: a missing master in the upright must not leave
            # the italic unchecked.
            self._structural_problem_found = False

            for phase_idx, (phase_id, phase_name) in enumerate(slice_phases):
                # Check for cancellation
                if self._cancelled:
                    return

                # Report phase
                if on_phase:
                    label = phase_name
                    if discrete_label:
                        label = f"{phase_name} [{discrete_label}]"
                    phase_num = len(doc_phases) + split_idx * len(slice_phases) + phase_idx + 1
                    on_phase(label, phase_num, total_steps)

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
                        self._tag_with_slice(result, discrete_loc, discrete_label)
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
                    failure = phase_failed(phase_id, e)
                    self._tag_with_slice(failure, discrete_loc, discrete_label)
                    yield failure

                # Stop on structural problems
                if phase_id == "sources" and self._structural_problem_found:
                    logger.info(f"Stopping {discrete_label} after {phase_id}: structural problems")
                    break

    def _run_document_checks(self, doc) -> Iterator[CheckResult]:
        """The source and instance checks that only make sense before a split."""
        from .checkers.instances import InstancesChecker
        from .checkers.sources import SourcesChecker

        for phase_id, checker_cls in (("sources", SourcesChecker), ("instances", InstancesChecker)):
            checker = checker_cls(entry=self._entry, doc=doc, path=self._path)
            try:
                yield from checker.check_document(doc)
            except Exception as e:
                logger.warning(f"Document-level {phase_id} checks failed: {e}")
                yield phase_failed(phase_id, e)

    @staticmethod
    def _tag_with_slice(result: CheckResult, discrete_loc, discrete_label: str) -> None:
        """Say which discrete slice a result came from."""
        if not discrete_label:
            return
        result.raw_data["discreteLocation"] = discrete_loc
        if result.location:
            result.location = f"{result.location} [{discrete_label}]"
        else:
            result.location = f"[{discrete_label}]"

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
