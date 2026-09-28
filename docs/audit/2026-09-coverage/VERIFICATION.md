# Verification of the audit (27 September 2026)

The audit was written by another agent, and some of its details do not hold:
line numbers in `lint-inventory.md` do not match the code at `2172d82`. Before
acting on it, every claim that drives a change was checked again against
primary sources: the installed fontTools 4.65.0 and ufo2ft 3.9.0, the
DesignSpace XML spec (`Doc/source/designspaceLib/xml.rst`), and small builds in
memory. Paths below are relative to `site-packages/`.

For these claims fontTools 4.60.1, 4.65.0 and 4.66.0 behave the same:
`designspaceLib/split.py` is byte-identical across the three, and the lines
cited in `varLib/__init__.py` and `designspaceLib/__init__.py` are present in
each.

## Confirmed

| Claim | Evidence |
|---|---|
| **AVAR2-01**: a mapping whose input is the default is dropped and shifts every other mapping | `fontTools/varLib/__init__.py:265` adds a `{}` base only when no input sits at the default; `:281` keeps only the VarIdx, so the base value — where a default-input mapping's output lands — is discarded, and the other deltas are taken against it. Built: wght 100/400/900, `900→700` alone gives normalized 1.0 → 0.59998; adding `400→650` gives 1.0 → 0.09998 and leaves 0 at 0. Inputs and outputs are design coordinates (`designspaceLib/__init__.py:2170,2174` read `xvalue` only). An axis left out of an input is unconstrained; left out of an output, it passes through. |
| **AXIS-04**: no `<map>` entry at the axis default | Silent when read. `varLib/__init__.py:220-224` raises `VarLibValidationError: Axis '…': there must be a mapping for the axis default value …` when the map is non-empty. |
| **AXIS-13 / DISC-06**: discrete `default` not in `values` | No read-time check (`designspaceLib/__init__.py:2130-2139`). `splitInterpolable` iterates `values` only, so a source at the default is dropped from every slice, and the slice's `findDefault()` returns None. |
| **DISC-10**: a source or instance at an undeclared discrete value | `split.py:104` builds slices from `values`; `split.py:277` / `:325` filter with exact point equality (`types.py:68-70`). The source falls into no slice, with no message. |
| **All-discrete document**: every slice has no axes | `split.py:200-227` keeps only `Range` axes. `varLib/__init__.py:971-972` then refuses: "Designspace must have at least one axis." |
| **Undeclared axis in a location is stripped on read** (why 2.3 cannot fire) | `designspaceLib/__init__.py:2468-2471`: `log.warning('Location with undefined axis: …'); continue`, with `_strictAxisNames` always True (`:2031`). Applies to sources, instances and labels; not to `<mappings>`. |
| **Unknown location label** on an instance | Read succeeds (`:2571-2576`); `getLocationLabelDescriptor` raises `DesignSpaceDocumentError` (`:810-815`), and so do `getFullDesignLocation`, `splitInterpolable` (`split.py:325`) and `varLib.load_designspace` (`varLib/__init__.py:1003`). |
| **SRC-02/03**: duplicates spelled differently | varLib compares full, normalized locations: `varLib/__init__.py:1003,1026-1042`, then `VariationModel` drops zeros and raises "Locations must be unique." (`varLib/models.py:277-280`). `{Weight: 900}` and `{Weight: 900, Width: <default>}` collide. |
| **RULE-17**: substitution glyphs are checked against the default master | `varLib/featureVars.py:60-63,117-127` checks both sides of every substitution against `font.getGlyphOrder()`, where `font` is a copy of the base master (`varLib/__init__.py:1255`). |
| **ufo2ft feature compatibility** (README claim) | `ufo2ft/featureCompiler.py:483-505`: all non-default equal to the default, or all empty. On failure the build falls back to per-master features (`ufo2ft/_compilers/baseCompiler.py:336-340`), it does not stop. |
| **fontinfo comes from the designspace default** | The VF is a copy of the default master (`varLib/__init__.py:1255`); ufo2ft picks it with `findDefault()` (`ufo2ft/_compilers/baseCompiler.py:294-315`). |

## Wrong or incomplete in the audit

