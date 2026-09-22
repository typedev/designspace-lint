"""
GTK wrapper around the designspace-lint engine.

The checks, the phase order and the discrete-axis splitting live in
`designspace_lint.engine`, which knows nothing about GTK and runs on whatever
thread it is called from. This adds the three things a window needs and a
library must not impose: a worker thread, callbacks marshalled to the main
loop, and results wrapped as `ProblemItem` GObjects for the list model.

Copyright 2024-2026 TypeDev
Licensed under the Apache License, Version 2.0
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from gi.repository import GLib

from designspace_lint.engine import PHASES, Linter

from .model import ProblemItem

if TYPE_CHECKING:
    from font_rover.designspace import DesignSpaceEntry

logger = logging.getLogger(__name__)

__all__ = ["ValidatorRegistry", "PHASES"]


class ValidatorRegistry:
    """
    Runs the lint engine for the UI.

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
    """

    def __init__(
        self,
        designspace_entry: "DesignSpaceEntry | None" = None,
        path: Path | None = None,
    ):
        """
        Args:
            designspace_entry: DesignSpaceEntry with loaded fonts (preferred)
            path: Path to .designspace file (fallback, read from disk)
        """
        self._entry = designspace_entry
        self._path = path or (designspace_entry.path if designspace_entry else None)
        self._is_running = False
        self._cancel = threading.Event()

    @property
    def is_running(self) -> bool:
        """True if an async check is currently running."""
        return self._is_running

    def cancel(self) -> None:
        """Ask a running check to stop at the next phase or glyph."""
        self._cancel.set()

    def _linter(self) -> Linter:
        return Linter(designspace=self._entry, path=self._path, cancel=self._cancel)

    def check_sync(self) -> list[ProblemItem]:
        """Run every check on this thread and return the results for the list."""
        return [ProblemItem.from_check_result(r) for r in self._linter().run()]

    def check_async(
        self,
        on_phase: Callable[[str, int, int], None] | None = None,
        on_progress: Callable[[int, int, str], None] | None = None,
        on_complete: Callable[[list[ProblemItem]], None] | None = None,
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        """
        Run every check on a worker thread.

        All callbacks are delivered on the GTK main thread.

        Args:
            on_phase: (phase_name, current, total) as each phase starts
            on_progress: (current, total, message) for finer-grained progress
            on_complete: Called with the finished list of ProblemItem
            on_error: Called with a message if the run raised
        """
        if self._is_running:
            logger.warning("Check already running")
            return

        self._is_running = True
        self._cancel.clear()

        def to_main(callback):
            """Hand a library callback to the main loop, or drop it."""
            if callback is None:
                return None
            return lambda *args: GLib.idle_add(callback, *args)

        def worker():
            try:
                items = [
                    ProblemItem.from_check_result(result)
                    for result in self._linter().run(
                        on_phase=to_main(on_phase),
                        on_progress=to_main(on_progress),
                    )
                ]
                if on_complete and not self._cancel.is_set():
                    GLib.idle_add(on_complete, items)
            except Exception as e:  # pragma: no cover - reported to the UI
                logger.exception(f"Check failed: {e}")
                if on_error:
                    GLib.idle_add(on_error, str(e))
            finally:
                self._is_running = False

        threading.Thread(target=worker, daemon=True).start()
