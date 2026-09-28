# designspace-lint 0.1.2 — Coverage Comparison

Comparison of `failure-catalog.md` (163 independently-derived failure modes, built without
reading the linter) against `lint-inventory.md` (what `designspace-lint` 0.1.2 actually checks,
read from its source at `designspace-lint` @ `2172d82`). Every COVERED/PARTIAL verdict in
the avar2, axes, sources, rules and discrete-axis categories, plus a 17-probe sample across
glyph/kerning/features/order/info (exceeding the required 10), was confirmed by building a
minimal `.designspace` (+ UFOs where needed) and running it through
`audit/venv/bin/python -m designspace_lint.cli --json <file>` (fontTools 4.66.0, ufo2ft 3.9.0).
64 probe `.designspace` files and 41 probe UFOs live under `audit/compare/probes/`. The catalog's
"Compliance Incident" section was ignored per instructions (misattribution).

The catalog's own per-category count table is stale: it says GLYPH=12/INFO=8; the real counts,
confirmed by counting IDs directly, are **GLYPH=13** (GLYPH-13† included) and **INFO=7**
(INFO-07† included). Total is still 163.

## 1. Summary table per category

| Category | Prefix | Rows | Covered | Partial | Not covered | Out of scope (build-only) | N/A (positive control) |
|---|---|---:|---:|---:|---:|---:|---:|
| avar2 / HOI | AVAR2- | 35 | 0 | 0 | 32 | 3 | 0 |
| Axes & axis maps | AXIS- | 18 | 8 | 3 | 7 | 0 | 0 |
| Labels / STAT / elidable | LABEL- | 16 | 2 | 0 | 14 | 0 | 0 |
| Discrete axes / DS5 axis-subsets | DISC- | 12 | 0 | 0 | 10 | 1 | 1 |
| Sources | SRC- | 14 | 6 | 2 | 4 | 1 | 1 |
| Instances | INST- | 9 | 2 | 1 | 4 | 1 | 1 |
| Rules / FeatureVariations | RULE- | 24 | 8 | 2 | 5 | 6 | 3 |
| Glyph-level compatibility | GLYPH- | 13 | 9 | 0 | 3 | 1 | 0 |
| Kerning / groups | KERN- | 6 | 2 | 1 | 1 | 1 | 1 |
| Features (GSUB/GPOS/GDEF) | FEAT- | 6 | 2 | 1 | 0 | 3 | 0 |
| Glyph order | ORDER- | 3 | 3 | 0 | 0 | 0 | 0 |
| Font info | INFO- | 7 | 0 | 1 | 3 | 2 | 1 |
| **Total** | | **163** | **42** | **11** | **83** | **19** | **8** |

Of the 155 rows that describe a real failure mode (excluding 8 positive-control/non-failure
rows): **27% COVERED, 7% PARTIAL, 54% NOT COVERED, 12% OUT OF SCOPE BY DESIGN** (only reachable
by actually building or by a shaping/rendering test). Roughly a third of catalog-eligible
failure modes get *some* signal from the linter; just over half are silently missed despite
frequently being statically detectable from the DS file alone or DS+UFOs.

"Covered via passthrough" means: fontTools' own reader raises a `DesignSpaceDocumentError` (or,
in three cases, a bare crash) at `.read()`/`fromfile()` time, before the linter object exists;
the CLI's generic handler ("`cannot read <path>: <exception>`") surfaces that message and exits
2. This is not a linter *check* — it is fontTools' own validation reaching the user through the
CLI's error path — but it is a real, user-visible outcome worth distinguishing from silence.

## 2. Full per-row matrix

### AVAR2 (35 rows) — verdict: NOT COVERED for every row except 3

There is no avar2 support anywhere in the linter: `doc.axisMappings` is never read (confirmed
architecturally in lint-inventory §3, confirmed empirically by probes below, and by the real
Amstelvar-avar2 runs already in `audit/runs/` — 79–93 mappings per file, zero ever mentioned).

| ID | Verdict | Code(s) | Justification |
|---|---|---|---|
| AVAR2-01 | NOT COVERED | — | probe `a1_avar2_default_input`: default-input mapping with non-identity output → zero avar2 finding |
| AVAR2-02 | NOT COVERED | — | same probe; the corrupted-neighbour effect is a build-time consequence anyway |
| AVAR2-03..06 | NOT COVERED | — | `axisMappings` never read; architectural |
| AVAR2-07 | NOT COVERED | — | probe `a2_avar2_tagname`: dimension name is a tag ("wght") not an axis name → reads and lints clean |
| AVAR2-08 | NOT COVERED (crash caught by CLI passthrough, no lint code) | — | probe `a4_avar2_uservalue`: `uservalue` in a `<mapping>` → CLI exit 2, `cannot read ...: 'xvalue'`, matching the predicted `KeyError`. No avar2 *content* is ever linted; only the malformed-XML crash is surfaced. |
| AVAR2-09..23 | NOT COVERED | — | architectural (same "mappings never read" fact) |
| AVAR2-24 | NOT COVERED | — | probe `a3_avar2_format50`: `<mappings>` under `format="5.0"` (spec wants 5.1) reads and lints with no complaint |
| AVAR2-25 | OUT OF SCOPE BY DESIGN | — | only reachable via `varLib.instancer`/`mutator`, never invoked |
| AVAR2-26..34 | NOT COVERED | — | architectural |
| AVAR2-12 | OUT OF SCOPE BY DESIGN | — | runtime user action (`font-variation-settings`), undetectable by any static or build tool |
| AVAR2-35 | OUT OF SCOPE BY DESIGN | — | platform/OS renderer bug, undetectable statically or by building |

### AXIS (18 rows)