| Claim | What is actually true |
|---|---|
| **RULE-05/06**: "the earlier rule wins silently" | Only for rules with identical regions (`featureVars.py:192-204`). Otherwise each overlap box keeps one lookup per rule, and lookups are numbered in **sorted order of the substitution tuples** (`featureVars.py:536`, `:565-584`). Built: `{a: a.zzz}` on wght 0..1 declared first, `{a: a.aaa}` on 0.5..1 second → in the overlap `a` becomes `a.aaa`. Static instances use `processRules` (`designspaceLib/__init__.py:423-445`), which goes in declaration order, so the variable font and the instances can disagree. |
| **RULE-13**: a rule without `<conditionset>` | It is **dead**, not always-on: `conditionSets == []`, `evaluateRule` is `any([])` = False (`designspaceLib/__init__.py:399-401`), and split drops the rule (`split.py:461`). An empty `<conditionset/>` (`[[]]`) is the always-on form, as the spec says (`xml.rst:468-469`). `RuleDescriptor` has no `conditions` attribute (`:375`). |
| **GLYPH-13† / INFO-07†**: "sentinel mismatch" | gvar leaves a master out when the glyph is missing or has no contours while the default has some (`varLib/__init__.py:342-355`); HVAR leaves it out only when the glyph is missing from `hmtx` or its advance is 0xFFFF (`:703-719`). So an **empty glyph with a real advance** is excluded from outlines and still moves the advance. Built: +300 HVAR delta, no gvar delta. MVAR excludes only a missing table, or `post` underline at `-0x8000`, which ufo2ft writes on layer masters. |
| `interpolatable` timings on GoogleSansFlex | The run in `interpolatable_googlesansflex.log` **crashed**: without `scipy` or `munkres`, contour matching raises for any glyph with 7+ contours (`varLib/interpolatableHelpers.py:158-172`). The 378 s and 918 MB describe a partial run. |
| `kerning.py` uses `sources[0]` as the default | It does not: `_default_font_source()` is used; only `fontinfo.py` falls back to `sources[0]`. |

## A claim of ours that went stale

The README and check 5.0 say a master with no kerning makes "the family's
kerning sag to 0 here". That was true up to ufo2ft 3.8.x. Since **ufo2ft 3.9.0**
(14 July 2026, PR #997 for issue #995) a non-default full source with empty
kerning is **skipped** in the variable kern path
(`ufo2ft/featureWriters/kernFeatureWriter.py:950-958`), and the kerning
interpolates across it. On the per-master path (features not compatible) such a
master is dropped by varLib's merger if it has no GPOS at all, and, per the
comment in ufo2ft, breaks the merge if it has other GPOS (#350; not reproduced
here). Layer sources are skipped for kerning in every version (`:946-948`),
which the check already knew.

## Not re-verified

Catalog rows outside what 0.2.0 changes, the avar2 renderer rows, and the
~40 sub-claims the catalog itself marks UNVERIFIED.

## Second pass: avar2 and labels (28 September 2026)

Re-checked for 0.5.0 against fontTools 4.65, with the avar, STAT and fvar
tables built in memory.

| Row | Finding |
|---|---|
| AVAR2-05 | **Wrong.** Two mappings from the default location, `{wght: default}` and `{wdth: default}`, do not slip through. Both normalize to `{}` and `VariationModel` refuses: "Locations must be unique." (`varLib/models.py:277-280`). |
| AVAR2-07 | **Wrong for real builds.** `build_many` splits the document first, and the split drops a mapping that names an unknown axis (`designspaceLib/split.py:231-241`) — silently for an input, with only a log line for an output. The `KeyError` happens only through `varLib.build()` called directly. |
| AVAR2-10 | **Wording wrong.** A mapping applies at *every* value of an axis its input leaves out, not only at that axis' default. |
| AVAR2-15 | **Confirmed**, and measured. An output past the outermost master is not frozen: the last master's support tapers to 0 at the axis end, so the effect rolls back toward the default. |
| AVAR2-21 | **Confirmed.** A mapping on a discrete axis is dropped by the split. |
| LABEL-03 | **True, low value.** Two labels at one value both reach STAT, and names use the first. |
| LABEL-09 | **True, mostly harmless in STAT.** The real damage from a missing `elidedfallbackname` is in instance names: `getStatNames` joins nothing into `""` (`statNames.py:104-111`), and `split.py:328-352` puts that into fvar. |
| LABEL-11 | **Confirmed.** A label with both a link and a range becomes format 3, and the range is dropped (`designspaceLib/__init__.py:1247-1265`). |
| LABEL-14 | **Confirmed, and the most common failure found.** A `stylename` without `xml:lang="en"` is replaced in fvar by the label-derived name. In a local corpus of 72 labelled DS5 documents, 50 give the default instance an empty name. |
| new | A location label that does not name every axis never names an instance: `labelForUserLocation` compares it with a full location (`designspaceLib/__init__.py:3020-3035`). |
