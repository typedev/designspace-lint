"""
ProblemsWindow for displaying DesignSpace validation issues.

Non-modal window with sortable table of problems.

Copyright 2024-2026 TypeDev
Licensed under the Apache License, Version 2.0
"""

import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

from .filter_config import (  # noqa: E402
    FilterState,
    get_subcategory_for_item,
    is_problem_visible,
)
from .filter_popover import FilterPopover  # noqa: E402
from .model import (  # noqa: E402
    SEVERITY_DESIGN,
    SEVERITY_INFO,  # noqa: F401 - may be used in future
    SEVERITY_STRUCTURAL,
    ProblemItem,
)
from .registry import ValidatorRegistry  # noqa: E402

if TYPE_CHECKING:
    from font_rover.designspace import DesignSpaceEntry
    from font_rover.utils import Settings

logger = logging.getLogger(__name__)

# Settings prefix
_SETTINGS_PREFIX = "designspace_problems_window"


class ProblemFilter(Gtk.Filter):
    """
    Custom Gtk.Filter for filtering ProblemItem based on FilterState.
    """

    __gtype_name__ = "ProblemFilter"

    def __init__(self, filter_state: FilterState):
        super().__init__()
        self._state = filter_state

    def set_filter_state(self, state: FilterState) -> None:
        """Update filter state and notify of change."""
        self._state = state
        self.changed(Gtk.FilterChange.DIFFERENT)

    def do_match(self, item: ProblemItem) -> bool:
        """Check if item matches current filter."""
        return is_problem_visible(item, self._state)

    def do_get_strictness(self) -> Gtk.FilterMatch:
        """Return filter strictness."""
        if not self._state.has_any_disabled():
            return Gtk.FilterMatch.ALL
        return Gtk.FilterMatch.SOME


