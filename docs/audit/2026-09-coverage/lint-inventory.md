# designspace-lint 0.1.2: inventory of what it actually checks

Source: `designspace-lint` @ `2172d82` (read-only). All line numbers refer to
`designspace_lint/…` in that tree. Run environment: a copy of the tree was installed into a
scratch venv (`audit/venv`, Python 3.12, fontTools 4.66.0, fontParts, fontPens, ufo2ft 3.9.0).
The repo itself was not touched.

Severity as shown by the CLI (`cli.py:_severity`, l.24-45):
- `is_structural=True` → **error**
- otherwise, category 4/5/6/9 → **warn**, category 0/1/2/3/7/8 → **info**
- the per-result `severity` override is used by exactly one check (5.7 → info).

"Inputs" legend: **DS** = designspace XML only; **UFO-fs** = looks at the filesystem (existence,
`metainfo.plist`, `layercontents.plist`) without opening fonts; **UFO** = needs the fonts opened
through fontParts (`entry.sources`); **ufo2ft** = needs the optional `ufo2ft` extra.

---

## 1. Every code it can emit

### Category 0 — File (`checkers/file.py`)

| code | sev | trigger | inputs |
|---|---|---|---|
| 0.0 | error | `self.doc` is None, lacks `axes`/`sources`, or loading raises (file.py:31-60) | DS |

Effectively **unreachable through `lint_path()`/CLI**: `open_designspace()` parses the file
*before* the linter exists (loader.py:122), so a malformed file raises there and the CLI exits 2
with `cannot read …`. 0.0 can only appear via `Linter(path=…)` with no entry.

### Category 1 — Geometry (`checkers/axes.py`)

| code | sev | trigger (file:line) | notes |
|---|---|---|---|
| 1.0 | error | `not doc.axes` (l.71) — returns | |
| 1.1 | error | `axis.minimum == axis.maximum` (l.116); skips rest of that axis | |
| 1.2 | error | default not in `[min, max]` (l.127) | user space |
| 1.3 | error | `axis.map` has < 2 pairs (l.159) | |
| 1.4 | error | a map **input** outside `[min,max]` (l.194) | user space |
| 1.6 | info | `inputs[0] != axis.minimum` (l.212) | not structural; assumes sorted |
| 1.7 | info | `inputs[-1] != axis.maximum` (l.226) | not structural |
| 1.8 | error | map inputs not sorted ascending (l.174) | |
| 1.9 | error | map outputs not sorted ascending (l.184) | reversed (decreasing) axes flagged too |
| 1.13 | error | duplicate `axis.name` (l.88) | |
| 1.14 | error | duplicate `axis.tag` (l.99) | |

**Declared but never emitted:** 1.5 (map output out of range), 1.10/1.11/1.12 (no-map
input≠output; the branch at l.146-150 is `pass`). Docstring lists them (l.12-20).
Input: DS only. Discrete axes are never seen here (see §2: in split mode the sub-documents
contain only continuous axes; without discrete axes there is nothing to see). Hidden axes are
treated like any other axis. `axisMappings` (avar2) are not read.

### Category 2 — Sources (`checkers/sources.py`)

| code | sev | trigger | inputs |
|---|---|---|---|
| 2.0 | error | `not doc.sources` (l.66) — returns | DS |
| 2.1 | error | source path does not exist (l.170) | UFO-fs |
| 2.2 | error | path is a file not ending `.ufoz` (l.181), or UFO dir lacks `metainfo.plist` (l.194) | UFO-fs |
| 2.3 | error | source location names an axis the document lacks (l.218) | DS |
| 2.4 | error | explicit location value outside the axis **design** range, taken as min/max of map outputs (or user min/max when unmapped) (l.241) | DS |
| 2.5 | error | no source has `copyInfo` or an exact explicit full-location match, **and** `doc.findDefault()` is None (l.147-157) | DS |
| 2.6 | error | two sources with identical `tuple(sorted(source.location.items()))` (l.122) | DS |
| 2.7 | error | `layerName` not found: no `glyphs.<layer>` dir and name absent from `layercontents.plist`, or no plist and no `glyphs/` (l.275-315) | UFO-fs |

