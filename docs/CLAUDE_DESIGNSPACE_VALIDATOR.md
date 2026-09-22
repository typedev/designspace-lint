# CLAUDE_DESIGNSPACE_VALIDATOR.md

Component documentation for Claude Code when working with DesignSpace Validator.

**Location**: `designspace_lint/` (the checks) and
`font_rover/designspace_validator/` (the window, the fixes, the GObject wrapper)

---

## Overview

Unified validation system for DesignSpace documents. Combines structural checks, glyph compatibility analysis, and design quality validation into a single module with async/sync execution modes.

### Where the seam is

The checks live in **`designspace_lint/`**, a package that imports neither GTK
nor font-rover, on its way to its own repository and to PyPI. Everything a
window needs stays here:

| In `designspace_lint/` | In `font_rover/designspace_validator/` |
|---|---|
| `checkers/` — all ten categories | `window.py` — the ProblemsWindow |
| `model.py` — `CheckResult`, categories, severities | `model.py` — `ProblemItem(GObject)` + re-exports |
| `engine.py` — `Linter`, `PHASES`, phase order, discrete splitting | `registry.py` — `ValidatorRegistry`: thread + `GLib.idle_add` + wrapping |
| `loader.py` — open a designspace from a path | `fixes.py`, `feature_sync.py` — the auto-fixes |
| `axis_span.py`, `glyph_order.py` | `filter_config.py`, `filter_popover.py` |
| `cli.py` — `designspace-lint <path>` | |

The application passes its own live `DesignSpaceEntry` straight to the checks:
`font_rover.designspace.FontSource` satisfies `designspace_lint.protocols.SourceLike`
structurally, and `tests/test_designspace_lint_isolation.py` fails if it stops
doing so — or if anything in the package grows an import of `gi` or
`font_rover`, however lazily.

`safe_glyph_order` now lives in `designspace_lint/glyph_order.py` and is
re-exported from `font_rover/utils/glyph_order.py`, so the thirty-odd call
sites are unchanged and there is only one copy of it.

From the command line:

```bash
designspace-lint Family.designspace      # one line per problem; exit 1 if any
designspace-lint -v Family.designspace   # with details
designspace-lint --json Family.designspace
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     ValidatorRegistry                            │
│  - Orchestrates all checkers                                    │
│  - Provides async (check_async) and sync (check_sync) modes     │
│  - Reports progress per phase                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
    ┌──────────┐        ┌──────────┐        ┌──────────┐
    │  File    │        │  Glyphs  │        │ Kerning  │
    │ Checker  │        │ Checker  │        │ Checker  │
    └──────────┘        └──────────┘        └──────────┘
          │                   │                   │
          └───────────────────┼───────────────────┘
                              ▼
                       CheckResult
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      ProblemsWindow                              │
│  - GTK4 ColumnView with sorting/filtering                       │
│  - Category/subcategory filter popover                          │
│  - Double-click navigation to source/glyph                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Categories

| Code | Category | Description | Checker |
|------|----------|-------------|---------|
| 0 | File | Basic file validation | `checkers/file.py` |
| 1 | Geometry | Axes, mappings | `checkers/axes.py` |
| 2 | Sources | Source file validation | `checkers/sources.py` |
| 3 | Instances | Instance definitions | `checkers/instances.py` |
| 4 | Glyphs | Glyph compatibility | `checkers/glyphs.py` |
| 5 | Kerning | Kerning consistency | `checkers/kerning.py` |
| 6 | Font Info | Font info consistency | `checkers/fontinfo.py` |
| 7 | Rules | Rule definitions | `checkers/rules.py` |
| 8 | Features | Feature files | `checkers/features.py` |
| 9 | GlyphOrder | Glyph order consistency | `checkers/glyphorder.py` |

---

## Glyph Problems (Category 4)

### Error Codes

| Code | Constant | Description | Localization |
|------|----------|-------------|--------------|
| 4.0 | `DIFFERENT_CONTOUR_COUNT` | Different contour count | Groups by count value |
| 4.1 | `DIFFERENT_COMPONENTS` | Component missing in some sources | Binary: present/missing |
| 4.2 | `DIFFERENT_ANCHORS` | Anchor missing in some sources | Binary: present/missing |
| 4.3 | `DIFFERENT_ON_CURVES` | On-curve points differ in contour | Groups by count |
| 4.4 | `DIFFERENT_OFF_CURVES` | Off-curve points differ in contour | Groups by count |
| 4.5 | `WRONG_CURVE_TYPE` | Curve type mismatch | Groups by type |
| 4.7 | `DEFAULT_GLYPH_EMPTY` | Glyph missing in default | Binary: exists in X |
| 4.8 | `WRONG_CONTOUR_DIRECTION` | Contour direction differs | Specific source |
| 4.9 | `INCOMPATIBLE_GLYPH` | Incompatible construction | Groups by digest |
| 4.10 | `DIFFERENT_UNICODES` | Unicode values differ | Groups by value |
| 4.11 | `GLYPH_AXIS_SPAN_GAP` | Glyph does not reach one end of an axis | Binary: axis + end |
| 4.12 | `GLYPH_EMPTY_IN_SOURCE` | Empty here, drawn elsewhere | Binary: empty in X |

Codes 0-10 match LettError's designspaceProblems. Codes past 10 are ours.
**The numbers are a public contract** -- other projects key on them -- so a
retired check keeps its number (see 8.2 and 9.1) and new checks only ever get
new ones.

### What a master is allowed to skip

There used to be an `_is_sparse_source()` in `checkers/base.py` that called a
master sparse when its name contained the substring "sparse". That is a house
convention, meaningless in a designspace somebody else wrote, and it decided
real checks. It is gone. What replaced it follows what fontTools and ufo2ft
actually do:

| Question | Answer | Where |
|---|---|---|
| May a glyph skip this master? | Yes in the middle of an axis, no at either end and no in the default | `axis_span.py`, codes 4.7 / 4.11 |
| May a master have fewer glyphs? | Yes, if the ones it has are in the default's order | code 9.3 |
| May a master have its own kerning pairs? | Yes, any set | not checked |
| May a master have no kerning at all? | No, if the default has some -- the family's kerning sags to 0 there | code 5.0 |
| May a master have no kern groups? | No, if it has pairs and the others have groups | code 5.6 |
| May a master have its own features.fea? | Only if every non-default master matches the default, or all are empty | code 8.3 |
| Do layer sources get checked for these? | No -- a layer has no kerning, features or glyph order of its own | `_is_layer_source()` |

Why the ends of an axis matter: varLib builds a per-glyph model from the
masters that have the glyph, so a gap in the middle interpolates away. Past the
glyph's *last* master the variation dies out and the glyph reverts to the
**default master's shape** while its neighbours keep changing -- measured on a
0 / 0.5 / 1.0 axis with values 100 / 150 / 300 and the last master missing: 0.75
gives 125 and 1.0 gives 100. The font builds without a word. Axes are judged
one at a time, so a missing corner master in a two-axis space is fine.

`axis_span.py` is deliberately free of GTK and of `font_rover` imports: it is
the first piece written for the eventual standalone package, which will be
called **`designspace-lint`** (name free on PyPI as of 2026-09-22). Only the
checks travel there; the fixes and this window stay in font-rover.

### Location Patterns

**Pattern A: Binary (present/missing)**
```python
# Problems: 4.1 (components), 4.2 (anchors), 4.7 (default empty)
raw_data = {
    "glyphName": "Aacute",
    "locationType": "binary",
    "presentIn": ["Light.ufo", "Regular.ufo"],
    "missingIn": ["Bold.ufo", "Black.ufo"],
}
# Location display: "missing in Bold, Black"
```

**Pattern B: Groups (different values)**
```python
# Problems: 4.0 (contours), 4.3/4.4 (points), 4.5 (curve type), 4.10 (unicodes)
raw_data = {
    "glyphName": "g",
    "locationType": "groups",
    "groups": {
        "2 contours": ["Light.ufo"],
        "3 contours": ["Bold.ufo", "Black.ufo", "Heavy.ufo"],
    },
}
# Location display: "Light ≠ 3 others" or "2 vs 3 contours"
```

**Pattern C: Differs from majority**
```python
# Problems: 4.8 (direction), 4.9 (incompatible)
raw_data = {
    "glyphName": "o",
    "locationType": "differs",
    "differsIn": ["Bold.ufo", "Black.ufo"],
    "contourIndex": 0,
}
# Location display: "≠ Bold, Black"
```

---

## Data Models

### CheckResult

Internal result from checkers:

```python
@dataclass
class CheckResult:
    category: int           # 0-9
    code: int              # Error code within category
    description: str       # Human-readable description
    location: str = ""     # Source name or summary
    glyph_name: str | None = None
    group_name: str | None = None
    details: str = ""      # Detailed explanation
    is_structural: bool = False  # Blocks designspace usage
    raw_data: dict = None  # Action data + source details
