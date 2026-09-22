"""
Auto-fix actions for DesignSpace validation problems.

Each fix is a function ``fix_xxx(window, item)`` where:
- ``window`` is the :class:`ProblemsWindow` (provides ``_designspace``,
  ``_editor_window``, source-introspection helpers, toasts, and ``run_check``).
- ``item`` is the :class:`ProblemItem` describing the problem to fix.

The :data:`FIXES` dispatch table maps ``(category, error_code)`` to a fix
function. Use :func:`get_fix` from the row-activation handler to find the
fix for a given problem.

Add a new fix by writing a function and registering it in :data:`FIXES`.

Copyright 2024-2026 TypeDev
Licensed under the Apache License, Version 2.0
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable

from gi.repository import Adw, GLib, Gtk

from font_rover.utils.glyph_order import safe_glyph_order

from .checkers.features import FEATURES_DIFFER_FROM_DEFAULT
from .checkers.glyphorder import GLYPHORDER_POSITION_MISMATCH
from .checkers.kerning import KERNING_GROUP_SORTED_DIFF
from .model import CATEGORY_FEATURES, CATEGORY_GLYPHORDER, CATEGORY_KERNING

if TYPE_CHECKING:
    from .model import ProblemItem
    from .window import ProblemsWindow

logger = logging.getLogger(__name__)

FixFn = Callable[["ProblemsWindow", "ProblemItem"], None]


# =============================================================================
# Fix: sync glyphOrder from reference master  (9, GLYPHORDER_POSITION_MISMATCH)
# =============================================================================


def fix_sync_glyph_order(window: "ProblemsWindow", item: "ProblemItem") -> None:
    """Open the reference picker for a GLYPHORDER_POSITION_MISMATCH item."""
    if window._editor_window is None or window._designspace is None:
        return

    manager = getattr(window._editor_window, "_glyph_order_manager", None)
    if manager is None:
        logger.warning("Cannot sync glyphOrder: editor window has no manager")
        return

    try:
        _show_glyph_order_picker(window, item, manager)
    except Exception as e:
        logger.exception(f"Error showing sync reference picker: {e}")


def _show_glyph_order_picker(window: "ProblemsWindow", item: "ProblemItem", manager) -> None:
    """Show Adw.AlertDialog to pick a reference master for glyphOrder sync.

    Lists every source in the same discrete-axis location as the problem.
    Each row shows the UFO filename plus a count of physical / template /
    total entries. The discrete-location's default source is preselected
    and tagged "(default)".
    """
    discrete_loc = item.raw_data.get("discreteLocation") or {}
    sources_in_discrete = window._collect_sources_in_discrete(discrete_loc)
    if len(sources_in_discrete) < 2:
        logger.info("Sync picker: fewer than 2 sources in discrete location")
        return

    default_idx = window._find_default_source_idx_for_discrete(discrete_loc)

    dialog = Adw.AlertDialog()
    loc_label = window._format_discrete_location(discrete_loc) if discrete_loc else ""
    if loc_label:
        dialog.set_heading(f"Sync glyphOrder from reference master ({loc_label})")
    else:
        dialog.set_heading("Sync glyphOrder from reference master")
    dialog.set_body(
        "All other masters in this discrete-axis location will be aligned "
        "to the reference's glyphOrder. Physical glyphs unique to a target "
        "are appended at the end; template entries unique to a target are "
        "removed."
    )

    content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    content_box.set_margin_top(12)
    content_box.set_margin_bottom(12)
    content_box.set_margin_start(12)
    content_box.set_margin_end(12)

    radio_group = None
    selected_ref_idx: list[int | None] = [None]

    for source_idx, fs in sources_in_discrete:
        font = fs.font
        order = safe_glyph_order(font)
        physical = set(font.keys())
        template_count = sum(1 for n in order if n not in physical)
        counts = f"({len(physical)} physical · {template_count} template · {len(order)} total)"
        display_name = fs.path.name.removesuffix(".ufo")
        is_default = source_idx == default_idx

        label_markup = (
            f"<b>{GLib.markup_escape_text(display_name)}</b>"
            + (" <i>(default)</i>" if is_default else "")
            + f"   <span alpha='65%'>{GLib.markup_escape_text(counts)}</span>"
        )
        radio = Gtk.CheckButton()
        radio.set_margin_start(4)

        inner = Gtk.Label(label=label_markup, use_markup=True, xalign=0)
        inner.set_margin_start(4)
        radio.set_child(inner)

        if radio_group is None:
            radio_group = radio
        else:
            radio.set_group(radio_group)

        preselect = (default_idx is not None and is_default) or (
            default_idx is None and selected_ref_idx[0] is None
        )
        if preselect and selected_ref_idx[0] is None:
            radio.set_active(True)
            selected_ref_idx[0] = source_idx

        def on_toggled(btn, idx=source_idx):
            if btn.get_active():
                selected_ref_idx[0] = idx

        radio.connect("toggled", on_toggled)
        content_box.append(radio)

    if len(sources_in_discrete) > 8:
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_min_content_height(120)
        scrolled.set_max_content_height(360)
        scrolled.set_propagate_natural_height(True)
        scrolled.set_child(content_box)
        dialog.set_extra_child(scrolled)
    else:
        dialog.set_extra_child(content_box)

    dialog.add_response("cancel", "Cancel")
    dialog.add_response("sync", "Sync")
    dialog.set_response_appearance("sync", Adw.ResponseAppearance.SUGGESTED)
    dialog.set_default_response("sync")
    dialog.set_close_response("cancel")

    def on_response(dlg, response):
        if response == "sync" and selected_ref_idx[0] is not None:
            _apply_glyph_order_sync(window, selected_ref_idx[0], discrete_loc, manager)

    dialog.connect("response", on_response)
    dialog.present(window)


def _apply_glyph_order_sync(
    window: "ProblemsWindow",
    ref_idx: int,
    discrete_loc: dict | None,
    manager,
) -> None:
    """Run sync_from_reference and refresh editor + validator state."""
    try:
        result = manager.sync_from_reference(ref_idx, discrete_loc or None)
    except (IndexError, ValueError) as e:
        logger.exception(f"sync_from_reference failed: {e}")
        window._show_error_toast(f"Sync failed: {e}")
        return

    changed = result.get("changed", [])
    skipped = result.get("skipped", [])
    logger.info(
        f"sync_from_reference applied: ref_idx={ref_idx}, "
        f"discrete={discrete_loc}, changed={changed}, skipped={skipped}"
    )

    # Mark editor dirty if anything actually changed and notify the grid.
    if changed and window._editor_window is not None:
        if hasattr(window._editor_window, "_mark_dirty"):
            window._editor_window._mark_dirty()
        wm = getattr(window._editor_window, "_window_manager", None)
        if wm is not None:
            from font_rover.event_config import EVENT_GLYPHS_REORDERED

            # Send the unified order from the reference so listeners
            # (grid, etc.) can refresh from a stable source of truth.
            ref_source = window._designspace.sources[ref_idx]
            ref_order = safe_glyph_order(ref_source.font)
            wm.event_bus.publish(EVENT_GLYPHS_REORDERED, {"new_order": ref_order})

    if not changed:
        window._show_info_toast("All masters were already in sync")
    else:
        window._show_info_toast(f"Synced {len(changed)} master(s) — review and save UFOs")

    window.run_check()


# =============================================================================
# Fix: sort kerning group members  (5, KERNING_GROUP_SORTED_DIFF)
# =============================================================================


def fix_sort_kerning_groups(window: "ProblemsWindow", item: "ProblemItem") -> None:
    """Pick a reference master, then align member order of all
    sorted-only-diff kerning groups in the same discrete-axis subspace.
    """
    if window._editor_window is None or window._designspace is None:
        return

    discrete_loc = item.raw_data.get("discreteLocation") or {}
    sources_in_discrete = window._collect_sources_in_discrete(discrete_loc)
    if len(sources_in_discrete) < 2:
        logger.info("Group sort fix: fewer than 2 sources in discrete location")
        return

    affected = _collect_sorted_diff_problems(window, discrete_loc)
    if not affected:
        logger.info("Group sort fix: no SORTED_DIFF problems in subspace")
        return

    try:
        _show_group_sort_picker(window, sources_in_discrete, discrete_loc, affected)
    except Exception as e:
        logger.exception(f"Error showing group sort picker: {e}")


def _collect_sorted_diff_problems(
    window: "ProblemsWindow", discrete_loc: dict | None
) -> list["ProblemItem"]:
    """Return SORTED_DIFF kerning problems sharing the given discrete location."""
    target = discrete_loc or {}
    out: list["ProblemItem"] = []
    for p in window._problems:
        if p.category != CATEGORY_KERNING or p.error_code != KERNING_GROUP_SORTED_DIFF:
            continue
        loc_raw = p.raw_data.get("discreteLocation") or {}
        if loc_raw == target:
            out.append(p)
    return out


def _show_group_sort_picker(
    window: "ProblemsWindow",
    sources_in_discrete: list,
    discrete_loc: dict,
    affected: list["ProblemItem"],
) -> None:
    """Adw.AlertDialog: pick reference master for kerning-group member order."""
    default_idx = window._find_default_source_idx_for_discrete(discrete_loc)

    affected_groups = sorted({p.raw_data["groupName"] for p in affected})
    affected_sources = {p.raw_data["font"] for p in affected}

    dialog = Adw.AlertDialog()
    loc_label = window._format_discrete_location(discrete_loc) if discrete_loc else ""
    if loc_label:
        dialog.set_heading(f"Sync kerning group member order ({loc_label})")
    else:
        dialog.set_heading("Sync kerning group member order")
    dialog.set_body(
        f"Affects {len(affected_groups)} group(s) across "
        f"{len(affected_sources)} source(s). Member order will be aligned to "
        "the chosen reference. Groups whose members differ in content (not "
        "just order) are left unchanged."
    )

    content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    content_box.set_margin_top(12)
    content_box.set_margin_bottom(12)
    content_box.set_margin_start(12)
    content_box.set_margin_end(12)

    radio_group = None
    selected_ref_idx: list[int | None] = [None]

    for source_idx, fs in sources_in_discrete:
        display_name = fs.path.name.removesuffix(".ufo")
        is_default = source_idx == default_idx
        kern_groups = sum(1 for n in fs.font.groups.keys() if n.startswith("public.kern"))
        counts = f"({kern_groups} kern groups)"

        label_markup = (
            f"<b>{GLib.markup_escape_text(display_name)}</b>"
            + (" <i>(default)</i>" if is_default else "")
            + f"   <span alpha='65%'>{GLib.markup_escape_text(counts)}</span>"
        )
        radio = Gtk.CheckButton()
        radio.set_margin_start(4)

        inner = Gtk.Label(label=label_markup, use_markup=True, xalign=0)
        inner.set_margin_start(4)
        radio.set_child(inner)

        if radio_group is None:
            radio_group = radio
        else:
            radio.set_group(radio_group)

        preselect = (default_idx is not None and is_default) or (
            default_idx is None and selected_ref_idx[0] is None
        )
        if preselect and selected_ref_idx[0] is None:
            radio.set_active(True)
            selected_ref_idx[0] = source_idx

        def on_toggled(btn, idx=source_idx):
            if btn.get_active():
                selected_ref_idx[0] = idx

        radio.connect("toggled", on_toggled)
        content_box.append(radio)

    if len(sources_in_discrete) > 8:
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_min_content_height(120)
        scrolled.set_max_content_height(360)
        scrolled.set_propagate_natural_height(True)
        scrolled.set_child(content_box)
        dialog.set_extra_child(scrolled)
    else:
        dialog.set_extra_child(content_box)

    dialog.add_response("cancel", "Cancel")
    dialog.add_response("sync", "Sync")
    dialog.set_response_appearance("sync", Adw.ResponseAppearance.SUGGESTED)
    dialog.set_default_response("sync")
    dialog.set_close_response("cancel")

    def on_response(dlg, response):
        if response == "sync" and selected_ref_idx[0] is not None:
            _apply_group_sort(
                window,
                selected_ref_idx[0],
                discrete_loc,
                affected_groups,
            )

    dialog.connect("response", on_response)
    dialog.present(window)


def _apply_group_sort(
    window: "ProblemsWindow",
    ref_idx: int,
    discrete_loc: dict | None,
    affected_groups: list[str],
) -> None:
    """Rewrite group member order in every non-reference source whose
    membership set matches the reference. Skip mismatches (those are 5,2)."""
    ds = window._designspace
    if ds is None:
        return

    sources_in_discrete = window._collect_sources_in_discrete(discrete_loc)
    ref_source = ds.sources[ref_idx]
    ref_font = ref_source.font

    fixed_count = 0
    skipped_count = 0
    changed_paths: set = set()

    for group_name in affected_groups:
        ref_members = list(ref_font.groups.get(group_name, []))
        if not ref_members:
            skipped_count += 1
            continue
        ref_set = set(ref_members)

        for source_idx, fs in sources_in_discrete:
            if source_idx == ref_idx:
                continue
            font = fs.font
            if group_name not in font.groups:
                skipped_count += 1
                continue
            cur_members = list(font.groups[group_name])
            if set(cur_members) != ref_set:
                # Membership differs in content — that's 5,2, not our job.
                skipped_count += 1
                continue
            if cur_members == ref_members:
                continue  # Already aligned
            font.groups[group_name] = list(ref_members)
            changed_paths.add(fs.path)
            fixed_count += 1

    logger.info(
        f"sort_kerning_groups: ref_idx={ref_idx} discrete={discrete_loc} "
        f"fixed={fixed_count} skipped={skipped_count} "
        f"changed_fonts={len(changed_paths)}"
    )

    if changed_paths and window._editor_window is not None:
        if hasattr(window._editor_window, "_mark_dirty"):
            window._editor_window._mark_dirty()
        wm = getattr(window._editor_window, "_window_manager", None)
        if wm is not None:
            from font_rover.event_config import EVENT_GROUPS_CHANGED

            for path in changed_paths:
                wm.event_bus.publish(
                    EVENT_GROUPS_CHANGED,
                    {"font_path": str(path), "source": "designspace-validator"},
                )

    if fixed_count == 0:
        window._show_info_toast("Nothing to sync — groups already aligned")
    else:
        window._show_info_toast(
            f"Synced {fixed_count} group(s) across {len(changed_paths)} "
            "source(s) — review and save UFOs"
        )

    window.run_check()


# =============================================================================
# Fix: make features.fea compatible  (8, FEATURES_DIFFER_FROM_DEFAULT)
# =============================================================================


def fix_features_mismatch(window: "ProblemsWindow", item: "ProblemItem") -> None:
    """Offer the two states ufo2ft accepts for a designspace's features."""
    if window._designspace is None:
        return
    try:
        _show_feature_sync_dialog(window, item)
    except Exception as e:
        logger.exception(f"Error showing features fix dialog: {e}")