**Declared but never emitted:** 2.8 (source has no font), 2.9 (default location mismatch).
Discrepancy: the module docstring still says 2.3 = "Source location missing axis value"; the code
was changed in 0.1.1 to "names an axis the document does not have" (comment l.208-215).

Caveats found by reading and confirmed by probes:
- 2.6 compares the *raw, partial* DS5 location, so a source that omits an axis and one that
  spells the same default explicitly are **not** detected as duplicates (probe p6: two sources at
  Weight 400/Width 100 → no 2.6). In split mode (discrete axes) fontTools expands locations, so the
  same case *would* be caught — behaviour differs by whether the document has a discrete axis.
- 2.4 derives the design default only from a map entry whose input equals the user default
  exactly (l.85-89); otherwise it uses the user default. This only feeds 2.5's first pass, and
  2.5 falls back to `findDefault()`, so no false positive was observed (probe p10).
- The file is not opened here; a UFO that fontParts refuses to open is dropped silently by the
  loader (loader.py:143-146, a log warning) and never reported as a problem.

### Category 3 — Instances (`checkers/instances.py`)

| code | sev | trigger | notes |
|---|---|---|---|
| 3.1 | info | `getFullDesignLocation()` returned None (l.117) | **dead**: that method always returns a dict |
| 3.2 | info | location names an axis not in the doc (l.170) | **dead** in practice: `getFullDesignLocation` only iterates `doc.axes`; reachable only if that call raises and the raw-location fallback (l.111-114) is used |
| 3.3 | info | a full design location value outside the axis design range (l.141) | also for anisotropic tuple members |
| 3.5 | info | emitted **together with every 3.3**, same condition, same details (l.157) | duplicate by construction |
| 3.4 | info | ≥2 instances with identical full design location, one result per location (l.223) | **crashes** when an instance has no familyName (see §5) |
| 3.6 | info | `not instance.familyName` (l.187) | |
| 3.7 | info | `not instance.styleName` (l.199) | |
| 3.8 | info | `not instance.filename` (l.211) | noisy for DS5 files: filenames are optional there |
| 3.10 | info | the document has no instances (l.71) — returns | |

Input: DS. User-location instances are mapped to design space by fontTools' avar1
`map_forward` (extrapolating past the last map point); **avar2 mappings are not applied**.
In split mode fontTools' `splitInterpolable(makeNames=True)` synthesises family/style names and
filenames from STAT labels, so 3.6/3.7/3.8 are quieter for documents that happen to have a discrete
axis than for the same instances in a non-discrete document.
Not checked: instance names vs STAT labels, postscript names, duplicate names, `<variable-fonts>`
subsets, whether instances fall inside a variable font's axis-subset.

### Category 4 — Glyphs (`checkers/glyphs.py`), needs UFO

Runs per interpolable slice (`_slices`, l.187-219: `splitInterpolable` again, even without
discrete axes). Needs ≥2 loaded sources overall and ≥2 in the slice (l.228-233).
Default = `sub_doc.findDefault()` matched by path+layer, falling back **silently** to the first
source of the slice (`base.py:278-293`). Glyph presence is per master and layer-aware
(`_own_keys`/`_own_glyph`, base.py:342-370). A glyph is compared **only across the sources that
contain it**; absence from a master is judged by 4.7/4.11/4.13, not by the compatibility checks.

| code | sev | trigger | notes |
|---|---|---|---|
| 4.0 | warn | contour counts differ among sources that have the glyph (l.518) | |
| 4.1 | warn | a component base-glyph **name** present in fewer sources than have the glyph (l.546) | presence by name only; count/order/transform differences fall to 4.9 or go unseen (transform never) |
| 4.2 | warn | an anchor **name** present in fewer sources than have the glyph (l.572) | docstring says "different number of anchors"; it compares names, so duplicate anchors and positions are not checked |
| 4.3 | warn | per-contour on-curve counts differ — only computed when 4.9 fires (l.664) | contour index aligned naïvely |
| 4.4 | warn | per-contour off-curve counts differ — only when 4.9 fires (l.688) | untested |
| 4.5 | warn | per-contour tuple of on-curve segment types differs — only when 4.9 fires (l.712) | untested |
| 4.7 | **error** | glyph exists in some slice source but not in the default (l.252, `_missing_in_default_result` l.272) | glyph then skips every other check |
| 4.8 | warn | a contour's signed-area sign (shoelace over **all** points incl. off-curves) differs across sources; zero-area contours skipped (l.736, l.821-842) | `MIN_AREA_THRESHOLD=1000` is defined but unused; untested |
| 4.9 | warn | `DigestPointStructurePen` digests differ (l.605) — segment type per point + component base names, no coordinates, no transforms | untested directly |
| 4.10 | warn | sorted unicode tuples differ (l.773) | untested |
| 4.11 | **error** | `axis_span_gaps()` finds an axis end the glyph's masters do not reach, and the glyph varies on that axis (l.306-364) | see §2 |
| 4.12 | warn | glyph has no contours and no components in some masters, drawn in others; one result per empty master (l.393-427) | |
| 4.13 | warn | glyph present in exactly one master of the slice (the default) while the slice has more (l.329-333, l.366-391) | docstring says "information", but no severity override → shows as **warn** |