| ID | Verdict | Code(s) | Justification |
|---|---|---|---|
| AXIS-01 | COVERED | 1.9 | probe `b1_nonmonotonic`: non-monotonic map outputs → `error 1.9` |
| AXIS-02 | PARTIAL | 1.6 (info) | probe `b2b`: map missing entry at minimum → fires, but `info` not `error`; "assumes sorted" per lint-inventory |
| AXIS-03 | PARTIAL | 1.7 (info) | probe `b3`: map missing entry at maximum → fires, `info` only |
| AXIS-04 | NOT COVERED | — | probe `b4_map_missing_default`: map missing entry at axis default → zero finding; no code exists for "default" (only 1.6/1.7 exist, for min/max) |
| AXIS-05 | **COVERED via passthrough** (catalog is version-stale) | — | probe `b5_dup_map_input`: duplicate map input, conflicting outputs → CLI exit 2 at **read time**, `Axis 'Weight': mapping input value 400.0 has conflicting outputs...`. Catalog (fontTools 4.60.1) describes a silent dict-overwrite; fontTools 4.66.0 (the linter's actual runtime) now rejects this at read time. Version-dependent — see correction #1. |
| AXIS-06 | COVERED | 2.4 / 3.3 | same mechanism as SRC-04/INST-03 |
| AXIS-07 | COVERED | 1.14 | existing `axes-tests/dup_tag.designspace` → `error 1.14 Duplicate axis tag: wght` |
| AXIS-08 | NOT COVERED | — | `axes-tests/missing_default.designspace` → CLI exit 2, raw `TypeError: float() argument must be a string...` — crashes before the linter exists, unhelpful (no code/line/axis name) |
| AXIS-09 | COVERED | 1.2 | probe `b8_default_oob` → `error 1.2 Axis default 50.0 not within range [100.0, 900.0]` |
| AXIS-10 | PARTIAL | 1.2 (misdiagnosed) | probe `b6_reversed_range`: min(900)>max(100) → 1.2 fires as a side effect ("default not within range [900.0, 100.0]"), correctly flags *something* but calls it "default out of range" rather than "reversed range" |
| AXIS-11 | COVERED (linter stricter than fontTools) | 1.1 | probe `b7_min_eq_max` → `error 1.1 Axis minimum equals maximum`. Catalog treats min==max as harmless/cosmetic; the linter treats it as a hard error — not a gap, an over-strictness worth noting. |
| AXIS-12 | NOT COVERED | — | `axes-tests/discrete_nonnumeric.designspace` → CLI exit 2, raw `ValueError` — same parse-crash class as AXIS-08 |
| AXIS-13 | NOT COVERED | — | probe `c1c_discrete_default_oob_clean` (isolated): discrete default not in `values` → zero finding in either slice. Confirms lint-inventory's "discrete axes' own values/default never validated." |
| AXIS-14 | NOT COVERED | — | not probed (cosmetic, no ordering check anywhere in `axes.py`) |
| AXIS-15 | **COVERED via passthrough** (catalog is timing-stale) | — | probe `b10b`: `<axis-subset>` range form on a discrete axis → CLI exit 2 **at read time**, exact predicted message. Catalog claims this fires "only when the subset is actually resolved"; empirically false on fontTools 4.66.0 — see correction #2. |
| AXIS-16 | NOT COVERED (for the real STAT concern) | — | probe `b9`: hidden axis with default out of range → `1.2` fires exactly as for a visible axis, confirming "hidden axes treated like any other axis" in geometry. The catalog's actual complaint (hidden axis not excluded from STAT) is unreachable since the linter never builds STAT. |
| AXIS-17 | **COVERED via passthrough** | — | `axes-tests/source_uservalue.designspace` → CLI exit 2, `<source> element "s1" must only have design locations...`. Same underlying fontTools check as SRC-06 — cross-category duplicate, not a second finding. |
| AXIS-18 | NOT COVERED | — | not probed; needs authoring-intent knowledge no static rule can resolve |

### LABEL (16 rows) — verdict: NOT COVERED for all except LABEL-06/12

Labels/STAT are loaded by fontTools but never read by any checker (lint-inventory §2).

| ID | Verdict | Code(s) | Justification |
|---|---|---|---|
| LABEL-01,02,03,04,07,08,09,10,11,13,14,15,16 | NOT COVERED | — | architectural — no checker reads `doc.locationLabels`/`axisLabels`. (LABEL-13 substantially overlaps INST-01/3.7, see there.) |
| LABEL-05 | **NOT COVERED — and a newly-found 4th silent phase-crash** | — | probe `d3_instance_bad_locationlabel`: instance with `location="Bogus"` (undeclared label) → the **glyphorder phase** crashes and is swallowed (`Phase glyphorder failed: ...getLocationLabelDescriptor(): unknown location label 'Bogus'...`); JSON output shows nothing about it. Lint-inventory §5 documents only 3 phase-crash bugs (rules/no-conditionset, instances/no-familyname, discrete-split-leak) — this is a 4th, previously undocumented one, and it hits **glyphorder**, not instances as first guessed. See correction #3. |
| LABEL-06 | **COVERED via passthrough** | — | probe `d1`: top-level `<label>` with a design (`xvalue`) location → CLI exit 2, exact predicted message. The catalog's own summary list of positive controls names only LABEL-12, omitting LABEL-06 — an incompleteness in that "e.g." list, not a wrong row. |
| LABEL-12 | **COVERED via passthrough** | — | probe `d2`: unknown attribute on `<label>` → CLI exit 2, message lists the offending attributes |

### DISC (12 rows)

| ID | Verdict | Code(s) | Justification |
|---|---|---|---|
| DISC-01 | NOT COVERED | — | same parse-crash class as AXIS-08/12 |
| DISC-02 | OUT OF SCOPE BY DESIGN | — | a caller's build-script mistake (`varLib.build()` without splitting); the linter itself correctly uses `splitInterpolable`, so it is not vulnerable |
| DISC-03,04,05,07,08,11 | NOT COVERED | — | all require `getVFUserRegion()`/`splitVariableFonts()`/`getVariableFonts()`, none of which the linter ever calls (it only calls `splitInterpolable`) — architecturally certain |
| DISC-06 | NOT COVERED (= AXIS-13, cross-category duplicate) | — | same mechanism and probe as AXIS-13 |
| DISC-09 | NOT COVERED | — | catalog itself marks this UNVERIFIED/reasoned-only; not probed (cosmetic) |
| DISC-10 | **NOT COVERED — confirmed dangerous total silent exclusion** | — | probe `c2c_discrete_undeclared_value_clean` (isolated): a source at an undeclared discrete value (`Italic=2` when `values="0 1"`) → **zero findings of any kind** anywhere. `splitInterpolable()`'s `itertools.product()` over declared `values` never generates a slice containing it, so no phase ever inspects it. A whole master can vanish from linting because of a one-character typo. Top-gap candidate. |
| DISC-12 | N/A | — | not a failure mode, a documentation/detection-surface note in the catalog itself |

### SRC (14 rows)

| ID | Verdict | Code(s) | Justification |
|---|---|---|---|
| SRC-01 | COVERED | 2.5 | probe: no source at default → `2.5 No default source defined or found` |
| SRC-02 | PARTIAL | 2.6 | fires only when both duplicate-at-default sources are written identically in XML; confirmed silent when one omits the axis (implicit default) and the other spells it explicitly — same normalized location, zero findings (matches lint-inventory's own probe p6 caveat) |
| SRC-03 | PARTIAL | 2.6 | same caveat, confirmed with a genuine non-default duplicate |
| SRC-04 | COVERED (positive control) | 2.4 | source at Weight=1200 (max 900) → `2.4 out of range` |
| SRC-05 | **NOT COVERED — reclassified from COVERED, corrects lint-inventory** | — | fontTools' own reader silently drops any `<dimension>` naming an undeclared axis (`log.warning` + `continue`) before the linter ever sees the location; by the time `sources.py`'s 2.3 check runs, the bad key is already gone. Probe: source with `<dimension name="Grade">` (no Grade axis) → **zero findings**, only a fontTools stderr warning. 2.3 is dead code for any file that goes through normal XML reading — see correction #4. |
| SRC-06 | COVERED via passthrough | — | `uservalue=` on a `<source>` → CLI exit 2. Same check as AXIS-17. |
| SRC-07 | NOT COVERED | — | `copyInfo`/`copyGroups`/etc. are pure metadata to the linter; nothing reads them |
| SRC-08 | OUT OF SCOPE BY DESIGN | — | depends on how a caller invokes `varLib.load_masters` directly, not DS/UFO-visible |
| SRC-09 | COVERED | 2.1 | well-confirmed already (probe p4, TestFont-* robustness runs) |
| SRC-10 | N/A (positive control) | — | two sources, same UFO path, different `layer=` → no spurious duplicate/2.6 finding; the glyph checker correctly treats them as distinct masters |
| SRC-11 / SRC-12 | COVERED | 4.12 | glyph with 0 contours/components in a non-default master, non-empty in default → `4.12` fires exactly, surfacing the sparse-vs-blank ambiguity |
| SRC-13 | NOT COVERED | — | no check reads source-level localized names |
| SRC-14 | NOT COVERED | — | cosmetic auto-name collision risk on reorder; not checked |

### INST (9 rows)

| ID | Verdict | Code(s) | Justification |
|---|---|---|---|
| INST-01 | PARTIAL | 3.7 | instance with no stylename, and one with only a non-English `<stylename>` → both fire `3.7` (info, not the "breaks build" severity varLib gives it) |
| INST-02 | COVERED via passthrough | — | instance with both `location=` and nested `<location>` → CLI exit 2 |
| INST-03 | COVERED (positive control) | 3.3 (+3.5 duplicate) | instance at Weight=5000 (max 900) → both fire, confirming 3.5's documented duplicate-by-construction |
| INST-04 | **NOT COVERED — catalog cross-reference is wrong** | — | catalog points to "see AXIS-08" (unrelated: a parse-time TypeError crash). The real mechanism is DISC-10 (instance/source at an undeclared discrete value) or AXIS-13/DISC-06 for the axis-default variant. See correction #5. |
| INST-05 | OUT OF SCOPE BY DESIGN | — | only by building (nameID-2/17 text + exact coordinate match) |
| INST-06 | N/A (correct by design) | — | discrete-axis coords correctly excluded from fvar `NamedInstance`; not a failure |
| INST-07 | NOT COVERED | — | no postscript-name legality/uniqueness check exists at all |
| INST-08 | **NOT COVERED — confirmed** | — | two instances, identical family+style name, different locations → zero findings; 3.4 only catches duplicate *locations*, never duplicate *names* at different locations |
| INST-09 | NOT COVERED | — | instance-level `<lib>`/`<info>`/`<glyphs>`/`<kerning>` are no-ops for the VF path; not checked |

### RULE (24 rows)

| ID | Verdict | Code(s) | Justification |
|---|---|---|---|
| RULE-01 | NOT COVERED | — | no user-space-vs-design-space heuristic; a condition value is just a float |
| RULE-02 | COVERED | 7.2 | `minimum > maximum` → `7.2` fires |
| RULE-03 | NOT COVERED — confirmed | — | `min == max` (degenerate) → zero rule findings; low severity/cosmetic |
| RULE-04 | COVERED | 7.1 | condition on an undefined axis → `7.1` fires |
| RULE-05 / RULE-06 | **NOT COVERED — confirmed, top gap** | — | two rules with overlapping conditionsets both touching glyph "A" → **zero rules findings**. Complete silence on the overlap/shadowing conflict fontTools itself resolves silently by declaration order. Catalog's own #4 "most dangerous silent failure." |
| RULE-07 | COVERED | 7.3 | condition box entirely outside axis range → `7.3` fires |
| RULE-08 / RULE-09 | COVERED | 7.5 | missing target glyph and missing source glyph both fire `7.5` (glyph missing from every master) |
| RULE-10 | OUT OF SCOPE BY DESIGN | — | rvrn/rclt correctness is a shaping-semantics judgment, not statically decidable even by fontTools |
| RULE-11 | OUT OF SCOPE BY DESIGN | — | DS-format structural limitation (one document-wide switch), not a bug to detect |
| RULE-12 | **COVERED (nuanced) — disambiguated from RULE-13** | 7.0 | `<conditionset/>` present but empty, followed by an ordinary second rule → `7.0` fires for the first rule, **and the second rule's `7.3` still fires** — no crash. A present-but-empty conditionset does not trigger the phase crash. |
| RULE-13 | **PARTIAL — dangerous crash blast radius** | 7.0, then a swallowed crash | rule with **zero** `<conditionset>` elements, followed by a second rule with an out-of-range condition → `7.0` fires for the first rule, then the rules phase crashes (`'list' object has no attribute 'get'`) and the **second rule's `7.3` is completely lost**. Confirms and sharpens the documented crash (probe p1): the row itself is flagged, but every later rule in the document silently goes unchecked. |
| RULE-14 | N/A (positive control) | — | OR-across-conditionsets correctly modeled; not independently re-probed |
| RULE-15 | OUT OF SCOPE BY DESIGN | — | a caller/build-script misuse (raw `varLib.build()`); the linter itself correctly uses `splitInterpolable` |
| RULE-16 | N/A (positive control) | — | linter's own discrete split does subset rules per slice, confirmed architecturally |
| RULE-17 | **PARTIAL — false all-clear from the dedicated check, caught incidentally elsewhere** | 7.5 (silent), 4.7 (fires) | glyph present only in a non-default/sparse master, missing from the base — `7.5`'s union-based check gives a **false all-clear** (the glyph is in the union), exactly the failure varLib.build() *will* raise on. But the **Glyphs checker independently flags the same root fact**: `4.7` fires as an error ("exists in Sparse.ufo but not in the default; will be dropped"). A user reading the full report gets a signal, just not one that names the rule or explains the substitution will break the build. |
| RULE-18 | OUT OF SCOPE BY DESIGN | — | glyph renaming by an intermediate build step is invisible to a DS+UFO-only linter |
| RULE-19 / RULE-20 | OUT OF SCOPE BY DESIGN | — | binary-font-state / call-sequencing issues, not DS/UFO-visible |
| RULE-21 | NOT COVERED | — | linter never processes `<variable-fonts>`/axis-subsets at all |
| RULE-22 | COVERED via passthrough (positive control) | — | invalid `processing="Last"` → CLI exit 2 |
| RULE-23 | COVERED via passthrough (positive control) | — | condition with neither bound → CLI exit 2 |
| RULE-24 | N/A | — | by the time DSSketch expands a wildcard rule, the linter sees N ordinary `<sub>`s; no special amplifier path |

### GLYPH (13 rows, incl. GLYPH-13†)

| ID | Verdict | Code(s) | Justification |
|---|---|---|---|
| GLYPH-01 | COVERED | 4.9 (+4.3) | point-count mismatch, same contour count → digest (4.9) and per-contour on-curve count (4.3) both fire |
| GLYPH-02 | COVERED | 4.0 (+4.9) | contour-count mismatch → `4.0` fires directly |
| GLYPH-03 | COVERED | 4.9 (+4.4) | same point/contour count, different on/off-curve flags → digest (4.9) and off-curve count (4.4) both fire |
| GLYPH-04 | COVERED | 4.0, 4.1, 4.9 | composite vs. simple outline → contour count, component-name and digest all fire |
| GLYPH-05 | **OUT OF SCOPE BY DESIGN — the canonical build-tool case** | — | "compatible by checklist, wrong by meaning" (identical counts/flags, different point correspondence) is definitionally invisible to every structural check above; none compares coordinates or point identity. This is exactly what `varLib.interpolatable`'s point-correspondence/rotation analysis exists for (see §5). |
| GLYPH-06 | NOT COVERED | — | ufo2ft's auto-synthesized `.notdef` for masters without one is invisible — the linter only reads what's physically in the source UFOs |
| GLYPH-07 | COVERED (indirect) | 4.0, 4.9 | the linter's own check is format-agnostic — it flags the same mismatch whether the eventual target is glyf or CFF2, so it's actually *more consistent* than fontTools's own asymmetric build behavior |
| GLYPH-08 | COVERED | 4.12 | glyph empty in a non-default master, non-empty in default → fires exactly as documented |
| GLYPH-09 | NOT COVERED | — | component transforms/flags (incl. `USE_MY_METRICS`) are "not examined anywhere" |
| GLYPH-10 | COVERED (two codes depending on shape) | 4.13 (2-master) / 4.11 (3-master) | glyph entirely absent from one non-default master → `4.13`; present in default + an interior master but missing at the top extreme → `4.11` (error, `axis_span_gaps`) — a *stronger* signal than 4.13. Resolves the original ambiguity in the linter's favor. |
| GLYPH-11 | COVERED | 4.2 | anchor present in default, absent in the other master → fires exactly as documented |
| GLYPH-12 | COVERED (transfers from GLYPH-11) | 4.2 | 4.2 is purely name-based; doesn't distinguish a plain mark anchor from a `_1`/`_2` ligature anchor |
| GLYPH-13† | **NOT COVERED — confirmed silent, top gap** | — | GLYPH-08's fixture plus a deliberately bogus advance width (12345, not the HVAR `0xFFFF` sentinel) → `4.12` fires for the empty outline, but **nothing anywhere examines the width**. Confirms the catalog's own flagged top-10 candidate: gvar exclusion is caught, HVAR-lane wrongness is invisible. |

### KERN (6 rows)

| ID | Verdict | Code(s) | Justification |
|---|---|---|---|
| KERN-01 | COVERED | 5.0 (+5.5) | default has kerning, other master has zero pairs/groups → `5.0` fires as error |
| KERN-02 | OUT OF SCOPE BY DESIGN | — | differing kern-subtable count from ufo2ft's internal splitter is invisible from UFO source data |
| KERN-03 | N/A (positive control, confirmed) | — | ordinary sparse per-pair kerning cascade → zero findings, no false positive |
| KERN-04 | **COVERED — resolves catalog's own UNVERIFIED tag** | 5.2 | differing `public.kern1.*` group membership → `5.2` fires exactly. The catalog's UNVERIFIED tag is about the *ufo2ft-level build* consequence (ufo2ft wasn't installed when the catalog was written), a different question from lint coverage, which is clean. |
| KERN-05 | NOT COVERED (dedicated); partial overlap | (4.7 incidental) | no kerning-aware check cross-references pairs against per-master glyph presence; 4.7 only helps if the glyph happens to be missing from the *default* master specifically |
| KERN-06 | PARTIAL | 4.2 (root cause only) | anchor-difference root cause caught via 4.2; the FeatureCount-mismatch consequence itself is build-only |

### FEAT (6 rows)

| ID | Verdict | Code(s) | Justification |
|---|---|---|---|
| FEAT-01 | **COVERED (narrower than lint-inventory implies)** | 8.1 | fires only when BOTH sides' `features.fea` are non-empty and differ in which top-level `kern`/`mark`/`mkmk` block exists; an entirely-empty `features.fea` on one side produces no comparison at all. Does not catch differing kern/mark-*writer*-generated feature sets (KERN territory), which stays build-only. |
| FEAT-02 | COVERED | 8.3 | two genuinely different, non-empty `features.fea` bodies → `8.3` fires as error, directly covering FEAT-02's practical concern |
| FEAT-03 | PARTIAL | 4.0, 4.9 (root cause only) | structural glyph-difference root cause proxied by the same fixture as GLYPH-04; GDEF-merge consequence itself is build-only |
| FEAT-04 | OUT OF SCOPE BY DESIGN | — | rvrn/rclt semantic mismatch invisible even to fontTools's own structural OTL merge |
| FEAT-05 | OUT OF SCOPE BY DESIGN | — | extension-lookup usage depends on final compiled table size |
| FEAT-06 | OUT OF SCOPE BY DESIGN | — | mark/base subtable format divergence is a compiled-binary-level detail |

### ORDER (3 rows)

| ID | Verdict | Code(s) | Justification |
|---|---|---|---|
| ORDER-01 | COVERED | 9.3 | same "common names in a different sequence" mechanism directly demonstrated by the ORDER-02 probe |
| ORDER-02 | **COVERED — resolves catalog's own UNVERIFIED tag** | 9.0, 9.3 | differing `public.glyphOrder` across masters → `9.3` fires directly; the catalog's uncertainty was about ufo2ft's internal reconciliation, a different question from lint coverage |
| ORDER-03 | COVERED (triple signal) | 4.13, 4.7, 9.0 | glyph renamed between masters → old name flagged via `4.13`, new name via `4.7`-as-error AND `9.0` — caught more thoroughly than expected |

### INFO (7 rows, incl. INFO-07†)

| ID | Verdict | Code(s) | Justification |
|---|---|---|---|
| INFO-01 | **PARTIAL — bug reconfirmed** | 6.0 | re-ran existing probe p9: `6.0` fires (catches real UPM divergence) but blames the two *correct* masters, treating `sources[0]` (which isn't the true default) as the reference — a `# TODO: Use doc.findDefault()` bug in `fontinfo.py` |
| INFO-02 | NOT COVERED | — | only `unitsPerEm`/`versionMajor` are checked; no MVAR-eligible metric (xHeight, capHeight, strikeout, underline...) is examined |
| INFO-03 | NOT COVERED | — | name-table/STAT naming is DS/instance-driven, not sourced from non-default masters' own fontinfo; cosmetic/explanatory |
| INFO-04 / INFO-05 | OUT OF SCOPE BY DESIGN | — | TrueType hinting bytecode / `cvt` table don't exist in UFO source form at all — compiled-binary-only data |
| INFO-06 | N/A (not a failure) | — | explanatory note in the catalog itself |
| INFO-07† | NOT COVERED | — | `postscriptUnderlineThickness`/`Position` never read; same sentinel-mismatch bug class as GLYPH-13† |

## 3. Probe results table

64 probe `.designspace` files + 41 UFOs were built and run; the table below lists every distinct
probe/condition (some `.designspace` files exercise the same fixture twice, e.g. GLYPH-13† reuses
GLYPH-08's fixture). "Silence confirmed" = expected no finding, got none.

| Probe | Tests | Expected | Actual | Match |
|---|---|---|---|---|
| a1_avar2_default_input | AVAR2-01/02 | no avar2 finding | only unrelated `3.10`/`6.0` | ✅ silence |
| a2_avar2_tagname | AVAR2-07 | no finding | only `3.10` | ✅ silence |
| a3_avar2_format50 | AVAR2-24/33 | no finding under fmt 5.0 | only `3.10` | ✅ silence |
| a4_avar2_uservalue | AVAR2-08 | CLI exit 2, `KeyError: 'xvalue'` | exit 2, `cannot read ...: 'xvalue'` | ✅ exact |
| b1_nonmonotonic | AXIS-01 | 1.9 error | `1.9` | ✅ |
| b2b_map_missing_min_fixed | AXIS-02 | 1.6 info | `1.6` alone | ✅ |
| b3_map_missing_max | AXIS-03 | 1.7 info | `1.7` | ✅ |
| b4_map_missing_default | AXIS-04 | no finding | only `3.10` | ✅ silence |
| b5_dup_map_input | AXIS-05 | (catalog:) silent overwrite | CLI exit 2, conflicting-outputs message | ❌ contradicts catalog — version-dependent (correction 1) |
| b6_reversed_range | AXIS-10 | 1.2 side-effect | `1.2` ("[900.0, 100.0]") | ✅ |
| b7_min_eq_max | AXIS-11 | 1.1 error | `1.1` | ✅ |
| b8_default_oob | AXIS-09 | 1.2 error | `1.2` | ✅ |
| b9_hidden_axis_default_oob | AXIS-16 sanity | 1.2 fires for hidden axis too | `1.2` | ✅ |
| b10b_vf_range_on_discrete_fixed | AXIS-15 | (catalog:) silent at read time | CLI exit 2 **at read time**, exact message | ❌ contradicts catalog — timing-dependent (correction 2) |
| c1c_discrete_default_oob_clean | AXIS-13/DISC-06 | no finding | only unrelated `3.10`/`6.0` | ✅ silence |
| e1_pure_discrete_control | new bug isolation | — | `1.0 error "No axes defined"` fires spuriously for an all-discrete doc | ⚠️ new linter bug (correction 4) |
| c2c_discrete_undeclared_value_clean | DISC-10 | no finding | only unrelated `3.10`/`6.0`, nothing about the stray source | ✅ silence, dangerous gap confirmed |
| d1_label_design_location | LABEL-06 | CLI exit 2 | exit 2, exact message | ✅ |
| d2_label_unknown_attr | LABEL-12 | CLI exit 2 | exit 2, lists offending attrs | ✅ |
| d3_instance_bad_locationlabel | LABEL-05 | uncertain (guessed instances-phase crash) | **glyphorder**-phase crash instead | ❌ phase-guess wrong, real 4th crash confirmed (correction 3) |
| dup_tag.designspace (existing) | AXIS-07 | 1.14 | `1.14` | ✅ |
| missing_default.designspace (existing) | AXIS-08 | CLI exit 2, raw TypeError | exit 2, `TypeError` | ✅ |
| discrete_nonnumeric.designspace (existing) | AXIS-12 | CLI exit 2, raw ValueError | exit 2, `ValueError` | ✅ |
| source_uservalue.designspace (existing) | AXIS-17/SRC-06 | CLI exit 2 | exit 2, exact message | ✅ |
| p_src01_no_default | SRC-01 | 2.5 | `2.5` | ✅ |
| p_src0203_dup_identical | SRC-02/03 | 2.6 | `2.6` | ✅ |
| p_src02_dup_implicit_vs_explicit | SRC-02/03 | silence (misses it) | no 2.x finding | ✅ confirms PARTIAL |
| p_src04_range | SRC-04 | 2.4 | `2.4` | ✅ |
| p_src05_badaxis | SRC-05 | (lint-inventory:) 2.3 | **zero findings**, fontTools stderr warning only | ❌ contradicts lint-inventory (correction 4) |
| p_src06_uservalue | SRC-06 | CLI exit 2 | exit 2, exact message | ✅ |
| p_src10_layer_intentional | SRC-10 | no spurious duplicate | none (unrelated glyph-content findings only) | ✅ |
| p_src1112_empty_glyph | SRC-11/12 | 4.12 | `4.12` | ✅ |
| p_inst01_no_stylename | INST-01 | 3.7 ×2 | `3.7` ×2 | ✅ |
| p_inst02_both_location_forms | INST-02 | CLI exit 2 | exit 2, exact message | ✅ |
| p_inst03_range | INST-03 | 3.3(+3.5) | both | ✅ |
| p_inst08_dupname_diffloc | INST-08 | silence | zero findings | ✅ confirms NOT COVERED |
| p_rule02_minmax | RULE-02 | 7.2 | `7.2` | ✅ |
| p_rule03_degenerate | RULE-03 | silence | zero rule findings | ✅ |
| p_rule04_badaxis | RULE-04 | 7.1 | `7.1` | ✅ |
| p_rule0506_overlap | RULE-05/06 | silence | zero rule findings | ✅ dangerous gap confirmed |
| p_rule07_oob | RULE-07 | 7.3 | `7.3` | ✅ |
| p_rule0809_missing_glyph | RULE-08/09 | 7.5 ×2 | both | ✅ |
| p_rule12_empty_conditionset | RULE-12 | 7.0, no crash | `7.0`, then `7.3` for the next rule also fired | ✅ disambiguated |
| p_rule13_zero_conditionsets | RULE-13 | 7.0, then crash, next rule lost | `7.0`; crash; next rule's `7.3` absent | ✅ |
| p_rule17_sparse_glyph | RULE-17 | 7.5 silent, false all-clear | 7.5 silent; `4.7`+`9.0` fired instead | ⚠️ partial match, nuance found |
| p_rule22_badprocessing | RULE-22 | CLI exit 2 | exit 2, exact message | ✅ |
| p_rule23_condition_nobound | RULE-23 | CLI exit 2 | exit 2, exact message | ✅ |
| g0103/g01_pointcount | GLYPH-01 | 4.9 | 4.9, 4.3, 4.5 | ✅ |
| g0103/g03_flagmismatch | GLYPH-03 | 4.9 | 4.9, 4.4, 4.5 | ✅ |
| g02 | GLYPH-02 | 4.0 | 4.0, 4.9 | ✅ |
| g04 | GLYPH-04 | 4.0/4.9 | 4.0, 4.1, 4.9 | ✅ |
| g0813 (v1) | GLYPH-08 | 4.12 | 4.0, 4.9, 4.12 | ✅ |
| g0813 (v2, width=12345) | GLYPH-13† | silence on width | 4.12 fired; nothing about width | ✅ silence confirmed, gap real |
| g10_2m | GLYPH-10 (2-master) | some presence code | 4.13 | ✅ |
| g10_3m | GLYPH-10 (3-master) | uncertain | 4.11 (error) — resolved | ✅ |
| g11 | GLYPH-11 | 4.2 | 4.2 | ✅ |
| k01 | KERN-01 | 5.0/5.1 | 5.0, 5.5 | ✅ |
| k03 | KERN-03 | no finding | none | ✅ |
| k04 | KERN-04 | 5.2 | 5.2 | ✅ resolves catalog UNVERIFIED |
| f01 (empty-vs-block) | FEAT-01 attempt 1 | 8.1 | no finding | ❌ initial guess wrong, refined |
| f01 (non-empty-vs-block) | FEAT-01 attempt 2 | 8.1 | 8.1 fired | ✅ confirmed on refined fixture |
| f02 | FEAT-02/8.3 | 8.3 error | 8.3 | ✅ |
| o02 | ORDER-02 | 9.0/9.3 | 9.3 | ✅ resolves catalog UNVERIFIED |
| o03 | ORDER-03 | presence+order codes | 4.13, 4.7(error), 9.0 | ✅ stronger than expected |
| p9_fontinfo_default (re-run) | INFO-01 | 6.0, wrong blame | 6.0 fires, blames correct masters | ✅ reconfirmed |
| interpolatable/Amstelvar-Roman-reference | build-cost baseline | — | 13.3s vs. lint's own 17s on the same file | see §5 |
| interpolatable/GoogleSansFlex | build-cost baseline | — | 378.5s / 918MB, exit 1, real point-rotation findings vs. lint's 132s/3.3GB/0 findings | see §5 |

## 4. Prioritized gap list — statically detectable, NOT COVERED

Ranked by (severity × commonality in real projects), avar2/HOI and DS5 axis-subset patterns
weighted per audit scope.

1. **AVAR2-01/02 — avar2 default-input mapping silently dropped, corrupting every other
   mapping.** Severity: ships-wrong-font, whole-space-wrong. Commonality: high — mapping the
   default label ("Regular") to its parametric values is a natural thing to author; the catalog's
   own #1-ranked danger. Confirmed silent (probe a1). **Check**: DS-only. For each axis in a
   `<mappings>` group, normalize `<input>` against that axis's design-space default; flag any
   mapping whose input is entirely at-default across every listed axis but whose output differs
   from those axes' own defaults. False-positive risk: near zero (exact membership test).
2. **RULE-05/06 — overlapping rule conditionsets touching the same glyph; the winner is
   declaration order, with zero warning.** Severity: ships-wrong-font. Commonality: any project
   with more than a couple of weight/width-conditioned substitution rules, especially once rules
   accumulate or wildcards are used (this repo's own `* > .rvrn (weight >= Bold)` pattern is
   exactly this shape). Confirmed silent (probe p_rule0506_overlap). **Check**: DS-only — parse
   every conditionset into an axis-aligned box, intersect pairwise, and for any pair whose boxes
   overlap and whose `sub` glyph-name sets intersect, flag "rule declared later is shadowed by an
   earlier rule for glyph G in the overlap region." False-positive risk: low; exclude identical
   substitutions (harmless to merge).
3. **DISC-10 — a source/instance at an undeclared discrete-axis value is completely invisible.**
   Severity: ships-wrong-font (a whole master silently absent from every check and, eventually,
   every build). Commonality: plausible whenever a discrete axis's `values=` list is hand-edited
   or a source block is copy-pasted with a stale numeral — DSSketch's own `ital 0:0:1` shorthand
   makes a one-character typo easy. Confirmed silent (probe c2c). **Check**: DS-only — for every
   discrete axis, diff every source/instance's discrete-dimension value against the axis's
   declared `values` set. False-positive risk: none (exact float-membership test).
4. **RULE-13's crash blast radius — a rule with zero `<conditionset>` elements silently disables
   every later rule's diagnostics in the document.** Severity: ships-wrong-font by omission (not
   the rule itself, but every rule after it). Commonality: plausible in any hand-edited or
   generator-produced DS with several rules; a single malformed rule anywhere in the list poisons
   the rest. Confirmed (probe p_rule13). **Check**: DS-only, and really a linter *bug fix* —
   pre-scan every `<rule>` for zero conditionsets before invoking the checker, and either guard
   the crash defensively or emit a structural finding per offending rule so it can't be silently
   absorbed by the phase's `try/except`.
5. **RULE-17 / sparse-master substitution glyphs — the dedicated rules check (7.5) validates
   against the union of all masters' glyphs, not the base/default master specifically, exactly
   backwards from what `varLib.build()` itself checks.** Severity: breaks build, mislabeled when
   caught at all (surfaces as an ordinary glyph-presence warning, not "this rule will break the
   build"). Commonality: DSSketch's own `@sparse` convention makes this a first-class, encouraged
   pattern. Confirmed (probe p_rule17). **Check**: DS+UFOs — re-run 7.5's existence check
   specifically against the default/base master's glyph set, and report it as a rules-category
   finding (not leave it to the incidental 4.7 hit).
6. **The "all-discrete-axes → spurious 1.0, then total blackout" linter bug (new, not a catalog
   row).** A document whose only axis(es) are discrete makes every split slice's geometry check
   spuriously fire `1.0 "No axes defined"` (since `splitInterpolable()` legitimately empties the
   per-slice axis list), and — combined with the already-known discrete-split-leak bug — this
   silently blacks out every check past the file phase for every slice after the first. Severity:
   high (total loss of linting) but likely low commonality (fully-discrete-axis families are
   rare; more likely mid-refactor when a continuous axis is temporarily removed). **Fix**: the
   geometry checker needs to distinguish "genuinely no axes" from "no axes left after a valid
   discrete split."
7. **AXIS-04 — no `<map>` entry at the axis default.** Severity: breaks build (only through
   `varLib.build`, silent otherwise) — the exact case named in the task brief. Commonality:
   moderate (equally easy to forget as the already-partially-covered min/max cases). Confirmed
   silent (probe b4). **Check**: DS-only, a trivial third comparison alongside the existing
   1.6/1.7 min/max logic, against `axis.default`.
8. **`<variable-fonts>`/`<axis-subset>` family (AXIS-15's real concern once the read-time crash
   is set aside, DISC-03/04/05/07/08/11).** Severity: ships-wrong-font or breaks build depending
   on the specific sub-row (falsy-zero `userDefault`, undeclared `userValue`, implicit-VF
   coverage gaps). Commonality: rising — this is exactly the DS5 multi-VF pattern used by
   large real families such as GoogleSansFlex. Confirmed (the linter never calls
   `getVFUserRegion`/`splitVariableFonts`/`getVariableFonts` at all — architectural, not
   individually re-probed beyond AXIS-15's read-time subset). **Check**: DS+axes — needs an
   independent, from-scratch re-implementation of `getVariableFonts()`'s cartesian-product logic
   and `userValue`/`values` membership checks; moderate effort, moderate false-positive risk if
   the implicit-VF fallback rule (`if self.variableFonts: return self.variableFonts`) is
   mis-modeled.
9. **GLYPH-13† / INFO-07† — sentinel-mismatch family (HVAR width / `post` underline metrics
   excluded from gvar's own exclusion mechanism).** Severity: ships-wrong-font (silent, hides
   behind an already-passing/warned glyph-shape check). Commonality: any sparse-master project
   where the shape is correctly emptied but the metrics aren't cleaned up to match. Confirmed
   silent (probe g0813 v2). **Check**: DS+UFOs — whenever 4.12 already flags a glyph as empty in
   a non-default master, additionally compare that master's advance width against a straight-line
   interpolation of the flanking masters and flag deviation beyond a tolerance; separately diff
   `postscriptUnderlineThickness/Position` across masters. False-positive risk: low-to-moderate
   (should be `info`/`warn`, not `error` — placeholder widths on non-participating sparse masters
   are common and often intentional).
10. **SRC-02/03 — duplicate-location detection (2.6) misses differently-spelled duplicates.**
    Severity: breaks build (SRC-01/02's own class). Commonality: moderate — happens whenever one
    source implicitly omits a default-value axis and another explicitly restates it, natural when
    hand-editing or merging DS files from different tools. Confirmed (probe
    p_src02_dup_implicit_vs_explicit). **Check**: DS-only — normalize every source's location
    (fill in axis defaults for omitted dimensions) before comparing, instead of comparing the raw
    partial dict.
11. **2.3 ("source location names an undeclared axis") is dead code for real files** — fontTools'
    own reader silently strips the bad dimension before the linter can see it, so an authored
    dimension on a renamed/removed axis vanishes with only a fontTools stderr warning, never a
    linter finding. This corrects lint-inventory, not just the catalog (see correction 4).
    **Check**: the only way to catch this from inside the current architecture is to parse the
    raw XML independently of `DesignSpaceDocument.fromfile()`, or capture/relay fontTools' own
    logging warnings as findings — a different implementation strategy, not a small patch.
12. **AXIS-13/DISC-06 — discrete axis `default` not present in its own `values` list.**
    Severity: ships-wrong-font (`findDefault()` silently returns `None`). Commonality: plausible
    after a discrete axis's stops change but `default` isn't updated. Confirmed silent (probe
    c1c). **Check**: DS-only — trivial membership test, `axis.default in axis.values`.
13. **LABEL-05 — instance referencing an undeclared location label silently crashes the
    glyphorder phase (new, 4th undocumented phase-crash).** Severity depends on document — loses
    an entire phase's diagnostics for that slice. Commonality: low-moderate (typo'd
    `location="..."` references). **Fix**: same defensive-guard pattern as RULE-13/instances'
    known crashes — catch and report per-instance rather than losing the whole phase.
14. **INST-08 — duplicate instance style names at different locations.** Severity: ships-wrong-
    font (UX-facing — a style picker can't disambiguate). Commonality: moderate in large
    instance sets. Confirmed silent. **Check**: DS-only — group instances by composed
    family+style name string, flag any group with more than one distinct location.
15. **FEAT-01's narrow trigger condition** — real projects commonly generate `kern`/`mark`/`mkmk`
    entirely via ufo2ft's writers rather than hand-authored top-level blocks, which 8.1 cannot
    see. Medium priority: solving this fully needs re-implementing ufo2ft's writers, likely not
    worth it; better documented as a known limitation than chased as a fixable gap.

## 5. What only a build-time step could catch, and is it worth adding

**Definitively build-only, no static check can help:** RULE-10/11/18/19/20 (shaping-semantics
judgment, call-sequencing, binary table state), FEAT-04/05/06 (compiled-table-size/format
details), INFO-04/05 (TrueType hinting bytecode, doesn't exist before TTF compilation),
AVAR2-24/35 (renderer/platform support), AVAR2-25 (instancer/mutator-specific bugs), INST-05
(nameID reuse depends on exact coordinate + existing name-table state), SRC-08 (depends on the
calling code, not the DS/UFO data). **GLYPH-05 is the cleanest example of all**: identical
point/contour/flag counts, wrong point correspondence — invisible to every structural check in
this linter by construction, and exactly the class of bug `fontTools.varLib.interpolatable`
exists to find (it does point-correspondence/rotation analysis that a count/digest comparison
structurally cannot).

**Would `varLib.interpolatable` be worth running as a complementary pass? Empirically tested,
not just estimated:**

| File | designspace-lint (existing, from `audit/runs/`) | `varLib.interpolatable` (measured here) |
|---|---|---|
| Amstelvar-Roman/reference (3 axes, 27 sources, 1041 glyphs) | 17 s, 0.47 GB, 2013 findings | **13.3 s**, exit 1, real point-count/component mismatches found |
| GoogleSansFlex (6 axes, 658 declared sources, ~720+ glyphs) | 132 s, 3.3 GB, 0 findings | **378.5 s (6:19), 918 MB peak RSS**, exit 1, dozens of real "Contour 0 start point differs... reversed: True" findings across many master pairs |

Both numbers for `varLib.interpolatable` are real, measured runs against the public repos already
available as local clones of the public `amstelvar-avar2` and `googlesans-flex` repositories), not estimates. Two
things stand out:

1. **It found real bugs GoogleSansFlex's own lint run reported zero findings for** — reversed
   contours / mismatched start points between masters, exactly GLYPH-05's failure class. This is
   the strongest concrete argument in this whole audit for adding it: the existing digest-based
   glyph checker is blind to exactly the kind of interpolation break that ships a visibly wrong
   variable font, and `interpolatable` catches it directly.
2. **Cost is the same order of magnitude as what the linter already pays**, and in a different
   resource: on GoogleSansFlex, `interpolatable` took ~2.9× the wall-clock time of the existing
   lint run but used ~28% of the memory (918 MB vs. 3.3 GB) — plausible since `interpolatable`
   does its own font loading via `TTFont`/UFO-glyph-set objects rather than fontParts' heavier
   font model, but does *O(master-pairs)* comparisons rather than the lint's *O(masters)* digest
   pass, which is why it costs more time despite less memory. Recommendation: **reasonable to add
   as an opt-in flag** (e.g. `--interpolatable`) rather than the default path, given it roughly
   doubles-to-triples total run time on the largest real-world file tested; not a candidate for a
   fast pre-commit gate on very large families, but entirely reasonable for CI/nightly or
   pre-release runs. If integrated *inside* the linter's own process (reusing already-opened
   font objects instead of re-opening every UFO from scratch as this standalone test did), the
   incremental cost would likely be meaningfully lower than the 378 s measured here.

**Would a trial `varLib.build()` be worth it?** Not measured directly in this audit (deliberately
— a full UFO→TTF compile of a 658-source, ~700+-glyph family via `ufo2ft` involves feature
compilation, kerning-class flattening, mark/mkmk generation and cu2qu conversion for every single
master before `varLib.build()` even starts merging them; attempting it risked a very long,
resource-heavy run for a single data point). This is reasoned, not measured: the linter's own
132 s is spent just *opening* 657 UFOs through fontParts; ufo2ft's per-master compile step does
substantially more work than an open, so a full trial build is very likely to cost at minimum
several minutes and plausibly considerably longer for a family this large — an order of magnitude
that makes it impractical as a routine, every-commit lint step, though defensible as an occasional
CI/pre-release gate (which is exactly how most real pipelines already use `fontmake`/`varLib.build`
today). The build-only rows this would additionally catch — RULE-08/09/17-class glyph checks
duplicated more accurately, FEAT-01..06's full breadth, KERN-01/02/06's actual FeatureCount
failures, GLYPH-06/07's TrueType/CFF2 asymmetry, and any interaction between all of the above —
substantially overlap with what a much cheaper `interpolatable` pass plus the existing UFO-level
checks already surface at 1/10th to 1/30th the likely cost; a full trial build's *unique*
marginal value (catching a build failure a moment before `fontmake` would anyway) is real but
comparatively small next to `interpolatable`'s. Recommendation: **interpolatable first, trial
build only as a separate, explicitly-opt-in, expect-it-to-be-slow "verify" mode**, not something
to fold into the default lint pass.

## 6. Catalog and lint-inventory corrections found during verification

1. **AXIS-05 is version-dependent; the catalog's framing is stale for the linter's actual
   fontTools (4.66.0).** The catalog (built against fontTools 4.60.1) describes duplicate `<map>`
   inputs with conflicting outputs as a silent dict-overwrite at read time. On 4.66.0,
   `DesignSpaceDocument.fromfile()` itself now rejects this at read time with a clear message.
   Reclassify AXIS-05 as COVERED-via-passthrough for any linter running on fontTools ≥ the
   version carrying this fix (plausibly related to the same PR #4153 the catalog's own Part-1
   notes mention in a different, avar2-v1-map context).
2. **AXIS-15's own timing claim is wrong for fontTools 4.66.0.** The catalog states the
   discrete-axis-range-subset error "is raised only when the subset is actually resolved...
   reading the designspace alone does not trigger it." Empirically, on 4.66.0, it fires directly
   from `.read()`/`fromfile()`. Reclassify as COVERED-via-passthrough; flag as possibly
   version-dependent (not checked against 4.60.1 here).
3. **A 4th, previously undocumented silent phase-crash exists** (lint-inventory §5 lists only 3):
   an instance's `location=` referencing a nonexistent top-level location label crashes the
   **glyphorder** phase (`InstanceDescriptor.getLocationLabelDescriptor()` raising, swallowed by
   the phase's `try/except`), not the instances phase. Worth adding to lint-inventory.md §5.
4. **lint-inventory's characterization of 2.3 is inaccurate for real files.** It documents 2.3 as
   a working check; the code does implement the logic, but fontTools' own XML reader silently
   strips any dimension naming an undeclared axis before the linter ever sees `source.location`
   (`log.warning` + `continue`), so 2.3 cannot fire through the normal file-reading path. Should
   be reclassified alongside 1.5/1.10-1.12/2.8/2.9 as declared-but-practically-unreachable.
5. **INST-04's cross-reference is wrong.** It points to "see AXIS-08" (missing-default-attribute
   parse crash — unrelated). The correct pointer is DISC-10 (instance/source at an undeclared
   discrete value) or AXIS-13/DISC-06 for the discrete-default variant.
6. **RULE-12 vs. RULE-13 needed disambiguation, not correction** — both catalog rows are
   individually accurate, but easy to conflate. A present-but-empty `<conditionset/>` (RULE-12)
   does not crash the rules phase; a `<rule>` with zero `<conditionset>` elements at all
   (RULE-13) does, and the crash's blast radius (every subsequent rule silently unchecked) is
   larger than RULE-13's own row implies.
7. **GLYPH-10's 3-master ambiguity resolves in the linter's favor**, via `4.11` (axis-span,
   error) rather than `4.13` when the glyph is missing only from a topmost extreme master — a
   stronger signal than originally guessed, not a gap.
8. **KERN-04 and ORDER-02's UNVERIFIED tags are about a different question than lint coverage.**
   Both are marked UNVERIFIED in the catalog because `ufo2ft` wasn't installed when those
   fragments were written, blocking confirmation of the *build-time* consequence. Whether the
   *linter* catches the underlying condition is a separate, now-resolved question: both are
   cleanly COVERED (5.2 and 9.0/9.3 respectively).
9. **FEAT-01's actual trigger condition (8.1) is narrower than lint-inventory's phrasing
   suggests** — it requires both compared UFOs to have non-empty `features.fea`; an entirely
   empty file on one side produces no comparison and no finding.
10. **LABEL-06 is a positive control the catalog's own summary bullet omitted** alongside
    LABEL-12 — an incompleteness in that "e.g." list (which never claimed to be exhaustive), not
    a wrong row.
11. **A new linter bug, not a catalog row**: a designspace whose only axis(es) are discrete makes
    every split slice spuriously fail `1.0 "No axes defined"`, and because 1.0 is structural, this
    triggers the already-known discrete-split-leak, silently blacking out every later slice past
    the file phase. Confirmed with an isolated control file.

## 7. What could not be verified / left as-is

- avar2/HOI renderer-support matrix rows (AVAR2-24/35) and the platform-specific macOS bug — not
  independently re-tested against real browsers/OSes here either; carried through as OUT OF
  SCOPE BY DESIGN on the strength of "no static or build check could help regardless."
- KERN-02, KERN-05, FEAT-03/04/05/06's exact ufo2ft-internal mechanics — still not independently
  traced through ufo2ft source in this pass (it is installed in the venv, 3.9.0, but reading its
  splitter/GDEF-classifier source was out of scope for this comparison phase); classified by
  architectural reasoning from what the linter reads, which is sufficient to answer the coverage
  question even without re-deriving ufo2ft's own internals.
- GLYPH-06/GLYPH-09/INFO-02/03 — not probed (architecturally certain absences per lint-inventory's
  own exhaustive code lists); confirming with a probe would only reproduce the same "zero
  findings" result already implied by the source-level enumeration.
- A trial `varLib.build()` timing/memory measurement on GoogleSansFlex was deliberately not
  attempted (see §5) — the cost/benefit conclusion there is reasoned from the measured
  `interpolatable` and lint numbers, not independently measured for the build path itself.
