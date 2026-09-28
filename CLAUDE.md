# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`designspace-lint` reports what a `.designspace` will actually do when fontTools/varLib/ufo2ft build it — silent glyph, kerning, feature and glyph-order problems in UFO masters — and each message names the **consequence**, not just the discrepancy. It was extracted from a GTK font editor (font-rover) and must stay toolkit-free.

## Commands

A `.venv` exists; dev deps are in `[dependency-groups] dev` in `pyproject.toml` (usable with `uv sync`). CI (`.github/workflows/ci.yml`, Python 3.10–3.13) runs:

```console
pip install -e ".[features]" pytest ruff==0.14.6
ruff format --check .
ruff check .
pytest -q
```

- Single test: `pytest tests/test_validator_glyph_presence.py::test_name -q`
- CLI: `designspace-lint Family.designspace` (`--json` for machine output). Exit codes: 0 clean, 1 problems, 2 unreadable.
- `ufo2ft` is optional (`[features]` extra); without it the category-8 features check is skipped.
- Release: bump version in **both** `pyproject.toml` and `designspace_lint/__init__.py` (`__version__`), update `CHANGELOG.md` (Keep a Changelog), push a `v*` tag — `publish.yml` uploads via PyPI Trusted Publishing.

## Architecture

- **Entry points** (`__init__.py`): `lint_path(path)` opens fonts via `loader.open_designspace`; `lint(ds)` / `iter_lint(ds)` take anything satisfying `protocols.DesignSpaceLike` (`path`, `doc`, `sources`) so a host app passes already-open fonts. `Problem` is an alias of `model.CheckResult`.
- **Engine** (`engine.py`, `Linter`): runs `PHASES` in fixed order, one checker per phase (`checkers/*.py`, each a `BaseChecker` subclass with a `CATEGORY`). A result with `is_structural=True` in `file`/`geometry`/`sources` stops the run (per slice, in split mode); errors that should be reported without stopping use `is_structural=False, severity=SEVERITY_STRUCTURAL` (e.g. a missing UFO, most checks added in 0.5). After `geometry`, `SourcesChecker.check_document` / `InstancesChecker.check_document` run once on the whole document in both modes (things a split would hide, and 2.3/3.2, which re-read the raw XML via `raw_xml.py` because fontTools drops unknown-axis dimensions on read). Designspaces with **discrete axes**: `file` and `geometry` run once on the full document, then `splitInterpolable` and the remaining phases per slice, results tagged by discrete location. The `labels` phase (category 10, `checkers/labels.py`) is also document-level: it runs once on the full document in both modes, because instance names are derived from full locations. avar2 checks 1.23–1.29 live in `checkers/avar2.py`, mixed into `AxesChecker`. Severity: the CLI defaults categories 4/5/6/9 to warn and everything else to info, so a warn-level check elsewhere must set `severity=SEVERITY_DESIGN`. `Linter(interpolatable=True)` inserts an `interpolation` phase after `glyphs` (`checkers/interpolation.py`, fontTools' `varLib.interpolatable` over the open fonts; `munkres` via the `interpolatable` extra). A phase that raises becomes a 0.1 finding (`engine.phase_failed`), never a silent log line. Supports `on_phase`/`on_progress` callbacks and a `cancel` object with `is_set()`. A check can also go quiet without raising (CHANGELOG 0.1.2), so tests should assert the codes they expect.
- **Layer-based sources**: several masters may share one UFO, distinguished by layer. Always go through `BaseChecker._match_source`, `_own_glyph`, `_own_keys` (never `font[name]` on a layer source), and `_is_layer_source` — layer sources carry no kerning, features or glyph order of their own (ufo2ft ignores them).
- **Helper modules**: `axis_span.py` (which masters a glyph may skip: mid-axis gaps are fine, end-of-axis gaps revert to the default shape — only when the glyph varies on that axis), `kerning_data.py` and `glyph_order.py` (read raw data around fontParts' normalizer so malformed files become findings, not crashed phases).
- **Results** (`model.py`): plain dataclasses; `severity` overrides the category-derived default (structural / design / info).

## Invariants

- **Every code is in `designspace_lint/codes.py` (`CODES`).** A new check needs an entry (title, group, severities, locators); `tests/test_codes.py` fails otherwise, and the autouse fixture in `tests/conftest.py` fails any test whose findings disagree with the catalogue (unknown or retired code, a severity not listed, a promised `raw_data` locator missing). Locators are only ever added. Consumers (Font-Rover) build their UI from `CODES`; each release gets a "For consumers" changelog section and public names are deprecated one minor release before removal.

- **`(category, code)` pairs are a public contract.** Never renumber or reuse a code; new checks get new numbers. Codes 4.0–4.10 match designspaceProblems (LettError) and must keep that meaning.
- **No toolkit or host-app imports** (`gi`, `gtk`, `adw`, `font_rover`) anywhere in the package, even lazy or under `TYPE_CHECKING` — enforced by `tests/test_designspace_lint_isolation.py`.
- **Rules must match what fontTools/ufo2ft actually do**, verified rather than assumed. Don't encode naming conventions (e.g. "sparse" in a source name) as rules. Differing kerning pair sets are normal and not reported; a master with *no* kerning is. A designspace 5 source may omit axes it is default on.
- Don't depend on other libraries' internal formats (e.g. fontPens digest tuple shapes); read glyph data directly.

## Tests

Tests are headless: fonts come from fakes in `tests/fakes.py`, document-only cases are written as XML with `tests/dsxml.py`. Both are on `pythonpath`.

The fakes model fontParts' `RFont`/layer surface (`layerOrder`, `defaultLayer`, `getLayer`). Keep the fakes faithful — code under test resolves layers through all of those, and an incomplete fake lets tests pass that a real font would fail.