def _discrete_locations(window: "ProblemsWindow") -> list[dict]:
    """Every discrete location in the document, or ``[{}]`` when it has none."""
    try:
        from fontTools.designspaceLib.split import splitInterpolable

        locations = [loc for loc, _sub in splitInterpolable(window._designspace.doc)]
    except Exception as e:  # pragma: no cover - malformed document
        logger.debug(f"splitInterpolable failed: {e}")
        return [{}]
    return locations or [{}]


def _show_feature_sync_dialog(window: "ProblemsWindow", item: "ProblemItem") -> None:
    """Pick a strategy -- and, when the default has none, a source of features.

    The two responses are the two states the build accepts: features only in
    the default master, or the same features everywhere. Which to prefer is a
    designer's decision, not ours, so both are offered with what each costs.
    """
    from .feature_sync import (
        STRATEGY_CLEAR,
        STRATEGY_COPY,
        broken_includes,
        features_text,
        plan_feature_sync,
        ufo_sources,
    )

    discrete_loc = item.raw_data.get("discreteLocation") or {}
    sources_in_discrete = window._collect_sources_in_discrete(discrete_loc)
    if len(sources_in_discrete) < 2:
        logger.info("Features fix: fewer than 2 sources in discrete location")
        return

    default_idx = window._find_default_source_idx_for_discrete(discrete_loc)
    sources = [fs for _idx, fs in sources_in_discrete]
    default_source = next(
        (fs for idx, fs in sources_in_discrete if idx == default_idx),
        sources[0],
    )
    masters = ufo_sources(sources)
    default_text = features_text(default_source)

    matching = [s for s in masters if s is not default_source and features_text(s) == default_text]
    empty = [s for s in masters if s is not default_source and not features_text(s).strip()]
    differing = [s for s in masters if s is not default_source and s not in matching + empty]

    dialog = Adw.AlertDialog()
    loc_label = window._format_discrete_location(discrete_loc) if discrete_loc else ""
    dialog.set_heading(
        f"Make features.fea compatible ({loc_label})"
        if loc_label
        else "Make features.fea compatible"
    )
    dialog.set_body(
        "ufo2ft builds one variable feature file from the default master, but "
        "only when every other master's features.fea matches it or all of them "
        "are empty. Otherwise features are compiled per master and varLib must "
        "merge them, which fails on a differing glyph order or set of lookups."
    )

    content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    content_box.set_margin_top(12)
    content_box.set_margin_bottom(12)
    content_box.set_margin_start(12)
    content_box.set_margin_end(12)

    summary = (
        f"Default: <b>{GLib.markup_escape_text(default_source.path.name)}</b>"
        f" — {'has features' if default_text.strip() else 'no features'}\n"
        f"{len(matching)} match it · {len(empty)} empty · {len(differing)} differ"
    )
    content_box.append(Gtk.Label(label=summary, use_markup=True, xalign=0))

    # Only when the default has nothing to hand out does the choice of a
    # source master arise; otherwise the default's own text is the answer.
    selected_seed: list = [None]
    if not default_text.strip():
        content_box.append(
            Gtk.Label(
                label="The default has no features. Take them from:",
                xalign=0,
                margin_top=6,
            )
        )
        candidates = [s for s in masters if features_text(s).strip()]
        radio_group = None
        for source in candidates:
            radio = Gtk.CheckButton()
            radio.set_margin_start(4)
            text = features_text(source)
            label = (
                f"<b>{GLib.markup_escape_text(source.path.name.removesuffix('.ufo'))}</b>"
                f"   <span alpha='65%'>({len(text.splitlines())} lines)</span>"
            )
            radio.set_child(Gtk.Label(label=label, use_markup=True, xalign=0, margin_start=4))
            if radio_group is None:
                radio_group = radio
                radio.set_active(True)
                selected_seed[0] = source
            else:
                radio.set_group(radio_group)

            def on_toggled(btn, src=source):
                if btn.get_active():
                    selected_seed[0] = src

            radio.connect("toggled", on_toggled)
            content_box.append(radio)

    # Two warnings about copying, both learned the hard way on an 84-master
    # family: a relative include lands in a UFO that cannot resolve it, and a
    # shared feature file names glyphs a smaller master does not have. Copying
    # there turned one problem into twelve unparsable feature files.
    trial = plan_feature_sync(sources, default_source, STRATEGY_COPY, selected_seed[0])
    warnings = []

    at_risk = broken_includes(trial)
    if at_risk:
        warnings.append(
            f"a relative include would land in {len(at_risk)} UFO(s) in another "
            f"folder, where it will not resolve"
        )

    default_glyphs = set(default_source.font.keys())
    smaller = [
        s
        for s in masters
        if s is not default_source and not default_glyphs.issubset(set(s.font.keys()))
    ]
    if smaller:
        warnings.append(
            f"{len(smaller)} master(s) have fewer glyphs than the default, so a "
            f"shared feature file may not parse there"
        )

    if warnings:
        content_box.append(
            Gtk.Label(
                label=(
                    "<span alpha='65%'>Copying everywhere: "
                    + GLib.markup_escape_text("; ".join(warnings))
                    + ".</span>"
                ),
                use_markup=True,
                xalign=0,
                wrap=True,
                margin_top=6,
            )
        )

    # A designspace without discrete axes has exactly one slice, so offering
    # "all of them" there would be the same button twice.
    all_locations = _discrete_locations(window)
    scope_check = None
    if len(all_locations) > 1:
        scope_check = Gtk.CheckButton(
            label=f"Apply to all {len(all_locations)} discrete locations",
            margin_top=6,
        )
        content_box.append(scope_check)

    if len(masters) > 8 and not default_text.strip():
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_min_content_height(120)
        scrolled.set_max_content_height(360)
        scrolled.set_propagate_natural_height(True)
        scrolled.set_child(content_box)
        dialog.set_extra_child(scrolled)
    else:
        dialog.set_extra_child(content_box)

    dialog.add_response("cancel", "Cancel")
    dialog.add_response("clear", "Features Only in Default")
    dialog.add_response("copy", "Same Features Everywhere")
    # Clearing is the safe half of the choice: the build reads the default's
    # features either way, and copying can carry a file into a master that
    # cannot parse it. It is only destructive when a master has features of its
    # own that nothing else has.
    if warnings:
        dialog.set_response_appearance("clear", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("clear")
    else:
        dialog.set_response_appearance("copy", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("copy")
    if differing:
        dialog.set_response_appearance("clear", Adw.ResponseAppearance.DESTRUCTIVE)
    dialog.set_close_response("cancel")

    def on_response(_dlg, response):
        if response not in ("clear", "copy"):
            return
        strategy = STRATEGY_CLEAR if response == "clear" else STRATEGY_COPY
        scope = all_locations if (scope_check and scope_check.get_active()) else [discrete_loc]
        _apply_feature_sync(window, strategy, scope, selected_seed[0])

    dialog.connect("response", on_response)
    dialog.present(window)


def _apply_feature_sync(
    window: "ProblemsWindow",
    strategy: str,
    scope: list[dict],
    seed_source,
) -> None:
    """Write the planned features text and tell the application about it."""
    from .feature_sync import plan_feature_sync

    written: dict = {}
    seeded = []
    for discrete_loc in scope:
        sources_in_discrete = window._collect_sources_in_discrete(discrete_loc or {})
        if len(sources_in_discrete) < 2:
            continue
        default_idx = window._find_default_source_idx_for_discrete(discrete_loc or {})
        sources = [fs for _idx, fs in sources_in_discrete]
        default_source = next(
            (fs for idx, fs in sources_in_discrete if idx == default_idx), sources[0]
        )
        plan = plan_feature_sync(sources, default_source, strategy, seed_source)
        if plan.seeded_from is not None:
            seeded.append(plan.seeded_from)

        by_path = {fs.path.resolve(): fs for fs in sources}
        for path, text in plan.writes.items():
            source = by_path.get(path)
            if source is None:
                continue
            try:
                source.font.features.text = text
            except Exception as e:
                logger.exception(f"Failed to write features to {path}: {e}")
                window._show_error_toast(f"Could not write features to {path.name}: {e}")
                continue
            written[path] = text

    logger.info(
        f"feature sync: strategy={strategy} slices={len(scope)} "
        f"written={len(written)} seeded={seeded}"
    )

    if not written:
        window._show_info_toast("Features were already compatible")
        window.run_check()
        return

    if window._editor_window is not None:
        if hasattr(window._editor_window, "_mark_dirty"):
            window._editor_window._mark_dirty()
        wm = getattr(window._editor_window, "_window_manager", None)
        if wm is not None:
            from font_rover.event_config import EVENT_FEATURES_CHANGED

            for path in written:
                wm.event_bus.publish(
                    EVENT_FEATURES_CHANGED,
                    {"font_path": str(path), "source": "designspace-validator"},
                )

    verb = "Cleared" if strategy == "clear" else "Updated"
    window._show_info_toast(f"{verb} features in {len(written)} UFO(s) — review and save UFOs")
    window.run_check()


# =============================================================================
# Dispatch table
# =============================================================================

FIXES: dict[tuple[int, int], FixFn] = {
    (CATEGORY_GLYPHORDER, GLYPHORDER_POSITION_MISMATCH): fix_sync_glyph_order,
    (CATEGORY_KERNING, KERNING_GROUP_SORTED_DIFF): fix_sort_kerning_groups,
    (CATEGORY_FEATURES, FEATURES_DIFFER_FROM_DEFAULT): fix_features_mismatch,
}


def get_fix(item: "ProblemItem") -> FixFn | None:
    """Return the fix function for ``item``, or None if no fix is registered."""
    return FIXES.get((item.category, item.error_code))