Not emitted: 4.6. Discrepancies with the docstring/README:
- Module docstring (l.7-17) lists only 4.0-4.10 and describes **4.7 as "Default glyph is empty"**.
  The code emits 4.7 for a glyph *absent* from the default; a glyph *empty* in the default (or
  any master) is reported as **4.12**. README says "codes 4.0 to 4.10 mean what they mean in
  designspaceProblems"; the docstring's own description of 4.7 is not what the code does.
- `GlyphProblemType.START_POINT_MISMATCH` / `StartPointDifference` exist in `model.py` but are
  never produced.
- Glyph widths, anchor positions, component transforms, point coordinates, `public.skipExportGlyphs`,
  `mutedGlyphNames` are **not** examined anywhere.

### Category 5 — Kerning (`checkers/kerning.py`), needs UFO

Layer sources are excluded throughout (l.83). If no non-layer source has any pairs, the whole
category returns silently (l.97). Default = `findDefault()` on the (whole or slice) document,
matched among non-layer sources, fallback first source.

| code | sev | trigger |
|---|---|---|
| 5.0 | **error** | a non-default full-UFO master has zero pairs while the default has pairs (l.161); skips its other group checks |
| 5.1 | warn | default has no pairs (l.112) — reachable only when some other master has pairs |
| 5.2 | warn | a group present in both with different member sets (l.237) |
| 5.3 | warn | a `public.kern*` group in a master that the default lacks (l.199) — the comment says "information", but no override → warn |
| 5.5 | warn | default has no `public.kern*` groups (l.127) |
| 5.6 | **error** | a master with pairs but no `public.kern*` groups while the default has some (l.181) |
| 5.7 | info (override) | same members, different order (l.215) |
| 5.8 | **error** | within one master, a glyph in two `public.kern1.*` (or two `kern2.*`) groups (l.279-322) |
| 5.9 | **error** | kerning keys with an empty/non-string side, read around fontParts' normaliser (l.94, l.255; `kerning_data.py`) |

Not emitted: 5.4 (pair-level; deliberately). Docstring (l.7-14) omits 5.8/5.9. Groups the default
has but a master lacks are *not* reported (only the reverse, 5.3). Kerning values, `muteKerning`,
and non-`public.kern` groups are ignored. Only groups prefixed `public.kern` are considered.

### Category 6 — Font Info (`checkers/fontinfo.py`), needs UFO

**Default = `entry.sources[0]`** (l.64, `# TODO: Use doc.findDefault()`) — not the real default.

| code | sev | trigger |
|---|---|---|
| 6.1 | error | `sources[0].info.unitsPerEm is None` (l.69) — returns |
| 6.0 | error | a source's UPM ≠ sources[0]'s UPM (l.87) |
| 6.2 | warn | `versionMajor` ≠ sources[0]'s (l.108), only when sources[0] has one; `None` in the other counts as different |

Not emitted: 6.3 (docstring l.15). README row "required fields, values that differ" amounts to:
UPM on the first source, and `versionMajor`. Layer sources are compared too (same UFO, so they
simply agree). Probe p9 (first source is not the default and has UPM 2048): the two *correct*
masters are the ones blamed ("L.ufo: unitsPerEm differs: 1000 (default: 2048)").

### Category 7 — Rules (`checkers/rules.py`), DS (+UFO for 7.5)

