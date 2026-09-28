# Section: avar2/HOI, Axes, Labels, Discrete axes (81 catalog rows)

Scope: AVAR2-01..35, AXIS-01..18, LABEL-01..16, DISC-01..12.
Tool: `audit/venv/bin/python -m designspace_lint.cli --json <file>` (fontTools 4.66.0).
All new probes live in `audit/compare/probes/avar2-axes-disc/`.

## 1. Per-row matrix

### AVAR2 (35 rows) — verdict: **NOT COVERED** for every row except the three noted.
There is no avar2 support anywhere in designspace-lint (`doc.axisMappings` is never
read; confirmed architecturally in lint-inventory §3, confirmed empirically by probe
`a1_avar2_default_input` and `a2_avar2_tagname` below, and by the real Amstelvar-avar2
runs already in `audit/runs/` — 79–93 mappings per file, zero mentioned in the output).

| id | verdict | code(s) | justification |
|---|---|---|---|
| AVAR2-01 | NOT COVERED | — | probe a1: mapping at default input with non-identity hidden-axis output produces zero avar2-related findings |
| AVAR2-02 | NOT COVERED | — | same probe (a1); corrupted-neighbour effect is a build-time consequence, invisible to a non-building linter regardless |
| AVAR2-03..06 | NOT COVERED | — | no code reads `axisMappings`; not probed individually, architectural certainty |
| AVAR2-07 | NOT COVERED | — | probe a2: dimension name is a tag ("wght") not the axis name ("Weight") — reads and lints clean, no finding (matches catalog: this is a *build-time* `KeyError`, not a read-time one) |
| AVAR2-08 | **NOT COVERED, but COVERED-via-passthrough for the crash itself** | — | probe a4: `uservalue` in a `<mapping>` dimension → CLI exits 2 with `cannot read ...: 'xvalue'`, exactly the catalog's predicted `KeyError: 'xvalue'`. The *content* is never linted (no avar2 code exists), but the malformed file at least fails loudly and clearly via fontTools' own reader + the CLI's exit-2 passthrough. Recorded as NOT COVERED for the coverage matrix (no lint *code* fires) with this caveat noted. |
| AVAR2-09..23 | NOT COVERED | — | architectural; no probe needed beyond a1/a2 above (same "mappings never read" fact covers all of these) |
| AVAR2-24 | NOT COVERED | — | probe a3: `<mappings>` present under `format="5.0"` (spec requires 5.1) reads and lints with **no complaint at all** — fontTools' reader is version-tolerant on input (matches the axes/labels fragment's own note); nothing warns about the v1-engine-compatibility risk either |
| AVAR2-25 | OUT OF SCOPE BY DESIGN | — | only reachable via `varLib.instancer`/`mutator`, which the linter never invokes |
| AVAR2-26..34 | NOT COVERED | — | architectural (mappings never read; labels/STAT never read either, see LABEL section) |
| AVAR2-12 | OUT OF SCOPE BY DESIGN | — | runtime user action (font-variation-settings), not detectable by any static or build-time tool |
| AVAR2-35 | OUT OF SCOPE BY DESIGN | — | platform/OS-specific renderer bug, not detectable statically or by building |

### AXIS (18 rows)