class ProblemsWindow(Adw.Window):
    """
    Window for displaying DesignSpace validation problems.

    Features:
    - Sortable ColumnView with problems
    - Summary row with counts by severity
    - Progress overlay during check
    - Double-click to navigate to glyph/source
    - Settings persistence for window size
    """

    def __init__(
        self,
        designspace: "DesignSpaceEntry",
        editor_window: Any = None,
        settings: "Settings | None" = None,
        on_check_complete: Callable[[int], None] | None = None,
        application: Gtk.Application | None = None,
    ):
        """
        Initialize ProblemsWindow.

        Args:
            designspace: DesignSpaceEntry with sources
            editor_window: Parent FontEditorWindow for navigation actions
            settings: Settings instance for persistence
            on_check_complete: Callback with problem count after check
            application: GTK Application
        """
        super().__init__()

        self._designspace = designspace
        self._editor_window = editor_window
        self._settings = settings
        self._on_check_complete = on_check_complete

        if application:
            self.set_application(application)

        # State
        self._has_results = False
        self._problems: list[ProblemItem] = []
        self._registry: ValidatorRegistry | None = None
        self._force_close = False  # Set by cleanup() to allow destroy
        self._destroyed = False  # Set by cleanup() to prevent callbacks

        # UI components
        self._model: Gio.ListStore | None = None
        self._sort_model: Gtk.SortListModel | None = None
        self._filter_model: Gtk.FilterListModel | None = None
        self._problem_filter: "ProblemFilter | None" = None
        self._selection: Gtk.MultiSelection | None = None
        self._column_view: Gtk.ColumnView | None = None
        self._scrolled_window: Gtk.ScrolledWindow | None = None
        self._recheck_selected_btn: Gtk.Button | None = None

        # Filter state
        self._filter_state = FilterState()
        self._filter_popover: FilterPopover | None = None
        self._filter_btn: Gtk.MenuButton | None = None

        # Cached cursor for clickable items (avoid creating on every bind)
        self._pointer_cursor: Gdk.Cursor | None = None

        # Summary labels
        self._structural_label: Gtk.Label | None = None
        self._design_label: Gtk.Label | None = None
        self._info_label: Gtk.Label | None = None
        self._total_label: Gtk.Label | None = None

        # Progress overlay
        self._progress_overlay: Gtk.Overlay | None = None
        self._progress_box: Gtk.Box | None = None
        self._progress_bar: Gtk.ProgressBar | None = None
        self._phase_label: Gtk.Label | None = None
        self._timer_label: Gtk.Label | None = None

        # Timer state
        self._check_start_time: float = 0
        self._timer_source_id: int | None = None

        self._setup_window()
        self._setup_header()
        self._setup_content()
        self._load_settings()

    @property
    def has_results(self) -> bool:
        """True if check has been run at least once."""
        return self._has_results

    # --- Setup ---

    def _setup_window(self) -> None:
        """Configure window properties."""
        self.set_title("DesignSpace Problems")
        self.set_default_size(750, 500)
        # Not modal, not transient - independent window

    def _setup_header(self) -> None:
        """Create header bar with recheck and copy buttons."""
        header = Adw.HeaderBar()

        # Copy report button
        self._copy_btn = Gtk.Button(icon_name="edit-copy-symbolic")
        self._copy_btn.set_tooltip_text("Copy Report to Clipboard")
        self._copy_btn.connect("clicked", self._on_copy_clicked)
        self._copy_btn.set_sensitive(False)  # Disabled until results available
        header.pack_end(self._copy_btn)

        # Recheck button (full)
        recheck_btn = Gtk.Button(icon_name="view-refresh-symbolic")
        recheck_btn.set_tooltip_text("Recheck All")
        recheck_btn.connect("clicked", self._on_recheck_clicked)
        header.pack_end(recheck_btn)

        # Recheck Selected button
        self._recheck_selected_btn = Gtk.Button(label="Recheck Selected")
        self._recheck_selected_btn.set_tooltip_text("Recheck only selected problems")
        self._recheck_selected_btn.connect("clicked", self._on_recheck_selected_clicked)
        self._recheck_selected_btn.set_sensitive(False)  # Disabled until selection
        header.pack_end(self._recheck_selected_btn)

        # Filter button with popover
        self._filter_popover = FilterPopover()
        self._filter_popover.connect("filter-changed", self._on_filter_changed)

        self._filter_btn = Gtk.MenuButton()
        self._filter_btn.set_icon_name("instant-mix-symbolic")
        self._filter_btn.set_tooltip_text("Filter Problems")
        self._filter_btn.set_popover(self._filter_popover)
        header.pack_start(self._filter_btn)

        # Title with designspace name
        ds_name = self._designspace.path.stem if self._designspace else "Unknown"
        title_label = Gtk.Label(label=f"Problems — {ds_name}")
        title_label.add_css_class("title")
        header.set_title_widget(title_label)

        # Use ToolbarView for proper Adw layout
        self._toolbar_view = Adw.ToolbarView()
        self._toolbar_view.add_top_bar(header)
        self.set_content(self._toolbar_view)

    def _setup_content(self) -> None:
        """Create main content with summary, table, and progress overlay."""
        # Main container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Summary row
        self._setup_summary_row(main_box)

        # Progress overlay wrapping table
        self._progress_overlay = Gtk.Overlay()

        # Scrolled window with ColumnView
        self._scrolled_window = Gtk.ScrolledWindow()
        self._scrolled_window.set_vexpand(True)
        self._scrolled_window.set_hexpand(True)

        self._setup_column_view()
        self._scrolled_window.set_child(self._column_view)

        self._progress_overlay.set_child(self._scrolled_window)

        # Progress box (hidden initially)
        self._setup_progress_box()
        self._progress_overlay.add_overlay(self._progress_box)

        main_box.append(self._progress_overlay)

        # Status bar
        self._setup_status_bar(main_box)

        self._toolbar_view.set_content(main_box)

    def _setup_summary_row(self, parent: Gtk.Box) -> None:
        """Create summary row with severity counts."""
        summary_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        summary_box.set_margin_top(8)
        summary_box.set_margin_bottom(8)
        summary_box.set_margin_start(12)
        summary_box.set_margin_end(12)
        summary_box.set_halign(Gtk.Align.START)

        # Structural count
        structural_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        structural_icon = Gtk.Image.new_from_icon_name("dialog-error-symbolic")
        structural_icon.add_css_class("error")
        self._structural_label = Gtk.Label(label="0 structural")
        structural_box.append(structural_icon)
        structural_box.append(self._structural_label)
        summary_box.append(structural_box)

        # Design count
        design_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        design_icon = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
        design_icon.add_css_class("warning")
        self._design_label = Gtk.Label(label="0 design")
        design_box.append(design_icon)
        design_box.append(self._design_label)
        summary_box.append(design_box)

        # Info count
        info_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        info_icon = Gtk.Image.new_from_icon_name("dialog-information-symbolic")
        self._info_label = Gtk.Label(label="0 info")
        info_box.append(info_icon)
        info_box.append(self._info_label)
        summary_box.append(info_box)

        parent.append(summary_box)

        # Separator
        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        parent.append(separator)

    def _setup_column_view(self) -> None:
        """Create ColumnView with sortable columns."""
        # Model
        self._model = Gio.ListStore(item_type=ProblemItem)

        # Sort model
        self._sort_model = Gtk.SortListModel(model=self._model)

        # Filter model (between sort and selection)
        self._problem_filter = ProblemFilter(self._filter_state)
        self._filter_model = Gtk.FilterListModel(
            model=self._sort_model, filter=self._problem_filter
        )

        # Selection model (multi-selection for recheck selected feature)
        self._selection = Gtk.MultiSelection(model=self._filter_model)
        self._selection.connect("selection-changed", self._on_selection_changed)

        # ColumnView
        self._column_view = Gtk.ColumnView(model=self._selection)
        self._column_view.set_show_row_separators(True)
        self._column_view.set_show_column_separators(False)
        self._column_view.add_css_class("data-table")

        # Connect row activation (double-click)
        self._column_view.connect("activate", self._on_row_activated)

        # Create columns
        self._add_severity_column()
        self._add_category_column()
        self._add_subcategory_column()
        self._add_description_column()
        self._add_location_column()

        # Set sorter
        self._sort_model.set_sorter(self._column_view.get_sorter())

    def _add_severity_column(self) -> None:
        """Add severity icon column."""
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._on_severity_setup)
        factory.connect("bind", self._on_severity_bind)

        column = Gtk.ColumnViewColumn(title="", factory=factory)
        column.set_fixed_width(40)

        # Custom sorter
        sorter = Gtk.CustomSorter.new(self._compare_severity)
        column.set_sorter(sorter)

        self._column_view.append_column(column)

    def _add_category_column(self) -> None:
        """Add category text column."""
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._on_category_setup)
        factory.connect("bind", self._on_category_bind)

        column = Gtk.ColumnViewColumn(title="Category", factory=factory)
        column.set_resizable(True)
        column.set_fixed_width(100)

        sorter = Gtk.CustomSorter.new(self._compare_category)
        column.set_sorter(sorter)

        self._column_view.append_column(column)

    def _add_subcategory_column(self) -> None:
        """Add subcategory text column."""
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._on_subcategory_setup)
        factory.connect("bind", self._on_subcategory_bind)

        column = Gtk.ColumnViewColumn(title="Subcategory", factory=factory)
        column.set_resizable(True)
        column.set_fixed_width(100)

        self._column_view.append_column(column)

    def _add_description_column(self) -> None:
        """Add description column."""
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._on_description_setup)
        factory.connect("bind", self._on_description_bind)

        column = Gtk.ColumnViewColumn(title="Description", factory=factory)
        column.set_resizable(True)
        column.set_expand(True)

        # Sort by glyph name (if present), then by description
        sorter = Gtk.CustomSorter.new(self._compare_glyph)
        column.set_sorter(sorter)

        self._column_view.append_column(column)

    def _add_location_column(self) -> None:
        """Add location column."""
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._on_location_setup)
        factory.connect("bind", self._on_location_bind)

        column = Gtk.ColumnViewColumn(title="Location", factory=factory)
        column.set_resizable(True)

        self._column_view.append_column(column)

    # --- Factory Callbacks ---

    def _on_severity_setup(self, factory, list_item):
        image = Gtk.Image()
        image.set_pixel_size(16)
        list_item.set_child(image)

    def _on_severity_bind(self, factory, list_item):
        item: ProblemItem = list_item.get_item()
        image: Gtk.Image = list_item.get_child()
        image.set_from_icon_name(item.severity_icon)

        # Set color class
        image.remove_css_class("error")
        image.remove_css_class("warning")
        if item.severity == SEVERITY_STRUCTURAL:
            image.add_css_class("error")
        elif item.severity == SEVERITY_DESIGN:
            image.add_css_class("warning")

    def _on_category_setup(self, factory, list_item):
        label = Gtk.Label(xalign=0)
        list_item.set_child(label)

    def _on_category_bind(self, factory, list_item):
        item: ProblemItem = list_item.get_item()
        label: Gtk.Label = list_item.get_child()
        label.set_text(item.category_name)

    def _on_subcategory_setup(self, factory, list_item):
        label = Gtk.Label(xalign=0)
        label.add_css_class("dim-label")
        list_item.set_child(label)

    def _on_subcategory_bind(self, factory, list_item):
        item: ProblemItem = list_item.get_item()
        label: Gtk.Label = list_item.get_child()
        subcategory = get_subcategory_for_item(item)
        label.set_text(subcategory if subcategory else "—")

    def _on_description_setup(self, factory, list_item):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)

        label = Gtk.Label(xalign=0)
        label.set_ellipsize(3)  # PANGO_ELLIPSIZE_END
        label.set_hexpand(True)
        box.append(label)

        # Glyph name in monospace (if present) - clickable style
        glyph_label = Gtk.Label()
        glyph_label.add_css_class("monospace")
        glyph_label.add_css_class("problem-clickable")
        glyph_label.set_cursor(Gdk.Cursor.new_from_name("pointer"))
        glyph_label.set_visible(False)
        box.append(glyph_label)

        # Group name in monospace (if present) - clickable style
        group_label = Gtk.Label()
        group_label.add_css_class("monospace")
        group_label.add_css_class("problem-clickable")
        group_label.set_cursor(Gdk.Cursor.new_from_name("pointer"))
        group_label.set_visible(False)
        box.append(group_label)

        list_item.set_child(box)

    def _on_description_bind(self, factory, list_item):
        item: ProblemItem = list_item.get_item()
        box: Gtk.Box = list_item.get_child()

        # Find child labels
        label = box.get_first_child()
        glyph_label = label.get_next_sibling()
        group_label = glyph_label.get_next_sibling()

        label.set_text(item.description)

        # Show glyph name if present
        if item.has_glyph:
            glyph_label.set_text(f"[{item.glyph_name}]")
            glyph_label.set_visible(True)
        else:
            glyph_label.set_visible(False)

        # Show group name if present (with @. prefix for kerning groups)
        if item.has_group:
            group_label.set_text(f"[@.{item.group_name}]")
            group_label.set_visible(True)
        else:
            group_label.set_visible(False)

        # Mark row as actionable for visual feedback
        if self._has_action_for_item(item):
            box.add_css_class("problem-actionable")
        else:
            box.remove_css_class("problem-actionable")

        # Set tooltip with details
        if item.details:
            box.set_tooltip_text(item.details)
        else:
            box.set_tooltip_text(None)

    def _on_location_setup(self, factory, list_item):
        label = Gtk.Label(xalign=0)
        label.set_ellipsize(3)
        list_item.set_child(label)

    def _on_location_bind(self, factory, list_item):
        item: ProblemItem = list_item.get_item()
        label: Gtk.Label = list_item.get_child()
        label.set_text(item.location if item.has_location else "—")

        # Show clickable style for source actions (not glyph actions)
        action, _ = self._get_action_for_problem(item)
        if action in ("switch_source", "switch_source_by_name"):
            label.add_css_class("problem-clickable")
            # Cache cursor to avoid creating on every bind
            if self._pointer_cursor is None:
                self._pointer_cursor = Gdk.Cursor.new_from_name("pointer")
            label.set_cursor(self._pointer_cursor)
        else:
            label.remove_css_class("problem-clickable")
            label.set_cursor(None)

    # --- Sorters ---

    def _compare_severity(self, item_a: ProblemItem, item_b: ProblemItem, user_data) -> int:
        if item_a.severity < item_b.severity:
            return -1
        elif item_a.severity > item_b.severity:
            return 1
        return 0

    def _compare_category(self, item_a: ProblemItem, item_b: ProblemItem, user_data) -> int:
        if item_a.category < item_b.category:
            return -1
        elif item_a.category > item_b.category:
            return 1
        return 0

    def _compare_glyph(self, item_a: ProblemItem, item_b: ProblemItem, user_data) -> int:
        """Sort by glyph name (items without glyph go last)."""
        glyph_a = item_a.glyph_name if item_a.has_glyph else "\uffff"
        glyph_b = item_b.glyph_name if item_b.has_glyph else "\uffff"
        if glyph_a < glyph_b:
            return -1
        elif glyph_a > glyph_b:
            return 1
        return 0

    # --- Progress Box ---

    def _setup_progress_box(self) -> None:
        """Create progress overlay box."""
        self._progress_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._progress_box.set_halign(Gtk.Align.CENTER)
        self._progress_box.set_valign(Gtk.Align.CENTER)
        self._progress_box.add_css_class("card")
        self._progress_box.set_margin_top(50)
        self._progress_box.set_margin_bottom(50)
        self._progress_box.set_margin_start(50)
        self._progress_box.set_margin_end(50)

        # Make it look like a card
        inner_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        inner_box.set_margin_top(24)
        inner_box.set_margin_bottom(24)
        inner_box.set_margin_start(32)
        inner_box.set_margin_end(32)

        # Phase label at top
        self._phase_label = Gtk.Label(label="Starting check...")
        self._phase_label.add_css_class("title-4")
        inner_box.append(self._phase_label)

        # Progress bar
        self._progress_bar = Gtk.ProgressBar()
        self._progress_bar.set_size_request(300, -1)
        self._progress_bar.set_show_text(True)
        inner_box.append(self._progress_bar)

        # Timer label
        self._timer_label = Gtk.Label(label="0:00")
        self._timer_label.add_css_class("dim-label")
        self._timer_label.add_css_class("monospace")
        inner_box.append(self._timer_label)

        self._progress_box.append(inner_box)
        self._progress_box.set_visible(False)

    def _show_progress(self, show: bool) -> None:
        """Show or hide progress overlay."""
        from gi.repository import GLib

        self._progress_box.set_visible(show)
        if show:
            # Reset progress bar
            self._progress_bar.set_fraction(0.0)
            self._progress_bar.set_text("0%")
            self._phase_label.set_text("Starting check...")
            # Start timer
            self._check_start_time = time.time()
            self._timer_label.set_text("0:00")
            self._timer_source_id = GLib.timeout_add(1000, self._update_timer)
        else:
            # Stop timer
            if self._timer_source_id is not None:
                GLib.source_remove(self._timer_source_id)
                self._timer_source_id = None

    def _update_timer(self) -> bool:
        """Update timer label. Returns True to keep running."""
        elapsed = time.time() - self._check_start_time
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        self._timer_label.set_text(f"{minutes}:{seconds:02d}")
        return True  # Continue timer

    def _update_progress_bar(self, current: int, total: int, message: str) -> None:
        """Update progress bar with current/total and message."""
        if total > 0:
            fraction = current / total
            self._progress_bar.set_fraction(fraction)
            percent = int(fraction * 100)
            self._progress_bar.set_text(f"{percent}% ({current}/{total})")
        self._phase_label.set_text(message)

    # --- Status Bar ---

    def _setup_status_bar(self, parent: Gtk.Box) -> None:
        """Create status bar with total count."""
        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        parent.append(separator)

        status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        status_box.set_margin_top(6)
        status_box.set_margin_bottom(6)
        status_box.set_margin_start(12)
        status_box.set_margin_end(12)

        self._total_label = Gtk.Label(label="No problems checked yet")
        self._total_label.add_css_class("dim-label")
        status_box.append(self._total_label)

        parent.append(status_box)

    # --- Check ---

    def run_check(self) -> None:
        """Run designspace check."""
        if self._registry and self._registry.is_running:
            logger.warning("Check already running")
            return

        self._show_progress(True)
        self._model.remove_all()

        # Create registry with our DesignSpaceEntry
        self._registry = ValidatorRegistry(designspace_entry=self._designspace)
        self._registry.check_async(
            on_phase=self._on_check_phase,
            on_progress=self._on_check_progress,
            on_complete=self._on_check_complete_internal,
            on_error=self._on_check_error,
        )

    def _on_check_phase(self, phase_name: str, current: int, total: int) -> None:
        """Handle phase progress (legacy, mostly for logging)."""
        if self._destroyed:
            return
        pass  # Progress bar handles this now

    def _on_check_progress(self, current: int, total: int, message: str) -> None:
        """Handle granular progress updates."""
        if self._destroyed:
            return
        self._update_progress_bar(current, total, message)

    def _on_check_complete_internal(self, items: list[ProblemItem]) -> None:
        """Handle check completion."""
        if self._destroyed:
            return
        # Calculate elapsed time before stopping progress
        elapsed = time.time() - self._check_start_time
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        elapsed_str = f"{minutes}:{seconds:02d}" if minutes else f"{seconds}s"

        self._show_progress(False)
        self._has_results = True
        self._problems = items

        # Populate model
        for item in items:
            self._model.append(item)

        # Update summary with time
        self._update_summary(elapsed_str)

        # Enable copy button
        self._copy_btn.set_sensitive(len(items) > 0)

        # Notify callback
        if self._on_check_complete:
            self._on_check_complete(len(items))

        logger.info(f"Check complete: {len(items)} problems found in {elapsed_str}")

    def _on_check_error(self, message: str) -> None:
        """Handle check error."""
        if self._destroyed:
            return
        self._show_progress(False)
        logger.error(f"Check failed: {message}")

        # Show error in status
        self._total_label.set_text(f"Error: {message}")

    def _update_summary(self, elapsed_str: str | None = None) -> None:
        """Update summary labels with counts."""
        # Count visible items using filter state
        visible_structural = 0
        visible_design = 0
        visible_info = 0

        for p in self._problems:
            if is_problem_visible(p, self._filter_state):
                if p.severity == SEVERITY_STRUCTURAL:
                    visible_structural += 1
                elif p.severity == SEVERITY_DESIGN:
                    visible_design += 1
                else:
                    visible_info += 1

        total = len(self._problems)
        visible = visible_structural + visible_design + visible_info

        self._structural_label.set_text(f"{visible_structural} structural")
        self._design_label.set_text(f"{visible_design} design")
        self._info_label.set_text(f"{visible_info} info")

        if total == 0:
            status = "No problems found"
        elif visible == total:
            status = f"Total: {total} problems"
        else:
            status = f"Showing {visible} of {total} problems"

        # Add elapsed time if provided
        if elapsed_str:
            status += f" (checked in {elapsed_str})"

        self._total_label.set_text(status)

    def _update_filter_badge(self) -> None:
        """Update filter button to show badge when filters active."""
        if self._filter_btn is None:
            return

        disabled_count = self._filter_state.get_disabled_count()
        if disabled_count > 0:
            self._filter_btn.add_css_class("suggested-action")
            self._filter_btn.set_tooltip_text(f"Filter Problems ({disabled_count} hidden)")
        else:
            self._filter_btn.remove_css_class("suggested-action")
            self._filter_btn.set_tooltip_text("Filter Problems")

    # --- Actions ---

    def _on_recheck_clicked(self, button) -> None:
        """Handle recheck button click."""
        self.run_check()

    def _on_selection_changed(self, selection, position, n_items) -> None:
        """Handle selection change - enable/disable recheck selected button."""
        has_selection = selection.get_selection().get_size() > 0
        if self._recheck_selected_btn:
            self._recheck_selected_btn.set_sensitive(has_selection)

    def _on_recheck_selected_clicked(self, button) -> None:
        """Handle recheck selected button click."""
        self.run_check_selected()

    def _get_selected_items(self) -> list[ProblemItem]:
        """Get list of currently selected ProblemItems."""
        if self._selection is None:
            return []

        selected = []
        bitset = self._selection.get_selection()

        # GTK4 BitsetIter.init_first() returns (valid, iter, value)
        # BitsetIter.next() returns (valid, value)
        valid, iter_val, pos = Gtk.BitsetIter.init_first(bitset)
        while valid:
            item = self._selection.get_item(pos)
            if item is not None:
                selected.append(item)
            valid, pos = iter_val.next()
        return selected

    def run_check_selected(self) -> None:
        """Recheck only selected problems (glyphs)."""
        selected_items = self._get_selected_items()
        if not selected_items:
            return

        # Save scroll position
        vadj = self._scrolled_window.get_vadjustment()
        scroll_pos = vadj.get_value()

        # Collect unique glyph names from selected items
        glyph_names: set[str] = set()
        for item in selected_items:
            if item.has_glyph:
                glyph_names.add(item.glyph_name)

        if not glyph_names:
            # Show message in status bar
            self._total_label.set_text("No glyph problems in selection")
            return

        # Show progress in status bar
        glyph_list = ", ".join(sorted(glyph_names)[:3])
        if len(glyph_names) > 3:
            glyph_list += f" +{len(glyph_names) - 3} more"
        self._total_label.set_text(f"Rechecking: {glyph_list}...")

        # Disable button while checking
        if self._recheck_selected_btn:
            self._recheck_selected_btn.set_sensitive(False)

        logger.info(f"Rechecking {len(glyph_names)} glyphs")

        # Run partial check
        self._run_partial_glyph_check(glyph_names, scroll_pos)

    def _run_partial_glyph_check(self, glyph_names: set[str], scroll_pos: float) -> None:
        """
        Run check for specific glyphs only.

        Properly handles discrete axes by splitting the designspace
        and checking each sub-space separately, same as the full check.
        """
        import threading
        from pathlib import Path

        from gi.repository import GLib

        from .checkers.glyphs import GlyphsChecker
        from .model import ProblemItem

        def worker():
            try:
                new_results: list[ProblemItem] = []
                entry = self._designspace

                if entry is None or entry.doc is None:
                    GLib.idle_add(
                        self._on_partial_check_complete,
                        glyph_names,
                        new_results,
                        scroll_pos,
                    )
                    return

                # Check if we have discrete axes
                has_discrete = any(
                    hasattr(axis, "values") and axis.values for axis in entry.doc.axes
                )

                if has_discrete:
                    # Split by discrete axes and check each sub-space
                    from fontTools.designspaceLib.split import splitInterpolable

                    from font_rover.designspace import DesignSpaceEntry

                    for discrete_loc, sub_doc in splitInterpolable(entry.doc):
                        # Build set of paths in sub_doc
                        sub_doc_paths = set()
                        for source in sub_doc.sources:
                            if source.path:
                                sub_doc_paths.add(Path(source.path).resolve())

                        # Filter entry sources
                        filtered_sources = [
                            fs for fs in entry.sources if fs.path.resolve() in sub_doc_paths
                        ]

                        if len(filtered_sources) < 2:
                            continue

                        # Create filtered entry
                        filtered_entry = DesignSpaceEntry(
                            path=entry.path,
                            doc=sub_doc,
                            sources=filtered_sources,
                        )

                        # Create checker for this sub-space
                        checker = GlyphsChecker(entry=filtered_entry, doc=sub_doc)

                        # Check specified glyphs
                        for result in checker.check_glyphs(glyph_names):
                            # Add discrete location to result
                            if discrete_loc:
                                result.raw_data["discreteLocation"] = discrete_loc
                                discrete_label = self._format_discrete_location(discrete_loc)
                                if result.location:
                                    result.location = f"{result.location} [{discrete_label}]"
                                else:
                                    result.location = f"[{discrete_label}]"

                            item = ProblemItem.from_check_result(result)
                            new_results.append(item)
                else:
                    # No discrete axes - check directly
                    checker = GlyphsChecker(entry=entry)
                    for result in checker.check_glyphs(glyph_names):
                        item = ProblemItem.from_check_result(result)
                        new_results.append(item)

                # Update UI on main thread
                GLib.idle_add(
                    self._on_partial_check_complete,
                    glyph_names,
                    new_results,
                    scroll_pos,
                )

            except Exception as e:
                logger.exception(f"Partial check failed: {e}")

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def _format_discrete_location(self, loc: dict[str, float] | None) -> str:
        """Format discrete location dict as human-readable string."""
        if not loc:
            return ""
        parts = []
        for axis, value in sorted(loc.items()):
            if value == int(value):
                parts.append(f"{axis}:{int(value)}")
            else:
                parts.append(f"{axis}:{value:.1f}")
        return ", ".join(parts)

    def _on_partial_check_complete(
        self, checked_glyphs: set[str], new_results: list[ProblemItem], scroll_pos: float
    ) -> None:
        """Handle partial check completion - update model with new results."""
        if self._destroyed:
            return
        from .model import CATEGORY_GLYPHS

        # Group new results by glyph name
        new_by_glyph: dict[str, list[ProblemItem]] = {}
        for item in new_results:
            if item.glyph_name not in new_by_glyph:
                new_by_glyph[item.glyph_name] = []
            new_by_glyph[item.glyph_name].append(item)

        # Process each glyph sequentially
        old_count = 0
        for glyph_name in checked_glyphs:
            # Find current positions for this glyph (recalculate each time!)
            glyph_indices = []
            for i in range(self._model.get_n_items()):
                item = self._model.get_item(i)
                if item.category == CATEGORY_GLYPHS and item.glyph_name == glyph_name:
                    glyph_indices.append(i)

            if not glyph_indices:
                continue

            old_count += len(glyph_indices)
            insert_pos = glyph_indices[0]  # Position to insert new items

            # Remove old items for this glyph (reverse order)
            for i in reversed(glyph_indices):
                self._model.remove(i)

            # Insert new items at the same position
            new_items = new_by_glyph.get(glyph_name, [])
            for j, item in enumerate(new_items):
                self._model.insert(insert_pos + j, item)

        # Update internal problems list
        self._problems = [self._model.get_item(i) for i in range(self._model.get_n_items())]

        # Calculate fixed count
        fixed_count = old_count - len(new_results)

        # Update summary with recheck info
        self._update_summary()

        # Show result in status bar
        if fixed_count > 0:
            status = f"Fixed {fixed_count} problems"
            if len(new_results) > 0:
                status += f", {len(new_results)} remaining"
        elif len(new_results) == old_count:
            status = f"No changes ({len(new_results)} problems)"
        else:
            status = f"{len(new_results)} problems found"
        self._total_label.set_text(status)

        # Scroll to first remaining item for checked glyphs (if any)
        def scroll_to_checked():
            if self._destroyed:
                return False
            if not new_results:
                # No remaining problems - restore original scroll
                vadj = self._scrolled_window.get_vadjustment()
                vadj.set_value(scroll_pos)
                return False

            # Find position of first checked glyph in filtered model
            first_glyph = new_results[0].glyph_name
            for i in range(self._filter_model.get_n_items()):
                item = self._filter_model.get_item(i)
                if item.glyph_name == first_glyph:
                    # Scroll to this row
                    self._column_view.scroll_to(i, None, Gtk.ListScrollFlags.FOCUS, None)
                    return False
            return False

        from gi.repository import GLib

        GLib.idle_add(scroll_to_checked)

        # Re-enable recheck selected button if there's still selection
        if self._recheck_selected_btn and self._selection:
            has_selection = self._selection.get_selection().get_size() > 0
            self._recheck_selected_btn.set_sensitive(has_selection)

        # Log result
        logger.info(
            f"Partial recheck: {old_count} checked, {fixed_count} fixed, {len(new_results)} remaining"
        )

    def _on_filter_changed(self, popover: FilterPopover) -> None:
        """Handle filter state change from popover."""
        self._filter_state = popover.get_filter_state()

        # Update filter
        if self._problem_filter:
            self._problem_filter.set_filter_state(self._filter_state)

        # Update summary to show visible/total
        self._update_summary()

        # Update filter button badge
        self._update_filter_badge()

    def _on_row_activated(self, column_view, position) -> None:
        """Handle row double-click."""
        item = self._selection.get_item(position)
        if item is None:
            return

        action, data = self._get_action_for_problem(item)

        if action == "fix":
            from .fixes import get_fix

            fix = get_fix(item)
            if fix is not None:
                fix(self, item)
        elif action == "open_glyph":
            self._action_open_glyph(data, item, column_view)
        elif action == "switch_source":
            self._action_switch_source_by_path(data)
        elif action == "switch_source_by_name":
            self._action_switch_source_by_name(data)

    def _get_action_for_problem(self, item: ProblemItem) -> tuple[str, Any]:
        """Determine action for problem item."""
        # Auto-fix takes precedence over navigation when available.
        from .fixes import get_fix

        if get_fix(item) is not None:
            return ("fix", None)

        # Glyph problems: open glyph
        if item.has_glyph:
            return ("open_glyph", item.glyph_name)

        # Source path: switch source
        if item.raw_data.get("path"):
            return ("switch_source", item.raw_data["path"])

        # Font name: switch source
        if item.raw_data.get("font"):
            return ("switch_source_by_name", item.raw_data["font"])

        return ("none", None)

    def _has_action_for_item(self, item: ProblemItem) -> bool:
        """Check if problem item has a navigation action."""
        action, _ = self._get_action_for_problem(item)
        return action != "none"

    def _action_open_glyph(
        self,
        glyph_name: str,
        item: ProblemItem,
        anchor_widget: Gtk.Widget | None = None,
    ) -> None:
        """
        Navigate to glyph in grid and open it in the glyph editor.

        If the problem has source location info:
        - Single source: switch to it and open
        - Multiple sources: show picker popover

        Otherwise falls back to current source or first available.
        """
        if self._editor_window is None:
            return

        from gi.repository import GLib

        # Check if we have source location info from raw_data
        source_groups = self._get_source_groups_from_item(item)
        all_sources = self._get_all_sources_from_item(item)

        if all_sources:
            if len(all_sources) == 1:
                # Single source - switch directly
                self._switch_to_source_and_open_glyph(all_sources[0], glyph_name)
                return
            elif len(all_sources) > 1 and anchor_widget is not None:
                # Multiple sources - show picker
                try:
                    self._show_source_picker_popover(item, source_groups, anchor_widget)
                except Exception as e:
                    logger.exception(f"Error showing source picker: {e}")
                return

        # Fallback: Handle discrete location if present (for problems without source groups)
        discrete_loc_data = item.raw_data.get("discreteLocation")
        if discrete_loc_data:
            # Can be dict (from glyphOrder check) or string (from other checks)
            if isinstance(discrete_loc_data, dict):
                discrete_loc = discrete_loc_data
            else:
                discrete_loc = self._parse_discrete_location(discrete_loc_data)
            source_idx = self._find_source_for_discrete_location(discrete_loc)
            if source_idx is not None:
                self._editor_window._switch_to_source(source_idx)
                self._open_glyph_editor(glyph_name)
                return

        # Fallback: check if glyph exists in current source
        current_font = getattr(self._editor_window, "_font", None)
        if current_font is not None and glyph_name in current_font:
            if hasattr(self._editor_window, "grid_component"):
                self._editor_window.grid_component.scroll_to_glyph(glyph_name)
            self._open_glyph_editor(glyph_name)
            return

        # Glyph doesn't exist in current source - find first source that has it
        glyph_order_mgr = getattr(self._editor_window, "_glyph_order_manager", None)
        if glyph_order_mgr is not None:
            source_idx = glyph_order_mgr.find_first_source_with_glyph(glyph_name)
            if source_idx is not None:
                logger.info(
                    f"Glyph '{glyph_name}' not in current source, switching to source {source_idx}"
                )
                self._editor_window._switch_to_source(source_idx)
                if hasattr(self._editor_window, "grid_component"):
                    # Must return False to prevent GLib from re-calling
                    def do_scroll(g=glyph_name):
                        if not self._destroyed and self._editor_window:
                            self._editor_window.grid_component.scroll_to_glyph(g)
                        return False

                    def do_open(g=glyph_name):
                        if not self._destroyed:
                            self._open_glyph_editor(g)
                        return False

                    GLib.idle_add(do_scroll)
                    GLib.idle_add(do_open)
            else:
                logger.warning(f"Glyph '{glyph_name}' not found in any source")

    def _action_switch_source_by_path(self, path_str: str) -> None:
        """Switch to source by UFO path."""
        if self._editor_window is None:
            return

        idx = self._find_source_index_by_path(path_str)
        if idx is not None:
            self._editor_window._switch_to_source(idx)

    def _action_switch_source_by_name(self, font_name: str) -> None:
        """Switch to source by font name."""
        if self._editor_window is None:
            return

        idx = self._find_source_index_by_name(font_name)
        if idx is not None:
            self._editor_window._switch_to_source(idx)

    def _open_glyph_editor(self, glyph_name: str) -> None:
        """Open glyph in the glyph editor window."""
        if self._destroyed or self._editor_window is None:
            return

        window_manager = getattr(self._editor_window, "_window_manager", None)
        if window_manager is not None:
            window_manager.open_glyph_editor(glyph_name, force_new=False)
        else:
            logger.warning("Cannot open glyph editor: no WindowManager available")

    # --- Source Finding ---

    def _find_source_index_by_path(self, path_str: str) -> int | None:
        """Find source index by UFO path."""
        path = Path(path_str)
        for idx, source in enumerate(self._designspace.sources):
            if source.path == path or source.path.name == path.name:
                return idx
        return None

    def _find_source_index_by_name(self, font_name: str) -> int | None:
        """Find source index by font name (Family Style)."""
        for idx, source in enumerate(self._designspace.sources):
            tooltip = source.get_tooltip()
            if tooltip == font_name:
                return idx
            # Also try just style name
            if source.style_name and font_name.endswith(source.style_name):
                return idx
        return None

    def _parse_discrete_location(self, loc_str: str) -> dict:
        """Parse discrete location string to dict."""
        result = {}
        for part in loc_str.split(", "):
            if ":" in part:
                axis, value = part.split(":", 1)
                try:
                    result[axis.strip()] = float(value.strip())
                except ValueError:
                    pass
        return result

    def _find_source_for_discrete_location(self, discrete_loc: dict) -> int | None:
        """Find default source for discrete location."""
        if not self._designspace or not self._designspace.doc:
            return None

        try:
            default_loc = self._designspace.doc.newDefaultLocation()
        except Exception:
            return None

        for idx, source in enumerate(self._designspace.sources):
            # Check discrete axes match
            matches_discrete = all(
                source.location.get(axis) == value for axis, value in discrete_loc.items()
            )
            if not matches_discrete:
                continue

            # Check continuous axes are at default
            is_default = all(
                source.location.get(axis) == default_loc.get(axis)
                for axis in default_loc
                if axis not in discrete_loc
            )
            if is_default:
                return idx

        # Fallback: first source matching discrete location
        for idx, source in enumerate(self._designspace.sources):
            matches_discrete = all(
                source.location.get(axis) == value for axis, value in discrete_loc.items()
            )
            if matches_discrete:
                return idx

        return None

    # --- Source Picker ---

    def _get_source_groups_from_item(self, item: ProblemItem) -> list[dict]:
        """
        Extract source groups from problem item's raw_data.

        Returns list of dicts: [{"label": "value", "sources": ["src1", "src2"]}, ...]
        """
        raw = item.raw_data
        loc_type = raw.get("locationType")

        if loc_type == "binary":
            groups = []
            present = raw.get("presentIn", [])
            missing = raw.get("missingIn", [])
            if present:
                groups.append({"label": "has", "sources": present})
            if missing:
                groups.append({"label": "missing", "sources": missing})
            return groups

        elif loc_type == "groups":
            return [
                {"label": label, "sources": sources}
                for label, sources in raw.get("groups", {}).items()
            ]

        elif loc_type == "differs":
            differs = raw.get("differsIn", [])
            if differs:
                return [{"label": "differs", "sources": differs}]

        return []

    def _get_all_sources_from_item(self, item: ProblemItem) -> list[str]:
        """Get flat list of all sources from item's raw_data."""
        groups = self._get_source_groups_from_item(item)
        all_sources = []
        for group in groups:
            all_sources.extend(group.get("sources", []))
        return all_sources

    def _show_source_picker_popover(
        self,
        item: ProblemItem,
        source_groups: list[dict],
        anchor_widget: Gtk.Widget,
    ) -> None:
        """
        Show popover for selecting which source to open.

        Args:
            item: The problem item
            source_groups: List of {"label": str, "sources": [str, ...]}
            anchor_widget: Widget to anchor popover to
        """
        total_sources = sum(len(g.get("sources", [])) for g in source_groups)

        # Use Adw.AlertDialog for reliable centering
        dialog = Adw.AlertDialog()
        dialog.set_heading(f"Select source for {item.glyph_name}")
        dialog.set_body(item.description)

        # Main content
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        content_box.set_margin_top(12)
        content_box.set_margin_bottom(12)
        content_box.set_margin_start(12)
        content_box.set_margin_end(12)

        # Radio button group
        radio_group = None
        selected_source = [None]  # Use list to allow modification in closure

        # Sort groups: smaller groups first (likely outliers/errors)
        sorted_groups = sorted(source_groups, key=lambda g: len(g.get("sources", [])))

        for group in sorted_groups:
            label = group.get("label", "")
            sources = group.get("sources", [])

            if not sources:
                continue

            # Group label
            group_label = Gtk.Label(
                label=f"<b>{label}</b> ({len(sources)}):",
                use_markup=True,
                xalign=0,
            )
            group_label.set_margin_top(8)
            content_box.append(group_label)

            # Limit displayed sources per group if too many
            max_display = 10 if len(sources) > 15 else len(sources)
            display_sources = sources[:max_display]

            # Radio buttons for each source
            for source_name in display_sources:
                display_name = source_name.replace(".ufo", "")
                radio = Gtk.CheckButton(label=display_name)
                radio.set_margin_start(12)

                if radio_group is None:
                    radio_group = radio
                    radio.set_active(True)
                    selected_source[0] = source_name
                else:
                    radio.set_group(radio_group)

                def on_toggled(btn, src=source_name):
                    if btn.get_active():
                        selected_source[0] = src

                radio.connect("toggled", on_toggled)
                content_box.append(radio)

            # Show "and N more" if truncated
            if len(sources) > max_display:
                more_label = Gtk.Label(
                    label=f"    <i>...and {len(sources) - max_display} more</i>",
                    use_markup=True,
                    xalign=0,
                )
                more_label.add_css_class("dim-label")
                content_box.append(more_label)

        # Put content in scrolled window if large
        if total_sources > 15:
            scrolled = Gtk.ScrolledWindow()
            scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            scrolled.set_min_content_height(100)
            scrolled.set_max_content_height(300)
            scrolled.set_propagate_natural_height(True)
            scrolled.set_child(content_box)
            dialog.set_extra_child(scrolled)
        else:
            dialog.set_extra_child(content_box)

        # Add buttons
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("open", "Open")
        dialog.set_response_appearance("open", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("open")
        dialog.set_close_response("cancel")

        def on_response(dlg, response):
            if response == "open" and selected_source[0]:
                self._switch_to_source_and_open_glyph(selected_source[0], item.glyph_name)

        dialog.connect("response", on_response)
        dialog.present(self)

    # =========================================================================
    # Discrete-axis introspection helpers (used by fixes.py and locally)
    # =========================================================================

    def _collect_sources_in_discrete(self, discrete_loc: dict | None) -> list[tuple[int, Any]]:
        """Return [(source_index, FontSource), ...] in DS order, scoped to a
        discrete-axis location.

        ``discrete_loc`` is the dict carried by the problem's raw_data; when
        the designspace has no discrete axes it will be ``{}`` or ``None`` and
        every source matches.
        """
        result: list[tuple[int, Any]] = []
        loc = discrete_loc or {}
        for idx, fs in enumerate(self._designspace.sources):
            fs_loc = getattr(fs, "location", None) or {}
            if loc and not all(fs_loc.get(k) == v for k, v in loc.items()):
                continue
            result.append((idx, fs))
        return result

    def _find_default_source_idx_for_discrete(self, discrete_loc: dict | None) -> int | None:
        """Find the default source index for a given discrete location.

        Uses fontTools' ``splitInterpolable`` so the answer matches whatever
        the validator and the GlyphOrderManager use.
        """
        if not self._designspace or not self._designspace.doc:
            return None
        try:
            from fontTools.designspaceLib.split import splitInterpolable
        except Exception:
            return None

        target = discrete_loc or {}
        for sub_loc, sub_doc in splitInterpolable(self._designspace.doc):
            if (sub_loc or {}) != target:
                continue
            default_desc = sub_doc.findDefault()
            if default_desc is None or default_desc.path is None:
                return None
            for idx, fs in enumerate(self._designspace.sources):
                if (
                    str(fs.path) == default_desc.path
                    or fs.path.name == Path(default_desc.path).name
                ):
                    return idx
            return None
        return None

    def _show_info_toast(self, text: str) -> None:
        """Show an informational toast if a toast overlay is available."""
        overlay = getattr(self, "_toast_overlay", None)
        if overlay is None:
            logger.info(text)
            return
        toast = Adw.Toast.new(text)
        toast.set_timeout(4)
        overlay.add_toast(toast)

    def _show_error_toast(self, text: str) -> None:
        """Show an error toast (longer timeout)."""
        overlay = getattr(self, "_toast_overlay", None)
        if overlay is None:
            logger.warning(text)
            return
        toast = Adw.Toast.new(text)
        toast.set_timeout(7)
        overlay.add_toast(toast)

    def _switch_to_source_and_open_glyph(self, source_name: str, glyph_name: str) -> None:
        """Switch to source by name and open glyph editor."""
        if self._destroyed or self._editor_window is None:
            return

        from gi.repository import GLib

        # Find source index by name
        idx = None
        for i, source in enumerate(self._designspace.sources):
            if source.path.name == source_name:
                idx = i
                break

        if idx is not None:
            self._editor_window._switch_to_source(idx)
            # Scroll and open after source switch (must return False)
            if hasattr(self._editor_window, "grid_component"):

                def do_scroll(g=glyph_name):
                    if not self._destroyed and self._editor_window:
                        self._editor_window.grid_component.scroll_to_glyph(g)
                    return False

                GLib.idle_add(do_scroll)

            def do_open(g=glyph_name):
                if not self._destroyed:
                    self._open_glyph_editor(g)
                return False

            GLib.idle_add(do_open)
        else:
            logger.warning(f"Source '{source_name}' not found in designspace")

    # --- Copy Report ---

    def _on_copy_clicked(self, button: Gtk.Button) -> None:
        """Copy problems report to clipboard."""
        report = self._generate_report()
        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.set(report)
        logger.info("Copied problems report to clipboard")

    def _generate_report(self) -> str:
        """Generate text report of problems."""
        lines = []

        # Header
        lines.append("=== DesignSpace Problems Report ===")
        lines.append(str(self._designspace.path))
        lines.append(f"{len(self._problems)} problems found")
        lines.append("")

        # Collect unique glyphs and groups
        glyphs: set[str] = set()
        groups: set[str] = set()
        other_problems: list[str] = []

        for item in self._problems:
            if item.has_glyph:
                glyphs.add(item.glyph_name)
            if item.has_group:
                groups.add(item.group_name)

            # Collect "other" problems (unique descriptions with location)
            if not item.has_glyph and not item.has_group:
                desc = f"[{item.category_name}] {item.description}"
                if item.has_location:
                    desc += f" — {item.location}"
                if desc not in other_problems:
                    other_problems.append(desc)

        # Glyphs section
        if glyphs:
            sorted_glyphs = sorted(glyphs)
            lines.append(f"--- Problematic Glyphs ({len(sorted_glyphs)}) ---")
            lines.append(" ".join(f"/{g}" for g in sorted_glyphs))
            lines.append("")

        # Groups section
        if groups:
            sorted_groups = sorted(groups)
            lines.append(f"--- Problematic Groups ({len(sorted_groups)}) ---")
            lines.append(" ".join(f"@{g}" for g in sorted_groups))
            lines.append("")

        # Other problems section
        if other_problems:
            lines.append(f"--- Other Problems ({len(other_problems)}) ---")
            for problem in other_problems:
                lines.append(f"• {problem}")
            lines.append("")

        return "\n".join(lines)

    # --- Settings ---

    def _load_settings(self) -> None:
        """Load settings."""
        if self._settings is None:
            return

        width = self._settings.get(f"{_SETTINGS_PREFIX}.width", default=750)
        height = self._settings.get(f"{_SETTINGS_PREFIX}.height", default=500)
        self.set_default_size(width, height)

        # Load filter state
        filter_data = self._settings.get(f"{_SETTINGS_PREFIX}.filters", default=None)
        if filter_data and isinstance(filter_data, dict):
            self._filter_state = FilterState.from_dict(filter_data)
            if self._filter_popover:
                self._filter_popover.set_filter_state(self._filter_state)
            if self._problem_filter:
                self._problem_filter.set_filter_state(self._filter_state)
            self._update_filter_badge()

    def _save_settings(self) -> None:
        """Save settings."""
        if self._settings is None:
            return

        self._settings.set(f"{_SETTINGS_PREFIX}.width", self.get_width())
        self._settings.set(f"{_SETTINGS_PREFIX}.height", self.get_height())

        # Save filter state
        self._settings.set(f"{_SETTINGS_PREFIX}.filters", self._filter_state.to_dict())

    # --- Lifecycle ---

    def do_close_request(self) -> bool:
        """Handle window close - hide instead of destroy."""
        # Allow destroy if cleanup() was called
        if self._force_close:
            return False

        self._save_settings()
        # Stop timer if running
        if self._timer_source_id is not None:
            GLib.source_remove(self._timer_source_id)
            self._timer_source_id = None
        # Cancel any running validation
        if self._registry is not None:
            self._registry.cancel()
        self.hide()
        return True  # Prevent destroy

    def cleanup(self) -> None:
        """
        Clean up resources before window is destroyed.

        Call this when the parent window is closing to ensure
        all timers and references are released.
        """
        # Mark as destroyed to prevent callbacks from running
        self._destroyed = True
        # Allow do_close_request to permit destroy
        self._force_close = True

        # Stop timer
        if self._timer_source_id is not None:
            GLib.source_remove(self._timer_source_id)
            self._timer_source_id = None

        # Cancel any running validation
        if self._registry is not None:
            self._registry.cancel()

        # Clear references
        self._editor_window = None
        self._registry = None
        self._designspace = None
        self._problems.clear()

        # Clear model to release ProblemItems
        if self._model is not None:
            self._model.remove_all()

        # Unregister from application to allow app to quit
        self.set_application(None)