| code | sev | trigger |
|---|---|---|
| 7.0 | info | no non-empty condition in any conditionset (l.464) |
| 7.1 | info | condition names an axis not in the doc (l.531) |
| 7.2 | info | condition `minimum > maximum` (l.544) |
| 7.3 | info | condition min below / max above the axis design range from map outputs (l.563, l.580) |
| 7.4 | info | rule has no `subs` (l.481) |
| 7.5 | info | a sub's source or target glyph not in the **union** of all masters' glyph sets (l.491-522); skipped when no fonts are loaded |
| 7.6 | info | duplicate rule name (l.442) |

A rule with **no `<conditionset>` crashes the whole rules phase** (see §5). Not checked: rule
overlap/ordering, `rulesProcessingLast`, conditions vs instance positions, substitution chains,
target present in every master.

### Category 8 — Features (`checkers/features.py`), needs UFO

Operates on one source per UFO path, layer sources excluded (`_ufo_sources`, l.139-151).

| code | sev | trigger | inputs |
|---|---|---|---|
| 8.0 | info | feaLib `Parser(..., glyphNames=font.keys(), followIncludes=True)` raises on a non-empty `features.fea` (l.109) | UFO |
| 8.1 | info | a top-level `feature kern/mark/mkmk` block exists in some but not all UFOs with non-empty features (l.121-137) | UFO |
| 8.3 | **error** | `ufo2ft.featureCompiler.tokenizeLayoutFeatures` of non-default masters are neither all equal to the default's nor all empty; one result per (slice) document (l.153-250); skipped entirely if any master fails to tokenize, or ufo2ft absent | UFO + ufo2ft |

8.2 retired (was name-based "sparse"). Module/class docstrings list only 8.0/8.1.
Generated features (kern/mark writers, GDEF), feature-variations from rules, and compile errors
are not examined.

### Category 9 — Glyph Order (`checkers/glyphorder.py`, `glyph_order.py`), needs UFO

Per slice (`splitInterpolable(entry.doc)`); slice skipped if `findDefault()` is None.

| code | sev | trigger |
|---|---|---|
| 9.0 | warn | a name in another master's glyph order (`public.glyphOrder`, else its keys) that is not in the default's (l.370-428, `extras_for_subdoc`) — overlaps 4.7 by design |
| 9.3 | warn | after intersecting both orders, the common names are in a different sequence; one result per master, naming the first divergence (l.430-544); layer masters skipped |

9.1 retired (still defined, not run; test asserts it is absent), 9.2 never implemented.
9.3 fires whether or not features would actually be compiled per master (8.3 is what decides
whether it matters). Detail: for a layer master, `source_order()` returns the *parent UFO's*
glyphOrder (it checks `safe_glyph_order(source.font)` first), so 9.0 can attribute the parent's
names to a layer master; `owns_glyph` then filters the location list.

---

## 2. How the engine works

**Loading (`loader.py`).** `DesignSpaceDocument.fromfile()` (fontTools designspaceLib), then
each source's UFO is opened with `fontParts.world.OpenFont`, cached by resolved path so layer
sources share one font object. Sources with no path, a missing UFO, or a UFO that fails to open
are **dropped with a log warning** (l.133-146) — the document-level checker (2.1) is what reports
them. `Source.location` is the raw `descriptor.location` (partial DS5 location as written).

DS5 elements, as far as the linter is concerned:
- **discrete axes** — loaded; drive the split (below). Their own `values`/`default` are never validated by this tool.
- **labels / STAT (`<labels>`, `<label>`, location labels, elidedfallbackname)** — loaded by fontTools, ignored by the linter (only used indirectly by `splitInterpolable(makeNames=True)` to synthesise instance names).
- **`<variable-fonts>` / axis-subsets** — loaded, ignored. A malformed one makes fontTools refuse the file → CLI exit 2 (probe p5 first version).
- **`<mappings>` (axisMappings, avar2)** — loaded, **ignored** (§3).
- **hidden axes** — loaded, treated as ordinary continuous axes.
- **instances by user location / location label** — resolved through `getFullDesignLocation` (avar1 only).
- `mutedGlyphNames`, `muteKerning`, `muteInfo`, `rulesProcessingLast`, `lib` — never referenced.
Nothing in the DS5 set crashed on its own.

