# Sources / Instances / Rules coverage (SRC-01..14, INST-01..09, RULE-01..24)

All probes run via `audit/venv/bin/python -m designspace_lint.cli --json <file>` against
files under `audit/compare/probes/src-inst-rules/`. UFOs (`Base.ufo`, `Other.ufo`,
`EmptyB.ufo`, `Sparse.ufo`, `Layered.ufo`) built with defcon, unitsPerEm=1000 throughout
to avoid unrelated 6.0 noise. Full raw output in `probes/src-inst-rules/results.txt`.

## 1. Per-row matrix

### Sources (SRC-01..14)

| id | verdict | code(s) | justification |
|---|---|---|---|
| SRC-01 | COVERED | 2.5 | probe: no source at default → `2.5 No default source defined or found`. |
| SRC-02 | PARTIAL | 2.6 | fires when both duplicate-at-default sources are written identically in XML; **confirmed silent** when one source omits the axis (implicit default) and the other spells `xvalue="400"` explicitly — same normalized location, zero findings. This matches the caveat already in lint-inventory (probe p6). |
| SRC-03 | PARTIAL | 2.6 | same mechanism/caveat as SRC-02, confirmed with a genuine non-default duplicate (two sources both explicit at Weight=700) → `2.6 Duplicate source location with Dup1`. Only catches literal-identical-XML duplicates. |
| SRC-04 | COVERED (positive control) | 2.4 | probe: source at Weight=1200 (axis max 900) → `2.4 Source location Weight=1200.0 out of range [100.0, 900.0]`. |
| SRC-05 | **NOT COVERED — reclassified from COVERED** | 2.3 (unreachable via XML) | **Correction:** lint-inventory lists 2.3 as a working check ("source location names an axis the document lacks"), and the code (`sources.py:207-224`) does implement exactly that. But fontTools' own reader (`designspaceLib/__init__.py:2456-2471`, `readLocationElement`) silently **drops** any `<dimension name="...">` whose name isn't a declared axis, emitting only a `log.warning('Location with undefined axis: "%s".')` — before the `DesignSpaceDocument` object exists. By the time `sources.py`'s `_check_source_location` runs, `source.location` no longer contains the bad key at all, so its `for axis_name in location: if axis_name not in axis_info` loop has nothing to find. Probe confirmed: a source with `<dimension name="Grade" xvalue="50"/>` (no `Grade` axis) produces **zero** findings in the JSON output, only a stderr warning from fontTools itself, not the linter. 2.3 is effectively dead code for any file that goes through the normal file-reading path — it could only fire if something builds a `SourceDescriptor` with a bad location key programmatically, bypassing the XML reader. This is a real, verified inaccuracy in lint-inventory's characterization of 2.3, not just a nuance. |
| SRC-06 | COVERED (via CLI passthrough) | — | `<source>` with `uservalue=` instead of `xvalue=` → `DesignSpaceDocumentError` at read time → CLI exit 2, `cannot read ...: <source> element "Default" must only have design locations (using xvalue="").` Same underlying fontTools check as AXIS-17 (other fork's scope) — cross-reference, not a duplicate finding. |
| SRC-07 | NOT COVERED | — | `copyInfo`/`copyGroups`/etc. source flags are pure metadata to the linter; no check reads them. No probe needed (architecturally certain). |
| SRC-08 | OUT OF SCOPE BY DESIGN | — | depends on how a caller invokes `varLib.load_masters` directly; not visible from DS/UFO. |
| SRC-09 | COVERED | 2.1 | already well-confirmed by existing evidence (probe p4, TestFont-* robustness runs in lint-inventory §5); not re-probed. |
| SRC-10 | N/A / positive control | — | two sources, same `Layered.ufo` path, different `layer=` ("wght500"), different locations. No spurious 2.6/duplicate finding; the glyph checker correctly treats `Layered.ufo` (default layer) and `Layered.ufo [wght500]` as **distinct** masters (see probe output: `location: "Layered [wght500]"` is a separate entity from `Layered.ufo`). Confirms the linter does not conflate same-path-different-layer sources. (Side note: my probe UFO accidentally had an undrawn glyph `B` in the `wght500` layer, which correctly triggered 4.0/4.9/4.12 for that unrelated reason — a useful accidental confirmation that per-layer glyph content *is* checked independently.) |
| SRC-11 / SRC-12 | COVERED | 4.12 | probe: `Base.ufo` has glyph B with an outline, `EmptyB.ufo` has glyph B present but 0 contours/components → `4.12 Glyph 'B' has no contours and no components in EmptyB.ufo, but is drawn in Base.ufo` (warn). Directly surfaces the sparse-vs-blank ambiguity the catalog describes. |
| SRC-13 | NOT COVERED | — | no check reads source-level localized names. No probe needed. |
| SRC-14 | NOT COVERED | — | cosmetic, auto-name collision risk on reorder; not checked. No probe needed. |

### Instances (INST-01..09)

| id | verdict | code(s) | justification |
|---|---|---|---|
| INST-01 | PARTIAL | 3.7 | probe: one instance with no `stylename=` at all, one with only `<stylename xml:lang="de">` (no English) → **both** fire `3.7 missing style name` (info). Confirms the code catches the exact catalog scenario, but only as `info`, not the `breaks build` severity varLib actually gives it. |
| INST-02 | COVERED (via CLI passthrough) | — | instance with both `location="Bold"` and a nested `<location>` → CLI exit 2, `cannot read ...: instance element must have at most one of the location="..." attribute or the nested location element`. |
| INST-03 | COVERED (positive control) | 3.3 (+3.5 duplicate) | instance at Weight=5000 (max 900) → `3.3 instance location has out of bounds value` and `3.5 instance location requires extrapolation` fire together (confirmed duplicate-by-construction, matching lint-inventory's note that 3.5 always accompanies 3.3). |
| INST-04 | NOT COVERED | — | **Catalog correction:** the catalog's own row points to "see AXIS-08" for evidence, but AXIS-08 is the *missing default attribute → parse-time TypeError crash* row — unrelated. The actual mechanism INST-04 describes (an instance sitting at an undeclared discrete-axis value) is DISC-10's territory (source/instance at an undeclared discrete value, silently excluded from every split slice), or AXIS-13/DISC-06 for the closely related "discrete default not in values" case. This cross-reference should be fixed in the catalog. |
| INST-05 | OUT OF SCOPE BY DESIGN | — | only by building (depends on exact nameID-2/17 text + coordinate match). |
| INST-06 | N/A (correct/by-design) | — | discrete-axis coords correctly excluded from fvar `NamedInstance`; not a failure to detect. |
| INST-07 | NOT COVERED | — | no postscript-name legality/uniqueness check exists in category 3 at all. |
| INST-08 | **NOT COVERED — confirmed** | — | probe: two instances, identical `familyname`+`stylename`, different locations (700 vs 750) → **zero findings**. Code 3.4 only catches duplicate *locations*, never duplicate *names* at different locations — genuinely different, uncovered check. |
| INST-09 | NOT COVERED | — | instance-level `<lib>`/`<info>`/`<glyphs>`/`<kerning>` are no-ops for the VF path; not checked. |

### Rules (RULE-01..24)

| id | verdict | code(s) | justification |
|---|---|---|---|
| RULE-01 | NOT COVERED | — | no user-space-vs-design-space heuristic exists; a condition value is just a float to the linter. |
| RULE-02 | COVERED | 7.2 | probe: `minimum="800" maximum="200"` → `7.2 Rule condition has invalid range: Weight min=800.0 > max=200.0`. |
| RULE-03 | **NOT COVERED — confirmed** | — | probe: `minimum="500" maximum="500"` (degenerate) → **zero rule findings** (only the unrelated `3.10 no instances`). Confirms silence, low severity/cosmetic. |
| RULE-04 | COVERED | 7.1 | probe: condition on axis "Grade" (undefined) → `7.1 Rule condition references undefined axis: Grade`. |
| RULE-05 / RULE-06 | **NOT COVERED — confirmed, top gap** | — | probe: rule A (`Weight [100,900]`, `A→B`) declared before rule B (`Weight [500,900]`, `A→A`), overlapping conditionsets both touching glyph `A` → **zero rules findings at all** (only `3.10`). Complete silence on the overlap/shadowing conflict fontTools itself resolves silently by declaration order. Matches catalog's #4 "most dangerous silent failure." |
| RULE-07 | COVERED | 7.3 | probe: `minimum="2000" maximum="3000"` on a 100-900 axis → `7.3 Rule condition maximum above axis maximum: Weight 3000.0 > 900.0`. |
| RULE-08 / RULE-09 | COVERED | 7.5 | probe: one rule subs to a target glyph missing everywhere (`A.zzzmissing`), one subs from a source glyph missing everywhere (`zzz.missingsource`) → both fire `7.5 Rule substitution references undefined glyph: ...`. |
| RULE-10 | OUT OF SCOPE BY DESIGN | — | rvrn/rclt correctness is a shaping-semantics judgment call, not statically decidable even by fontTools. |
| RULE-11 | OUT OF SCOPE BY DESIGN | — | DS-format structural limitation (one document-wide switch), not a bug to detect. |
| RULE-12 | COVERED (nuanced) | 7.0 | probe: `<rule><conditionset/><sub .../></rule>` (conditionset *present*, zero `<condition>` children) followed by a second, ordinary rule with an out-of-range condition → **7.0 fires for the empty-conditionset rule, AND 7.3 fires correctly for the second rule** — no crash. This resolves the RULE-12/RULE-13 ambiguity: a *present-but-empty* conditionset does not trigger the phase crash. (Side nuance: per OT spec an empty conditionset legitimately means "matches everywhere," so 7.0 is technically flagging spec-legal input as a problem — reasonable as an authoring-intent warning, but worth noting it isn't strictly a spec violation.) |
| RULE-13 | PARTIAL — dangerous side effect | 7.0, then a phase crash | probe: `<rule><sub .../></rule>` with **no `<conditionset>` element at all**, followed by a second rule with an out-of-range condition → stderr shows `Phase rules failed: 'list' object has no attribute 'get'`; JSON shows **only** `7.0 Rule has no conditions` for the first rule — the second rule's `7.3` finding is completely lost. Confirms lint-inventory's documented crash (probe p1) and sharpens it: RULE-13 itself IS flagged (info), but the crash silently disables checking of **every subsequent rule in the document**, a much more severe consequence than the row's own listed severity suggests. |
| RULE-14 | N/A (positive control) | — | not independently re-probed (low priority per directive); OR-across-conditionsets semantics not exercised by other probes but no evidence of trouble. |
| RULE-15 | OUT OF SCOPE BY DESIGN | — | a caller/build-script misuse (`varLib.build()` without splitting first); the linter itself correctly uses `splitInterpolable`, so it is not vulnerable to this pitfall. |
| RULE-16 | N/A (positive control) | — | lint-inventory confirms the linter's own discrete split subsets rules per slice; not independently re-probed (low priority). |
| RULE-17 | **PARTIAL — false all-clear from the dedicated check, but caught incidentally elsewhere** | 7.5 (silent), 4.7 (fires) | probe: `Base.ufo` (default) lacks glyph `b.rvrn`; `Sparse.ufo` (non-default) has it; rule `b > b.rvrn`. Result: **7.5 does not fire** (its glyph-existence check is against the *union* of all masters, and `b.rvrn` exists in the union) — a genuine false negative for the exact scenario that will make a real `varLib.build()` raise `VarLibValidationError: Missing glyphs are referenced in conditional substitution rules: b.rvrn`. However, the **Glyphs checker independently flags the same root fact**: `4.7 error — Glyph 'b.rvrn' exists in Sparse.ufo but not in the default source (Base.ufo); it will be dropped from the variable font`, plus `9.0 warn` on glyph order. So a user reading the *full* report (not just Rules findings) does get an actionable signal, just not one that names the rule or explains the substitution will break the build — it reads as an ordinary interpolation-compatibility issue, not a rules problem. |
| RULE-18 | OUT OF SCOPE BY DESIGN | — | glyph renaming by an intermediate build step is invisible to a DS+UFO-only linter. |
| RULE-19 / RULE-20 | OUT OF SCOPE BY DESIGN | — | binary-font-state / call-sequencing issues, not DS/UFO-visible. |
| RULE-21 | NOT COVERED | — | linter never processes `<variable-fonts>`/axis-subsets at all (architecturally certain, same reasoning as AXIS-15/DISC-04/05/07/08/11 in the other fork's scope). |
| RULE-22 | COVERED (via CLI passthrough, positive control) | — | `<rules processing="Last">` (wrong case) → CLI exit 2, `cannot read ...: <rules> processing attribute value is not valid: 'Last', expected 'first' or 'last'`. |
| RULE-23 | COVERED (via CLI passthrough, positive control) | — | `<condition name="Weight"/>` with neither bound → CLI exit 2, `cannot read ...: condition missing required minimum or maximum in rule 'r1'`. |
| RULE-24 | N/A | — | by the time DSSketch expands a wildcard rule, the linter just sees N ordinary `<sub>` elements; no special amplifier code path exists to test. |

## 2. Probe results table

| probe | tests | expected | actual | match? |
|---|---|---|---|---|
| p_src01_no_default | SRC-01 | 2.5 error | `2.5 No default source defined or found` | yes |
| p_src0203_dup_identical | SRC-02/03 (identical XML) | 2.6 error | `2.6 Duplicate source location with Dup1` | yes |
| p_src02_dup_implicit_vs_explicit | SRC-02/03 (implicit vs explicit) | silence (2.6 misses it) | only `3.10`, no 2.x | yes (confirms PARTIAL) |
| p_src04_range | SRC-04 | 2.4 error | `2.4 Source location Weight=1200.0 out of range [100.0, 900.0]` | yes |
| p_src05_badaxis | SRC-05 | 2.3 error (per lint-inventory) | **zero findings**, stderr fontTools warning only | **no — reclassified NOT COVERED** |
| p_src06_uservalue | SRC-06 | CLI exit 2 | `cannot read ...: <source> element "Default" must only have design locations...` | yes |
| p_src10_layer_intentional | SRC-10 | no spurious duplicate flag | 4.0/4.9/4.12 fired for an unrelated, self-inflicted empty glyph in the layer; no 2.x/duplicate finding | yes (core claim holds) |
| p_src1112_empty_glyph | SRC-11/12 | 4.12 warn | `4.12 Glyph 'B' has no contours... in EmptyB.ufo, but is drawn in Base.ufo` | yes |
| p_inst01_no_stylename | INST-01 | 3.7 info ×2 | `3.7 missing style name` for both instances | yes |
| p_inst02_both_location_forms | INST-02 | CLI exit 2 | `cannot read ...: instance element must have at most one of the location=... attribute or the nested location element` | yes |
| p_inst03_range | INST-03 | 3.3 (+3.5) | both fired | yes |
| p_inst08_dupname_diffloc | INST-08 | silence | zero findings | yes (confirms NOT COVERED) |
| p_rule02_minmax | RULE-02 | 7.2 | `7.2 Rule condition has invalid range: Weight min=800.0 > max=200.0` | yes |
| p_rule03_degenerate | RULE-03 | silence | zero rule findings | yes |
| p_rule04_badaxis | RULE-04 | 7.1 | `7.1 Rule condition references undefined axis: Grade` | yes |
| p_rule0506_overlap | RULE-05/06 | silence | zero rule findings | yes |
| p_rule07_oob | RULE-07 | 7.3 | `7.3 Rule condition maximum above axis maximum: Weight 3000.0 > 900.0` | yes |
| p_rule0809_missing_glyph | RULE-08/09 | 7.5 ×2 | both fired (target + source) | yes |
| p_rule12_empty_conditionset | RULE-12 | 7.0, no crash | `7.0` fired, then `7.3` for the second rule also fired (no crash) | yes |
| p_rule13_zero_conditionsets | RULE-13 | 7.0 then crash, later rule lost | `7.0` fired; stderr crash; second rule's `7.3` **absent** | yes |
| p_rule17_sparse_glyph | RULE-17 | 7.5 silent, false all-clear | 7.5 silent; but `4.7` + `9.0` fired instead | partial match — nuance found |
| p_rule22_badprocessing | RULE-22 | CLI exit 2 | `cannot read ...: <rules> processing attribute value is not valid: 'Last'...` | yes |
| p_rule23_condition_nobound | RULE-23 | CLI exit 2 | `cannot read ...: condition missing required minimum or maximum in rule 'r1'` | yes |

## 3. Catalog / lint-inventory corrections

1. **INST-04's cross-reference is wrong.** It points to "see AXIS-08" (missing-default-attribute parse crash) — unrelated. The correct pointer is DISC-10 (instance/source at an undeclared discrete value) or AXIS-13/DISC-06 (discrete default not in values).
2. **RULE-12 vs RULE-13 needed disambiguation** (the catalog rows are individually accurate, but the two are easy to conflate): a `<conditionset/>` element present-but-empty (RULE-12) does **not** crash the rules phase; a `<rule>` with **no** `<conditionset>` at all (RULE-13) does, and the crash silently drops every subsequent rule's findings in the document — a much bigger blast radius than RULE-13's own row implies.
3. **lint-inventory's characterization of 2.3 is inaccurate for real files.** It documents 2.3 as a working check ("source location names an axis the document lacks"), and the code does implement that logic — but fontTools' own XML reader silently strips any dimension naming an undeclared axis before the linter ever sees it (`designspaceLib/__init__.py:2456-2471`, `log.warning` + `continue`), so 2.3 cannot fire through the normal file-reading path. This should be corrected to "declared, but practically unreachable via the CLI on any real file" — the same category as 1.5, 1.10-1.12, 2.8, 2.9 that lint-inventory itself already flags as dead code, just missed for 2.3.
4. **RULE-17 is more nuanced than a pure gap.** The dedicated rules check (7.5) does give a false all-clear (union-based, not base-master-based), but the *glyphs* checker (4.7) independently catches the same underlying fact (glyph present in a non-default master, absent from default) as an ERROR. The practical risk is lower than "completely silent," but the signal is mislabeled (looks like an ordinary interpolation-compatibility issue, not "this rule will break the build").

## 4. Candidate top-gap entries (this scope)

1. **RULE-05/06 — overlapping rule conditionsets, silent declaration-order winner.** Severity: ships-wrong-font (silent). Commonality: any project with more than a couple of weight/width-conditioned substitution rules risks accidental overlap, especially once rules accumulate over a font's lifetime or wildcards are involved. Check sketch: DS-only — parse all rule conditionsets into axis-aligned boxes, compute pairwise intersection, and for each intersecting pair compare `sub` glyph-name sets; if they share any source glyph, flag "rule X (declared first) shadows rule Y for glyph G in the overlap region". False-positive risk: low — this is a geometric fact, not a heuristic; the only judgment call is whether to also flag same-target-same-substitution overlaps (fontTools merges those harmlessly, so exclude when the substitution dict is identical).
2. **RULE-13's crash blast radius.** Severity: ships-wrong-font, but really "some rules silently vanish from checking" — a single malformed rule (easy to produce by hand-editing, or by a buggy generator) disables every later rule's diagnostics with no indication anything was skipped beyond a stderr line most users won't see. Commonality: plausible in any hand-edited or generator-produced DS with several rules. Check sketch: DS-only — before invoking the rules checker at all, pre-scan every `<rule>` for zero conditionsets and either fix the crash (defensive coding) or at minimum emit a structural/error-level finding per empty-conditionset rule so it can't be silently absorbed by a later `try/except`.
3. **RULE-17 / sparse-master substitution glyphs.** Severity: breaks build, deceptively labeled when caught at all. Commonality: DSSketch's own `@sparse` convention makes this a first-class, encouraged pattern — any font using sparse correction masters together with rules that touch sparse-only glyphs is at risk. Check sketch: DS+UFOs — re-run 7.5's glyph-existence check specifically against the **default/base master's** glyph set (not the union), matching what `varLib.build()` actually validates; report separately from the Glyphs checker's 4.7 finding so it's attributed to the rule, not just "a glyph that will be dropped."
4. **SRC-02/03 default/non-default duplicate-location detection misses differently-spelled duplicates.** Severity: breaks build (SRC-01/02's own class), currently caught only when both sources are copy-pasted identically. Commonality: moderate — happens whenever one source is written with an implicit default and another explicitly restates the same value (very natural when hand-editing or merging DS files from different tools). Check sketch: DS-only — normalize every source's location via `getFullDesignLocation()`-equivalent logic (fill in axis defaults for omitted dimensions) before comparing for duplicates, rather than comparing the raw partial dict.
5. **2.3 is effectively dead code for its documented purpose.** Severity: cosmetic-for-the-linter-itself but represents a real, silent AXIS-06-style data loss (an authored dimension on an undeclared axis vanishes with just a stderr warning). Commonality: plausible after an axis rename where old source files aren't fully updated. Check sketch: since fontTools already strips the bad dimension before the linter can inspect `source.location`, the only way to catch this is to **parse the raw XML independently of `DesignSpaceDocument.fromfile()`** (or capture/relay fontTools' own logging warnings as findings) — a genuinely different implementation strategy from what 2.3 currently does.
