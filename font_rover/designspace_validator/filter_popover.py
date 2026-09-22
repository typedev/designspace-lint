"""
FilterPopover for DesignSpace validator problem filtering.

Provides a hierarchical UI for enabling/disabling problem categories
and subcategories using Adw.ExpanderRow and Adw.ActionRow.

Copyright 2024-2026 TypeDev
Licensed under the Apache License, Version 2.0
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GObject, Gtk

from .filter_config import (
    FILTER_GROUPS,
    FilterState,
    get_all_categories,
    get_category_name,
)


class FilterPopover(Gtk.Popover):
    """
    Popover for filtering validator problems by category and subcategory.

    Uses Adw.ExpanderRow for categories with subcategories and
    Adw.ActionRow for single-group categories - they align automatically.

    Signals:
        filter-changed: Emitted when any filter checkbox changes
    """

    __gtype_name__ = "FilterPopover"

    __gsignals__ = {
        "filter-changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self):
        super().__init__()

        self._state = FilterState()
        self._updating = False  # Prevent recursive updates

        # Category row widgets and their checkboxes
        self._category_checks: dict[int, Gtk.CheckButton] = {}
        self._group_checks: dict[int, dict[str, Gtk.CheckButton]] = {}

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the popover UI."""
        # Main container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Header with buttons
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header_box.set_margin_top(12)
        header_box.set_margin_bottom(8)
        header_box.set_margin_start(12)
        header_box.set_margin_end(12)

        title_label = Gtk.Label(label="Filter")
        title_label.add_css_class("heading")
        title_label.set_hexpand(True)
        title_label.set_xalign(0)
        header_box.append(title_label)

        # Select All button
        all_btn = Gtk.Button(label="All")
        all_btn.add_css_class("flat")
        all_btn.set_tooltip_text("Enable all filters")
        all_btn.connect("clicked", self._on_select_all)
        header_box.append(all_btn)

        # Select None button
        none_btn = Gtk.Button(label="None")
        none_btn.add_css_class("flat")
        none_btn.set_tooltip_text("Disable all filters")
        none_btn.connect("clicked", self._on_select_none)
        header_box.append(none_btn)

        main_box.append(header_box)

        # Scrolled area for categories
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_min_content_height(300)
        scrolled.set_max_content_height(450)
        scrolled.set_propagate_natural_height(True)

        # ListBox for rows (Adw rows align automatically in ListBox)
        self._listbox = Gtk.ListBox()
        self._listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self._listbox.add_css_class("boxed-list")
        self._listbox.set_margin_start(8)
        self._listbox.set_margin_end(8)
        self._listbox.set_margin_bottom(8)

        # Add each category
        for category in get_all_categories():
            row = self._create_category_row(category)
            self._listbox.append(row)

        scrolled.set_child(self._listbox)
        main_box.append(scrolled)

        # Footer with Reset button
        footer_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        footer_box.set_margin_top(8)
        footer_box.set_margin_bottom(8)
        footer_box.set_margin_start(12)

        reset_btn = Gtk.Button(label="Reset to Defaults")
        reset_btn.add_css_class("flat")
        reset_btn.connect("clicked", self._on_reset)
        footer_box.append(reset_btn)

        main_box.append(footer_box)

        self.set_child(main_box)

    def _create_category_row(self, category: int) -> Gtk.Widget:
        """Create row for a category - ExpanderRow or ActionRow."""
        groups = FILTER_GROUPS.get(category, [])
        category_name = get_category_name(category)

        # Single group: use ActionRow (no expansion needed)
        if len(groups) == 1:
            return self._create_action_row(category, groups[0], category_name)

        # Multiple groups: use ExpanderRow
        return self._create_expander_row(category, groups, category_name)

    def _create_action_row(
        self, category: int, group_info: tuple, category_name: str
    ) -> Adw.ActionRow:
        """Create ActionRow for category with single group."""
        group_id, _, _, tooltip = group_info

        row = Adw.ActionRow()
        row.set_title(category_name)
        if tooltip:
            row.set_subtitle(tooltip)

        # Checkbox as suffix (right side)
        check = Gtk.CheckButton()
        check.set_active(True)
        check.set_valign(Gtk.Align.CENTER)
        check.connect("toggled", self._on_group_toggled, category, group_id)
        row.add_suffix(check)

        # Make row activatable to toggle checkbox
        row.set_activatable_widget(check)

        # Store references
        self._category_checks[category] = check
        self._group_checks[category] = {group_id: check}

        return row

    def _create_expander_row(
        self, category: int, groups: list, category_name: str
    ) -> Adw.ExpanderRow:
        """Create ExpanderRow for category with multiple groups."""
        row = Adw.ExpanderRow()
        row.set_title(category_name)
        row.set_subtitle(f"{len(groups)} subcategories")

        # Category checkbox as suffix
        category_check = Gtk.CheckButton()
        category_check.set_active(True)
        category_check.set_valign(Gtk.Align.CENTER)
        category_check.connect("toggled", self._on_category_toggled, category)
        row.add_suffix(category_check)
        self._category_checks[category] = category_check

        # Add subcategory rows
        self._group_checks[category] = {}

        for group_id, group_name, _, tooltip in groups:
            sub_row = Adw.ActionRow()
            sub_row.set_title(group_name)
            if tooltip:
                sub_row.set_subtitle(tooltip)

            # Checkbox for subcategory
            check = Gtk.CheckButton()
            check.set_active(True)
            check.set_valign(Gtk.Align.CENTER)
            check.connect("toggled", self._on_group_toggled, category, group_id)
            sub_row.add_suffix(check)
            sub_row.set_activatable_widget(check)

            self._group_checks[category][group_id] = check
            row.add_row(sub_row)

        return row

    # --- Event Handlers ---

    def _on_category_toggled(self, check: Gtk.CheckButton, category: int) -> None:
        """Handle category checkbox toggle."""
        if self._updating:
            return

        enabled = check.get_active()
        self._state.set_category_enabled(category, enabled)

        # Update all group checkboxes in this category
        self._updating = True
        if category in self._group_checks:
            for group_check in self._group_checks[category].values():
                group_check.set_active(enabled)
        self._updating = False

        self.emit("filter-changed")

    def _on_group_toggled(self, check: Gtk.CheckButton, category: int, group_id: str) -> None:
        """Handle group checkbox toggle."""
        if self._updating:
            return

        enabled = check.get_active()
        self._state.set_enabled(category, group_id, enabled)

        # Update category checkbox state (checked, unchecked, or inconsistent)
        self._update_category_check_state(category)

        self.emit("filter-changed")

    def _update_category_check_state(self, category: int) -> None:
        """Update category checkbox based on group states."""
        if category not in self._category_checks:
            return

        # Check if this is a single-group category (same checkbox)
        groups = FILTER_GROUPS.get(category, [])
        if len(groups) == 1:
            return  # Same checkbox, no need to sync

        self._updating = True
        category_check = self._category_checks[category]

        if self._state.is_category_enabled(category):
            category_check.set_active(True)
            category_check.set_inconsistent(False)
        elif self._state.is_category_partially_enabled(category):
            category_check.set_active(False)
            category_check.set_inconsistent(True)
        else:
            category_check.set_active(False)
            category_check.set_inconsistent(False)

        self._updating = False

    def _on_select_all(self, button: Gtk.Button) -> None:
        """Enable all filters."""
        self._updating = True
        self._state.reset_to_defaults()
        self._sync_ui_from_state()
        self._updating = False
        self.emit("filter-changed")

    def _on_select_none(self, button: Gtk.Button) -> None:
        """Disable all filters."""
        self._updating = True
        for category in get_all_categories():
            self._state.set_category_enabled(category, False)
        self._sync_ui_from_state()
        self._updating = False
        self.emit("filter-changed")

    def _on_reset(self, button: Gtk.Button) -> None:
        """Reset to default state (all enabled)."""
        self._on_select_all(button)

    def _sync_ui_from_state(self) -> None:
        """Sync all checkboxes from current state."""
        for category in get_all_categories():
            # Update group checkboxes
            if category in self._group_checks:
                for group_id, check in self._group_checks[category].items():
                    check.set_active(self._state.is_enabled(category, group_id))

            # Update category checkbox
            self._update_category_check_state(category)

    # --- Public API ---

    def get_filter_state(self) -> FilterState:
        """Get current filter state."""
        return self._state

    def set_filter_state(self, state: FilterState) -> None:
        """Set filter state and update UI."""
        self._state = state
        self._updating = True
        self._sync_ui_from_state()
        self._updating = False