**Phases (`engine.py`).** Fixed order (l.42-53): file, geometry, sources, instances, glyphs,
kerning, fontinfo, rules, features, glyphorder. Each phase is wrapped in `try/except Exception`
that **logs a warning and moves on** (l.300-302, 400-402): results already yielded by the phase
survive, the rest of the phase is lost. A structural result in file/geometry/sources **stops the
run** (l.304-308).

**Discrete split.** If any axis has non-empty `values` (l.460-473) the run goes through
`_run_checks_split` (l.320-410): `fontTools.designspaceLib.split.splitInterpolable(doc)` (with its
defaults `makeNames=True, expandLocations=True`) and every phase runs once per slice, with a
filtered entry (sources matched by path+layer) and the sub-document; results get
` [Axis:value]` appended to `location` and `raw_data["discreteLocation"]`. The sub-documents drop
discrete axes, subset rules, expand source/instance locations, and keep avar2 mappings only when
all their axes survive. Document-level findings (3.10, 7.x …) are repeated per slice.
**Bug:** `_structural_problem_found` is reset only once per run (l.220), not per slice, so after
one slice has a structural finding every later slice stops right after its `file` phase — its
sources, glyphs, etc. are never checked (examples below).

**Default source.** Four different rules coexist:
- 2.5: `copyInfo` or exact explicit match, else `doc.findDefault()`.
- glyphs, kerning, features: `doc.findDefault()` (slice doc) matched by path+layer, else first source — silently.
- glyph order: `sub_doc.findDefault()`, slice skipped if None.
- font info: `entry.sources[0]`, always (bug/TODO).
`findDefault()` compares `getFullDesignLocation` with the axis defaults mapped by avar1.

**Walking locations/regions.** There is no region model. Checks are either per axis (min/max/default,
map lists), per source location against per-axis design min/max, or set comparisons across masters.
The only positional reasoning is `axis_span.py`.

**`axis_span.py`.** `axis_span_gaps(doc, all_descriptors, covering_descriptors, tol=1e-6)`
(l.49-128): for each continuous axis (`not axis.values`, l.26-33) takes full design locations
(`descriptor.getFullDesignLocation(doc)`, l.36-46) of all slice sources and of those containing the
glyph. If the covering sources span no range on that axis (`max-min <= tol`) the axis is skipped
(glyph does not vary there). Otherwise reports `minimum` if `min(covered) > min(all)+tol` and
`maximum` if `max(covered) < max(all)-tol`. Axes are independent: corner masters are never
required; missing from an interior master is never reported. Only masters that were actually
loaded take part (unloaded descriptors are not in `pairs`), so the "required" extent shrinks when
UFOs are missing. Called by 4.11 only when the glyph is missing from at least one master and
present in ≥2. The span is computed over **all** axes, hidden ones included; no avar2 awareness
(a glyph's reach in hidden-axis design space is what matters for avar2 fonts, so this is
consistent, but mapping-driven reachability is not considered).

## 3. avar2 / hidden axes / HOI

`grep -rniE "axisMapping|avar|hidden|variableFont|axisSubset|locationLabel|labelNames|userLocation|map_forward|mutedGlyph|muteKerning|rulesProcessingLast"`
over `designspace_lint/` and `tests/` returns **nothing** (only the prose word "varLib").
**There is no avar2 support of any kind.** `doc.axisMappings` is never read; hidden axes are never
distinguished from visible ones; no check touches HOI (higher-order interpolation / intermediate
regions) either — nothing reasons about regions, `VariationModel`, or supports.
Probe p3 (hidden axis + avar2 mapping whose output is 5000 on a 0–100 axis, plus two conflicting
mappings with the same input): **no finding**. On the real Amstelvar avar2 designspaces (79–93
axisMappings, 87–89 hidden axes) the linter runs to completion and reports only master-level
issues; the mappings are invisible to it. The only avar2-relevant consequence is incidental:
because hidden axes are ordinary axes to fontTools, 4.11's span logic and 2.x range checks apply
to them.

## 4. What it cannot see by construction

It never compiles anything (no `varLib.build`, no `ufo2ft.compile*`, no `VariationModel`). So it
cannot see:
- anything produced only by the build: fvar/avar/avar2/STAT/name/OS2 tables, instance naming as
  compiled, `GSUB` FeatureVariations from rules (overlap, ordering, `rulesProcessingLast`),
  generated kern/mark/mkmk/GDEF from the feature writers, `ShouldBeConstant`/
  `InconsistentGlyphOrder` merge errors themselves (8.3/9.3 only predict them);