```

### ProblemItem

GObject wrapper for GTK display:

```python
class ProblemItem(GObject.Object):
    # Properties
    category: int          # GObject.Property
    error_code: int
    description: str
    location: str
    glyph_name: str
    group_name: str
    details: str
    is_structural: bool

    # Computed
    raw_data: dict         # Original data for actions
    category_name: str     # "Glyphs", "Kerning", etc.
    severity: int          # 0=structural, 1=design, 2=info
    severity_icon: str     # Icon name
    has_glyph: bool
    has_location: bool
```

---

## Basic Usage

### Async Validation (for UI)

```python
from font_rover.designspace_validator import ValidatorRegistry

registry = ValidatorRegistry(designspace_entry=entry)

def on_phase(name: str, current: int, total: int):
    print(f"Phase: {name} ({current}/{total})")

def on_complete(items: list[ProblemItem]):
    print(f"Found {len(items)} problems")
    for item in items:
        print(f"  {item.category_name}: {item.description}")

registry.check_async(
    on_phase=on_phase,
    on_complete=on_complete,
)
```

### Sync Validation (blocking)

```python
items = registry.check_sync()
for item in items:
    print(f"{item.category_name}: {item.description}")
```

### Partial Recheck

The registry runs whole-designspace checks (`check_async` / `check_sync`).
Re-running only the currently selected problems is a window operation:

```python
# Re-check just the rows selected in the ProblemsWindow
window.run_check_selected()
```

---

## ProblemsWindow

GTK4 window for displaying validation results.

### Creation

```python
from font_rover.designspace_validator import ProblemsWindow

window = ProblemsWindow(
    designspace=designspace_entry,
    editor_window=main_window,  # For navigation callbacks
)
window.present()

# Run validation
window.run_check()
```

The window is titled **DesignSpace Validator** (the class keeps its older
name). The editor's toolbar button says the same.

### Features

- **ColumnView** with sortable columns (Category, Glyph, Location, Description)
- **Fixable column** — a narrow icon column (`fr-auto-fix-symbolic`) marking
  the rows this window can fix itself, driven by `fixes.get_fix()`, so a fix
  added to the table shows up in the list without touching the window
- **Filter popover** by category/subcategory
- **Double-click navigation** to source or glyph — or, on a fixable row, the
  fix dialog
- **Recheck Selected** for partial validation
- **Copy to clipboard** for bug reports

### Auto-fixes (`fixes.py`)

A fix is `fix_xxx(window, item)` registered in `FIXES` under
`(category, error_code)`. All three ask before they act, mark the fonts dirty,
publish an event and re-run the check; none of them saves a UFO.

| Problem | Fix |
|---|---|
| 9.3 glyphOrder differs | Sync from a reference master |
| 5.7 group members sorted differently | Sort from a reference master |
| 8.3 features.fea is mixed | Features only in the default, or the same features everywhere |

The features fix (`fix_features_mismatch` + the GTK-free planner in
`feature_sync.py`) offers both states ufo2ft accepts. **Clearing is the safe
half**: the build reads the default's features either way, while copying can
carry a file into a master that cannot parse it. On an 84-master family,
"same features everywhere" turned one problem into twelve `8.0 features file
corrupt` rows, because the shared file names glyphs the sparse masters do not
have. The dialog therefore checks for masters with fewer glyphs (and for
relative `include()` paths landing in another folder), warns, and makes
clearing the default button when it finds either.

### Double-Click Behavior

```python
def _on_row_activated(self, column_view, position):
    item = self._selection.get_item(position)

    if item.has_glyph:
        sources = self._get_problem_sources(item)
        if len(sources) == 1:
            # Single source: switch and open immediately
            self._switch_and_open_glyph(sources[0], item.glyph_name)
        else:
            # Multiple sources: show picker popover
            self._show_source_picker_popover(item, sources)

    elif item.raw_data.get("path"):
        # Source problem: switch to that source
        self._action_switch_source_by_path(item.raw_data["path"])