| id | verdict | code(s) | justification |
|---|---|---|---|
| AXIS-01 | **COVERED** | 1.9 | probe b1: non-monotonic map outputs → `error 1.9 Axis mapping output values not in increasing order`, exact match |
| AXIS-02 | **PARTIAL** | 1.6 (info) | probe b2b: map missing entry at axis minimum → fires, but only `info`, not the `error`/build-stop severity the catalog's varLib check would give; also inventory notes 1.6 "assumes sorted" (unverified edge case for out-of-order maps, not probed) |
| AXIS-03 | **PARTIAL** | 1.7 (info) | probe b3: map missing entry at maximum → fires as `info` only, same severity-understatement caveat |
| AXIS-04 | **NOT COVERED** | — | probe b4: map missing entry at the axis *default* (min+max mapped, default un-mapped) → **zero** related finding. No code exists for this (1.0–1.14 has nothing for "default"). Confirmed silent. |
| AXIS-05 | **COVERED-via-passthrough (version-dependent — see correction #1 below)** | — | probe b5: duplicate map input, different outputs → CLI exits 2 with `cannot read ...: Axis 'Weight': mapping input value 400.0 has conflicting outputs 440.0 and 460.0.` This is a **read-time** rejection on fontTools 4.66.0, contradicting the catalog's description (written against 4.60.1) of a silent dict-overwrite with no read-time check. See correction. |
| AXIS-06 | **COVERED** | 2.4 / 3.3 | same mechanism as SRC-04/INST-03 (verified in the parallel sources/instances fork); not re-probed here to avoid duplicate work |
| AXIS-07 | **COVERED** | 1.14 | ran existing `audit/axes-tests/dup_tag.designspace` directly → `error 1.14 Duplicate axis tag: wght` |
| AXIS-08 | **NOT COVERED** | — | ran `audit/axes-tests/missing_default.designspace` → CLI exit 2, raw `TypeError: float() argument must be a string or a real number, not 'NoneType'` — crashes before the linter exists, unhelpful message (no code, no file/line, no axis name) |
| AXIS-09 | **COVERED** | 1.2 | probe b8: default outside [min,max] → `error 1.2 Axis default 50.0 not within range [100.0, 900.0]` |
| AXIS-10 | **PARTIAL** | 1.2 | probe b6: minimum(900) > maximum(100) → fires 1.2 as a side effect: `Axis default 400.0 not within range [900.0, 100.0]` — correctly flags *something* is wrong but misdiagnoses it as "default out of range" rather than "reversed min/max"; the reversed-looking `[900.0, 100.0]` in the message is the only clue |
| AXIS-11 | **COVERED** | 1.1 | probe b7: min==max==400 → `error 1.1 Axis minimum equals maximum: 400.0`. Note: lint treats this as a hard `error`; fontTools/the catalog treat it as harmless-degenerate (cosmetic). The linter is *stricter* than fontTools here, not a gap. |
| AXIS-12 | **NOT COVERED** | — | ran `audit/axes-tests/discrete_nonnumeric.designspace` → CLI exit 2, raw `ValueError: could not convert string to float: 'abc'` — same crash-before-linter class as AXIS-08 |
| AXIS-13 | **NOT COVERED** | — | probe c1c (clean, isolated): discrete axis `values="0 1" default="2"`, both slices given proper Weight-default coverage → **zero** related finding in either slice. (An earlier, badly-isolated probe c1b produced a misleading `2.5` "No default source" finding that turned out to be caused by a missing Weight=400 source in the Italic=1 slice, not by the bad discrete default — see probe table for the debugging trail.) |
| AXIS-14 | NOT COVERED | — | not probed (cosmetic/low-value; architecturally certain — no ordering check anywhere in axes.py per lint-inventory) |
| AXIS-15 | **COVERED-via-passthrough (contradicts catalog's own timing claim — see correction #2)** | — | probe b10b (with `userdefault` added so the file passes the reader's structural completeness gate first): `<axis-subset>` range form on a discrete axis → CLI exits 2 **at read time** with the exact predicted message: `Cannot select a range over 'Italic' for variable font 'VF' because it's a discrete axis, use only 'userValue' instead.` The catalog says this error is "raised only when the subset is actually resolved ... reading the designspace alone does not trigger it" — empirically false for fontTools 4.66.0: it fires on a plain `.read()`/CLI load, before any linter phase runs. |
| AXIS-16 | NOT COVERED (sanity-checked) | — | probe b9: hidden axis with default out of range → `error 1.2` fires exactly as it would for a visible axis, confirming lint-inventory's "hidden axes treated like any other axis" for the geometry checker. The catalog's actual complaint (hidden axis not excluded from *STAT*) is unreachable since the linter never builds STAT — NOT COVERED for the real concern. |
| AXIS-17 | **COVERED-via-passthrough** | — | ran `audit/axes-tests/source_uservalue.designspace` → CLI exit 2, exact message `<source> element "s1" must only have design locations (using xvalue="").` Identical underlying fontTools check to SRC-06 (see cross-reference note). |
| AXIS-18 | NOT COVERED | — | not probed; needs authoring-intent knowledge (is this xvalue a mistaken user-value or a deliberate design coordinate?) that no static rule can resolve — low value as a probe target |

### LABEL (16 rows) — verdict: **NOT COVERED** for all except LABEL-05/06/12.
Labels/STAT are loaded by fontTools but never read by any checker (lint-inventory §2, confirmed architecturally; not re-probed per-row since it's a single blanket fact, not a per-row nuance).

| id | verdict | code(s) | justification |
|---|---|---|---|
| LABEL-01,02,03,04,07,08,09,10,11,13,14,15,16 | NOT COVERED | — | architectural — no checker reads `doc.locationLabels`/`axisLabels` at all |
| LABEL-05 | **NOT COVERED, and triggers a newly-discovered 4th silent phase-crash** | — | probe d3: instance with `location="Bogus"` (undeclared location label), real UFOs present. Result: the **glyphorder phase** crashes and is swallowed: stderr shows `Phase glyphorder failed: InstanceDescriptor.getLocationLabelDescriptor(): unknown location label \`Bogus\` in instance \`None\`.` — JSON output has only one unrelated finding (`3.8 missing output path`). This is a previously-undocumented phase crash (lint-inventory §5 only lists 3: rules/no-conditionset, instances/no-familyname, discrete-split-leak). See correction #3 / top-gap list. |
| LABEL-06 | **COVERED-via-passthrough** | — | probe d1: top-level `<label>` given a design (`xvalue`) location → CLI exit 2, exact message `<label> element "Foo" must only have user locations (using uservalue="").` The catalog's own "positive controls" summary bullet lists only LABEL-12 as this kind of control, not LABEL-06 — an incompleteness in that "e.g." list, not a wrong row (see note below). |
| LABEL-12 | **COVERED-via-passthrough** | — | probe d2: `<label>` with unknown attribute → CLI exit 2, message lists both offending attribute names. (Probe accidentally also had `uservalue` as a bare attribute rather than nested in `<location>`, which is itself invalid — doesn't undermine the confirmation, the unknown-attribute rejection is exactly what fired.) |

### DISC (12 rows)

| id | verdict | code(s) | justification |
|---|---|---|---|
| DISC-01 | NOT COVERED | — | same parse-crash class as AXIS-08/12 (not separately probed) |
| DISC-02 | OUT OF SCOPE BY DESIGN | — | a *caller's* build-script mistake (calling `varLib.build()` directly on an unsplit doc), not something wrong with the DS file itself or visible to a DS-only linter's own use of `splitInterpolable` |
| DISC-03 | NOT COVERED | — | linter never touches `<variable-fonts>`/`<axis-subset>` semantics beyond the read-time structural gate (see AXIS-15); `userDefault=0` falsy-bug is inside `getVFUserRegion()`, never called |
| DISC-04, DISC-05 | NOT COVERED | — | same: require `getVFUserRegion()`/`splitVariableFonts()`, never invoked by the linter (confirmed: linter only calls `splitInterpolable`, per lint-inventory §2) |
| DISC-06 | **NOT COVERED** (= AXIS-13, cross-category duplicate) | — | see AXIS-13; identical mechanism, verified with the same clean probe (c1c) |
| DISC-07 | NOT COVERED | — | requires `splitVariableFonts()`, never invoked |
| DISC-08 | NOT COVERED | — | requires `getVariableFonts()`'s implicit-VF naming, never invoked (linter's own `splitInterpolable` would just generate two identical redundant slices, which is harmless for linting purposes, not the VF-name-collision DISC-08 actually describes) |
| DISC-09 | NOT COVERED | — | catalog itself marks this UNVERIFIED/reasoned-only; not probed (low value, cosmetic) |
| DISC-10 | **NOT COVERED — confirmed as a genuinely dangerous silent total-exclusion bug** | — | probe c2c (clean, isolated): discrete axis `values="0 1"`, a 5th source at the undeclared value `Italic=2`, both real slices given complete coverage. Result: **zero** findings mention the stray source in any way — it is completely invisible (no 2.1, no warning, nothing). `splitInterpolable()`'s `itertools.product()` over the declared `values` never generates a slice containing it, so no phase ever looks at it. A whole master (and its UFO) can vanish from linting entirely because of a single-character discrete-value typo. See top-gap list. |
| DISC-11 | NOT COVERED | — | requires `getVariableFonts()`, never invoked |
| DISC-12 | N/A | — | not a failure mode, a documentation/detection-surface note in the catalog itself |

## 2. Probe results table

| probe | tests | expected | actual | match? |
|---|---|---|---|---|
| a1_avar2_default_input | AVAR2-01/02 | no avar2 finding | `3.10 info`, `6.0 error` (unrelated UPM noise from reused UFO) only | ✅ silence confirmed |
| a2_avar2_tagname | AVAR2-07 | reads clean, no finding | `3.10 info` only, no crash, no finding | ✅ |
| a3_avar2_format50 | AVAR2-24/33 | reads clean under format 5.0 | `3.10 info` only | ✅ |
| a4_avar2_uservalue | AVAR2-08 | CLI exit 2, `KeyError: 'xvalue'` | exit 2, `cannot read ...: 'xvalue'` | ✅ exact |
| b1_nonmonotonic | AXIS-01 | 1.9 error | `error 1.9 Axis mapping output values not in increasing order` | ✅ |
| b2_map_missing_min (superseded by b2b) | AXIS-02 | 1.6 info | contaminated by an accidental source-location collision (2.6) in my first draft | ⚠️ probe bug, fixed |
| b2b_map_missing_min_fixed | AXIS-02 | 1.6 info | `info 1.6 Axis mapping minimum input 400.0 != axis minimum 100.0` alone | ✅ |
| b3_map_missing_max | AXIS-03 | 1.7 info | `info 1.7 Axis mapping maximum input 400.0 != axis maximum 900.0` | ✅ |
| b4_map_missing_default | AXIS-04 | no finding | `3.10 info` only | ✅ silence confirmed |
| b5_dup_map_input | AXIS-05 | catalog expects silent dict-overwrite (no read error) | CLI exit 2, `cannot read ...: mapping input value 400.0 has conflicting outputs 440.0 and 460.0.` | ❌ contradicts catalog (version-dependent, see correction #1) |
| b6_reversed_range | AXIS-10 | 1.2 fires as side effect | `error 1.2 Axis default 400.0 not within range [900.0, 100.0]` | ✅ (misdiagnosed but present, as predicted) |
| b7_min_eq_max | AXIS-11 | 1.1 error | `error 1.1 Axis minimum equals maximum: 400.0` | ✅ |
| b8_default_oob | AXIS-09 | 1.2 error | `error 1.2 Axis default 50.0 not within range [100.0, 900.0]` | ✅ |
| b9_hidden_axis_default_oob | AXIS-16 sanity | 1.2 fires for hidden axis too | `error 1.2 Axis default 500.0 not within range [0.0, 100.0]` | ✅ |
| b10_vf_range_on_discrete (incomplete XML) | AXIS-15 | — | CLI exit 2, but with a *different*, generic completeness message (missing `userdefault`) | ⚠️ probe bug, fixed |
| b10b_vf_range_on_discrete_fixed | AXIS-15 | catalog expects silence at read time | CLI exit 2 **at read time** with the exact discrete-specific message | ❌ contradicts catalog (see correction #2) |
| c1_discrete_default_oob (pure discrete axis) | AXIS-13/DISC-06 | — | `error 1.0 [Italic:0] No axes defined in designspace` — **unexpected**, revealed a separate linter bug (see correction #4) | ⚠️ probe confounded, led to a real finding |
| e1_pure_discrete_control | confirms the 1.0-false-positive is specific to all-discrete docs | 1.0 fires spuriously | `error 1.0 [Italic:0] No axes defined in designspace` | ✅ bug reproduced, isolated |
| c1b_discrete_default_oob_mixed (incomplete coverage) | AXIS-13/DISC-06 | — | `2.5 error [Italic:1] No default source` — probe artifact (missing Weight=400 source in that slice), not the real effect | ⚠️ probe bug, fixed |
| c1c_discrete_default_oob_clean | AXIS-13/DISC-06 | no finding | `3.10 info` ×2, `6.0 error` (unrelated UPM noise) — nothing about the bad default | ✅ silence confirmed (clean) |
| c2_discrete_undeclared_value (pure discrete) | DISC-10 | — | same 1.0 false-positive as c1, confounded | ⚠️ probe bug, fixed |
| c2b_discrete_undeclared_value_mixed (incomplete coverage) | DISC-10 | — | `2.5 error [Italic:1]`, probe artifact again | ⚠️ probe bug, fixed |
| c2c_discrete_undeclared_value_clean | DISC-10 | no finding about the U4 (Italic=2) source | `3.10 info` ×2, `6.0 error` (unrelated) — **nothing at all about U4** | ✅ silence confirmed, dangerous gap verified |
| d1_label_design_location | LABEL-06 | CLI exit 2, DesignSpaceDocumentError | exit 2, `<label> element "Foo" must only have user locations (using uservalue="").` | ✅ exact |
| d2_label_unknown_attr | LABEL-12 | CLI exit 2, unknown-attrs message | exit 2, `Label element contains unknown attributes: uservalue, oldesibling` | ✅ |
| d3_instance_bad_locationlabel | LABEL-05 | uncertain — guessed instances-phase crash | **glyphorder**-phase crash instead (`Phase glyphorder failed: ... unknown location label \`Bogus\`...`), instances phase completed fine | ❌ my phase-guess was wrong, but confirms a real (different) silent crash — 4th phase-crash class, see correction #3 |
| dup_tag.designspace (existing) | AXIS-07 | 1.14 error | `error 1.14 Duplicate axis tag: wght` | ✅ |
| missing_default.designspace (existing) | AXIS-08 | CLI exit 2, raw TypeError | exit 2, `TypeError: float() argument must be a string or a real number, not 'NoneType'` | ✅ |
| discrete_nonnumeric.designspace (existing) | AXIS-12 | CLI exit 2, raw ValueError | exit 2, `ValueError: could not convert string to float: 'abc'` | ✅ |
| source_uservalue.designspace (existing) | AXIS-17 / SRC-06 | CLI exit 2, clean message | exit 2, `<source> element "s1" must only have design locations (using xvalue="").` | ✅ |

## 3. Catalog corrections

1. **AXIS-05 is version-dependent, and the catalog's framing is stale for the linter's actual runtime.** The catalog (built against fontTools 4.60.1 in DSSketch's own `.venv`) describes duplicate `<map>` inputs with conflicting outputs as a *silent* dict-overwrite at read time, only becoming a build error inside `varLib.build()`. On fontTools **4.66.0** — the version actually installed in `designspace-lint`'s own venv per lint-inventory's own header — `DesignSpaceDocument.fromfile()` itself now rejects this at read time with a clear message (`Axis 'Weight': mapping input value 400.0 has conflicting outputs 440.0 and 460.0.`). This matches a fontTools PR the catalog's own Part-1 notes already anticipated in a different context ("PR #4153, 2026-08-20 ... rejects conflicting duplicate *v1* `<map>` inputs" — I had originally read that note as avar2-specific/v1-only and set it aside, but it applies directly here). **Correction: AXIS-05 should be marked COVERED-via-passthrough for any linter (like this one) running on fontTools ≥ the version that ships PR #4153, not NOT-COVERED/silent as the row's "how it manifests" cell states.**
2. **AXIS-15's own timing claim is wrong for fontTools 4.66.0.** The catalog states the discrete-axis-range-subset error "is raised only when the subset is actually resolved... reading the designspace alone does not trigger it." Empirically, on this linter's fontTools version, it fires directly from `.read()`/`fromfile()`, before any resolution step. **Correction: mark AXIS-15 as COVERED-via-passthrough**, with a note that this may itself be version-dependent (worth someone checking against 4.60.1 to see if this is a fontTools regression/improvement between versions, not verified here).
3. **A 4th, previously undocumented, silent phase-crash exists, triggered by LABEL-05's scenario**: an instance with a `location=` attribute referencing a nonexistent top-level location label crashes the **glyphorder** phase (`InstanceDescriptor.getLocationLabelDescriptor()` raising inside `glyph_order.py`'s use of `getFullDesignLocation`/label resolution), not the instances phase as I'd guessed going in. Lint-inventory §5 documents exactly 3 such crashes (rules/no-conditionset, instances/no-familyname, discrete-split-leak) — this is a 4th, distinct one, sharing the same "phase-level `try/except Exception` swallows it and moves on" architecture. Worth adding to `lint-inventory.md`'s §5 if that document is later revised.
4. **New linter defect, not a catalog row but directly confounded two of my probes**: a designspace whose *only* axis(es) are discrete (no continuous axis at all) makes every slice's geometry check spuriously fire `1.0 error "No axes defined in designspace"`, because `splitInterpolable()` correctly removes the discrete axis from each sub-document, leaving `sub_doc.axes == []`, and the geometry checker's `not doc.axes` test can't tell "genuinely no axes" from "no axes *left after a valid discrete split*". Confirmed with a 1-discrete-axis, 2-source control file (`e1_pure_discrete_control.designspace`). Because 1.0 is `is_structural=True`, this also **stops linting entirely for every such document** past the geometry phase (no sources/instances/glyphs/etc. get checked, for any slice), and thanks to the already-documented discrete-split-leak bug (structural-flag not reset per slice), only the *first* slice's spurious 1.0 is even reported — later slices are silently skipped down to the file phase. A pure discrete-axis project (e.g. an italic-only sub-family with no weight axis) gets essentially no linting at all beyond one misleading message. Not a catalog row (it's a linter bug, not a DesignSpace failure mode), but material to the audit because it explains why two of my early discrete-axis probes gave misleading results, and it is itself a serious finding worth surfacing prominently.

## 4. Candidate top-gap entries (this section's scope)

1. **DISC-10 — source at an undeclared discrete value is completely invisible (confirmed silent, no diagnostic of any kind).** Severity: ships-wrong-font (a whole master, and everything it corrects, silently absent from every build without a trace). Commonality: plausible any time someone hand-edits a discrete axis's `values=` list or copy-pastes a source block with a stale numeral — DSSketch's own `ital 0:0:1`-shorthand makes off-by-one typos easy. Check sketch: DS-only — for each discrete axis, diff every source/instance discrete-dimension value against the axis's declared `values` set; trivial, essentially zero false-positive risk (an exact-membership test on floats already present in the file).
2. **The "all-discrete-axes → spurious 1.0, then total blackout" linter bug (correction #4).** Severity: high (total loss of linting for an entire, legitimate document shape) but commonality is probably low (families with *zero* continuous axes are rare — but a single-discrete-axis family used as a component/test file, or a document mid-refactor with a continuous axis just removed, would hit this). Not itself a catalog row / DS-authoring mistake, so it's a "fix the linter" item, not a "add a check" item.
3. **AVAR2-01/02 (default-input mapping silently dropped and corrupts every other mapping) — the single highest-value avar2 gap**, per the catalog's own #1 ranking; confirmed silent here. Commonality in real avar2/HOI projects: high — mapping "Regular"/the default label to its parametric values is a natural thing to write. Check sketch: DS-only — normalize each `<mapping>`'s `<input>` against each listed axis's design-space default; flag any all-default input whose `<output>` differs from that axis's own default value. Low false-positive risk (only fires on a literal all-zero/all-default input combined with a non-identity output).
4. **AXIS-04 (no `<map>` entry at the axis default) confirmed silent**, same class of bug as the (partially covered) AXIS-02/03 minimum/maximum checks, but with zero coverage at all despite being the row the task brief explicitly calls out. Check sketch: DS-only, same shape as the existing 1.6/1.7 checks — add a third comparison against `axis.default` (trivial extension of code that already exists for min/max).
5. **AXIS-15/DISC-03/04/05/07/08/11 as a family: `<variable-fonts>`/`<axis-subset>` is entirely unprocessed except for the handful of structural shapes fontTools itself rejects at read time.** Commonality: rising as DS5 multi-VF documents become more common (this is exactly the multi-VF pattern googlesans-flex and similar large families use). Check sketch: DS+axes — this needs actual `getVariableFonts()`/`getVFUserRegion()`-equivalent logic (cartesian product of discrete values vs. declared `<variable-fonts>` coverage, `userValue` membership checks against declared `values`, the falsy-zero `userDefault` bug) — a bigger lift than most of the above, DS-only, moderate false-positive risk only if the linter mis-models `getVariableFonts()`'s implicit-VF fallback rule.