- point-level interpolation compatibility beyond structure digests: start-point rotation,
  contour order swaps, wrong point correspondence, kinks/overweight (what
  `fontTools.varLib.interpolatable` reports), component transform differences, width/advance
  and anchor-position behaviour, glyph-level metrics;
- the effect of avar2 mappings or HOI: reachability of hidden-axis regions, whether a mapping
  sends the default somewhere else, whether masters cover the regions that mappings land in,
  monotonicity of the composed mapping;
- per-master behaviour after `mutedGlyphNames`/`muteKerning`/`muteInfo`, `public.skipExportGlyphs`,
  production names;
- instance output (it never generates instances), and any check that needs the whole
  designspace when UFOs are missing (see §5: the run stops).

## 5. Robustness runs

CLI: `python -m designspace_lint.cli --json <ds>` from the scratch venv. Per-run JSON/stderr in
`audit/runs/`, probes in `audit/probes/` (`results.txt`). fontTools Tests/ data is **not installed**
(no `Tests/` in site-packages, no fontTools checkout found on disk) — skipped.

| designspace | axes (disc/hidden) | avar2 maps | sources (UFOs present) | exit | time | findings |
|---|---|---|---|---|---|---|
| DSSketch/examples/AmstelvarA2-Roman_avar2 | 67 (0/0) | 29 | 126 (0) | 1 | 0.2 s | 126× 2.1, run stopped |
| examples/avar1, avar2, avar2Fences, avar2OpticalSize, avar2QuadraticRotation | 3 | 0/11/5/2/2 | 0 | 1 | 0.1 s | 1× 2.0 each, run stopped |
| examples/avar2-RobotoDelta-Roman | 39 | 38 | 75 (0) | 1 | 0.1 s | 75× 2.1, run stopped |
| examples/MegaFont-3x5x7x3-Variable | 4 | 0 | 72 (72) | 0 | 0.7 s | 0 |
| examples/MegaFont-WithSkip | 4 | 0 | 72 (72) | 0 | 0.6 s | 0 |
| examples/SuperFont-6x2 | 2 (1 discrete) | 0 | 6 (6) | 0 | 0.2 s | 0 |
| examples/TestFont-ElidableScenarios | 3 (1) | 0 | 3 (0) | 1 | 0.1 s | 2× 2.1 (3rd missing UFO not reported — slice leak) |
| examples/TestFont-MultiElidable | 3 | 0 | 2 (0) | 1 | 0.1 s | 2× 2.1 |
| examples/TestFont-Skip | 2 (1) | 0 | 6 (0) | 1 | 0.1 s | 3× 2.1 — only the upright slice; 3 italic UFOs unreported |
| examples/TestFont-SkipValidation | 2 (1) | 0 | 8 (0) | 1 | 0.1 s | 4× 2.1 of 8 missing — same leak |
| googlesans-flex/GoogleSansFlex | 6 (0/2) | 0 | 657 (657; 441 layer sources in 234 UFOs) | 0 | 132 s, 3.3 GB RSS | 0 |
| amstelvar-avar2/Italic/AmstelvarA2-Italic | 91 (0/87) | 79 | 136 (136) | 1 | 83 s, 2.1 GB | 335: 9×3.8, 6×4.10, 3×4.11, 9×4.8, 24×5.0, 135×6.2, 1×8.3, 32×9.0, 116×9.3 |
| amstelvar-avar2/Roman/AmstelvarA2-Roman | 93 (0/89) | 93 | 138 (138) | 1 | 95 s, 2.4 GB | 300: 9×3.8, 1×4.10, 2×4.13, 12×4.8, 26×5.0, 137×6.2, 1×8.3, 13×9.0, 99×9.3 |
| amstelvar-avar2/Roman/AmstelvarA2-Roman_v2 | 73 (0/62) | 83 | 150 (137) | 1 | 0.6 s | 13× 2.1, run stopped: 137 present UFOs never checked |
| amstelvar-avar2/Italic/reference/Amstelvar-Italic | 3 | 0 | 27 (27) | 1 | 17 s, 0.46 GB | 1673 (507× 4.1, 230× 4.9, 162× 4.12, 160× 4.10, …, 26× 8.0) |
| amstelvar-avar2/Roman/reference/Amstelvar-Roman | 3 | 0 | 27 (27) | 1 | 17 s, 0.47 GB | 2013 (846× 5.7 info, 280× 4.12, 163× 4.1, 160× 5.2, 136× 4.9, …, 1× 5.9) |