```

### Source Picker Popover

When a problem affects multiple sources:

```
┌─────────────────────────────────────────────┐
│  g.ss10 — different contour count           │
├─────────────────────────────────────────────┤
│  2 contours (1 source):                     │
│    ● Light.ufo                              │
│                                             │
│  3 contours (3 sources):                    │
│    ○ Bold.ufo                               │
│    ○ Black.ufo                              │
│    ○ Heavy.ufo                              │
├─────────────────────────────────────────────┤
│           [Open Selected]                   │
└─────────────────────────────────────────────┘
```

---

## Filter System

### FilterState

```python
from font_rover.designspace_validator import FilterState

state = FilterState()

# Toggle category
state.toggle_category(CATEGORY_GLYPHS)

# Toggle specific subcategory
state.toggle_subcategory(CATEGORY_GLYPHS, "contour_count")

# Check visibility
if is_problem_visible(item, state):
    # Show in list
```

### Filter Groups

Defined in `filter_config.py`:

```python
FILTER_GROUPS = {
    CATEGORY_GLYPHS: {
        "name": "Glyphs",
        "subcategories": {
            "contour_count": {"codes": [0], "name": "Contour Count"},
            "components": {"codes": [1], "name": "Components"},
            "anchors": {"codes": [2], "name": "Anchors"},
            "points": {"codes": [3, 4], "name": "Point Counts"},
            "curve_type": {"codes": [5], "name": "Curve Types"},
            "empty": {"codes": [7], "name": "Missing in Default"},
            "direction": {"codes": [8], "name": "Contour Direction"},
            "incompatible": {"codes": [9], "name": "Incompatible"},
            "unicodes": {"codes": [10], "name": "Unicodes"},
        },
    },
    # ... other categories
}
```

---

## Creating Custom Checkers

### BaseChecker

```python
from font_rover.designspace_validator.checkers.base import BaseChecker
from font_rover.designspace_validator.model import CheckResult

class MyChecker(BaseChecker):
    CATEGORY = 10  # New category

    def check(self) -> Iterator[CheckResult]:
        for source in self.entry.sources:
            if self._has_problem(source):
                yield self._make_result(
                    code=0,
                    description="Problem description",
                    location=source.path.name,
                    raw_data={"path": str(source.path)},
                )
```

### Helper Methods

```python
class BaseChecker:
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
    ) -> CheckResult:
        """Create CheckResult with category auto-filled."""

    @property
    def doc(self) -> DesignSpaceDocument:
        """Access designspace document."""

    @property
    def entry(self) -> DesignSpaceEntry:
        """Access entry with loaded fonts."""
```

---

## Import Paths

```python
# Top-level
from font_rover.designspace_validator import (
    # Registry
    ValidatorRegistry,
    PHASES,
    # Window (lazy loaded)
    ProblemsWindow,
    # Category constants
    CATEGORY_FILE,
    CATEGORY_GEOMETRY,
    CATEGORY_SOURCES,
    CATEGORY_INSTANCES,
    CATEGORY_GLYPHS,
    CATEGORY_KERNING,
    CATEGORY_FONTINFO,
    CATEGORY_RULES,
    CATEGORY_FEATURES,
    CATEGORY_GLYPHORDER,
    CATEGORY_NAMES,
    # Severity
    SEVERITY_STRUCTURAL,
    SEVERITY_DESIGN,
    SEVERITY_INFO,
    # Data classes
    CheckResult,
    ProblemItem,
    # Filter
    FilterState,
    FILTER_GROUPS,
    is_problem_visible,
)
```

---

## Files

| File | Description |
|------|-------------|
| `__init__.py` | Module exports, lazy window loading |
| `model.py` | CheckResult, ProblemItem, constants |
| `registry.py` | ValidatorRegistry orchestrator |
| `window.py` | ProblemsWindow GTK4 UI |
| `filter_config.py` | Filter groups, FilterState |
| `filter_popover.py` | Filter UI component |
| `checkers/base.py` | BaseChecker class |
| `checkers/glyphs.py` | Glyph compatibility checks |
| `checkers/sources.py` | Source file validation |
| `checkers/kerning.py` | Kerning consistency |
| `checkers/*.py` | Other category checkers |

---

## TODO: Location Enhancement

Current limitation: Most glyph problems don't store source-level location info.

### Planned Changes

1. **GlyphsChecker**: Collect source groups for each problem type
2. **raw_data structure**: Standardize `locationType`, `groups`, `presentIn`, `missingIn`
3. **Location column**: Smart formatting based on `locationType`
4. **Double-click**: Show source picker popover when multiple sources affected