No process crashed (no traceback, no exit 2 on well-formed files). The 6.2 counts on Amstelvar are
genuine: sources[0] is also the real default there (versionMajor 1 vs 0/None elsewhere).

**Missing UFOs.** The loader drops them with a stderr warning; 2.1 is structural, so the run
**stops after the sources phase**: no instance, rule, glyph, kerning, font-info, feature or
glyph-order check runs, even for the UFOs that are present (Roman_v2: 13 missing, 137 present,
nothing else checked). A designspace with no `<sources>` (avar2 test files) stops at 2.0. So on
DS-only inputs the tool can only ever report categories 0-2; category 3 and 7 checks, which need
only the XML, are never reached. Probe p12 (one missing UFO, a rule on an undefined axis, an
instance at Weight 5000): only 2.1 reported.

**Phase crashes found by probes** (the engine swallows them as a log warning — printed on stderr
through logging's last-resort handler — and the rest of the phase is lost; exit code still 1/0):
1. **Rules phase** — a `<rule>` without `<conditionset>`: `conditionSets == []` makes
   `conditions = [[rule.conditions]]` → fontTools' `RuleDescriptor` has no `conditions`, so
   `[[[]]]`; 7.0 is yielded, then `_check_condition([])` calls `[].get` → `AttributeError`
   (`rules.py:458-477`, `:526`). Every later rule goes unchecked (probe p1 lost a 7.3).
2. **Instances phase** — an instance without `familyname` that shares a location with another:
   `inst.familyName + " " + …` in 3.4's `raw_data` raises `TypeError` (`instances.py:236`);
   3.4 is lost (probe p2).
3. **Discrete split state leak** — `_structural_problem_found` not reset per slice
   (`engine.py:220`, `:405-410`); after the first slice with a structural finding, later slices
   run only their `file` phase (probe p4 and the TestFont examples).

Other noise: fontTools `statNames` warnings ("Cannot look up family name…") are printed on stderr
for documents without a default-source familyname, because the glyphs and glyph-order checkers
call `splitInterpolable(makeNames=True)` even when there is no discrete axis.

Cost: glyph phase dominates; ~0.6-0.7 s per master for Amstelvar, ~0.2 s per source for
GoogleSansFlex, with every UFO fully opened through fontParts (RSS 2-3.3 GB on the big families).

## 6. Test coverage

66 tests pass (`pytest` on the copy, 0.16 s). All use in-memory fakes (`tests/fakes.py`);
no test runs the loader, the CLI, the engine/phase logic, the discrete split, or real UFOs.

| module / code | tested? |
|---|---|
| `axis_span.axis_span_gaps` | yes, 10 tests (`test_designspace_axis_span.py`) |
| 4.0, 4.3 | yes (`test_contour_and_point_differences_are_reported`) |
| 4.7, 4.11, 4.12, 4.13 | yes (`test_validator_glyph_presence.py`, incl. discrete slices and layer masters via `GlyphsChecker` directly) |
| 4.1, 4.2, 4.4, 4.5, 4.8, 4.9, 4.10 | **no** assertion |
| 5.0, 5.2, 5.6, 5.8, layer skipping | yes (`test_validator_kerning_groups.py`) |
| 5.1, 5.3, 5.5, 5.7, 5.9 | **no** |
| 8.3 | yes, 8 tests (`test_validator_features_compat.py`) |
| 8.0, 8.1 | **no** |
| 9.3, 9.1-absent, layer masters | yes (`test_validator_glyphorder_rules.py`) |
| 9.0 | **no** |
| 0.x, 1.x, 2.x, 3.x, 6.x, 7.x (FileChecker, AxesChecker, SourcesChecker, InstancesChecker, FontInfoChecker, RulesChecker) | **no tests at all** |
| engine (phase order, structural stop, exception swallowing, discrete split), loader, CLI (exit codes, JSON) | **no** |
| package isolation (no GTK / app imports) | yes, 3 tests |
