# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Every live code is produced by at least one test, and the suite enforces
  it.** A full `pytest` run now fails when a code that is not retired was
  never produced, the same way four checks went silent before 0.1.2. 18 codes
  had no test: 0.0, 1.0, 1.3, 1.8, 1.13, 2.2, 2.7, 3.1, 4.10, 4.17, 5.1, 5.7,
  5.9, 6.1, 6.2, 7.4, 7.6 and 8.0.
- **More locators.**
  - `sourceName` on the per-master kerning (5.x), font info (6.x) and
    unreadable-features (8.0) findings.
  - `instanceIndices` on 10.2: the instances whose labels are all elided.

### Fixed

- **2.7 (layer not found) was skipped when a checker was given only a
  document**, even though the source path fontTools reads is absolute. It now
  needs a document folder only for a relative path.

### For consumers

- New locators: `sourceName` on 5.0–5.3, 5.5–5.9, 6.0–6.2 and 8.0, and
  `instanceIndices` on 10.2. `raw_data` gained keys and lost none.

## [0.6.0] - 2026-09-28

A public surface for tools that show the findings. It was agreed with
Font-Rover, the editor the checks came from, so that a new release needs no
code changes on its side.

### Added

- **`designspace_lint.codes.CODES`**, a catalogue of every
  `(category, code)`. Each entry has a title, a stable `group` slug and group
  title, the default severity and every severity the code can take, the
  phase, whether it needs `interpolatable`, whether it is `retired`, and its
  `locators`.
  - A test keeps the catalogue in step with the source.
  - The suite checks every finding it produces against the catalogue, and a
    run over the audit's probe designspaces exercises most codes for real.
  - Codes that are declared but never reported (1.5, 1.10–1.12, 2.8, 2.9,
    9.1, 9.2) are listed as retired, and their numbers stay taken.
- **Every result from `lint()` carries an explicit `severity`.**
  `effective_severity(result)` gives the same answer for results from a
  checker called directly. The CLI uses it too.
- **Locators**: `raw_data` keys that are guaranteed per code, listed in
  `CODES[...].locators`.
  - 10.0 and the 3.x instance findings now carry `instanceName` and
    `instanceIndex`.
  - 2.x source findings carry `sourceName`.
  - 4.11 carries `axisName`.
- **Scoped runs**: `lint(..., phases=[...], glyphs=[...])`, also on
  `iter_lint`, `lint_path` and `Linter`. "file" and "geometry" always run,
  and `glyphs=` restricts the glyph phases.
- **Public helpers**:
  - `label_for_source`
  - `raw_glyph_order` and `dedupe_glyph_order`
  - `undeclared_axis_dimensions` and `undeclared_axis_dimensions_from_string`,
    which list what fontTools will drop on read and so what a
    `DesignSpaceDocument.write()` would lose.

### Fixed

- **10.0 no longer flags an instance that has localised style names in any
  language.** The split keeps an instance's own localised names whenever there
  are any, and fvar then adds English from `stylename` itself. 0.5.0 skipped
  only an explicit `xml:lang="en"`, so a document with German names alone got
  a finding for every instance. The DSSketch agent reported it, and it is
  confirmed in `designspaceLib/split.py` and `varLib._add_fvar`.

### For consumers

- New public names: `CODES`, `CodeInfo`, `code_info`, `effective_severity`,
  `label_for_source`, `raw_glyph_order`, `dedupe_glyph_order`,
  `undeclared_axis_dimensions`, `undeclared_axis_dimensions_from_string` and
  `StrayDimension`.
- New parameters `phases=` and `glyphs=` on `lint`, `iter_lint`, `lint_path`
  and `Linter`.
- Deprecated, and removed in 0.7:
  - `glyph_order._raw_glyph_order` and `glyph_order._first_wins`; use the
    public names.
  - Calling `GlyphsChecker(...).check_glyphs()` for a partial recheck; use
    `lint(..., phases=["glyphs"], glyphs=[...])`.
- `raw_data` gained keys and lost none.
- No code changed its number, severity or meaning, apart from the 10.0 fix
  above.

## [0.5.0] - 2026-09-28

Prompted by an independent coverage audit (`docs/audit/2026-09-coverage/`).
Every claim acted on here was checked again against fontTools 4.65 and ufo2ft
3.9 source first, often by building the tables in memory (`VERIFICATION.md`
there). Several claims did not hold as written, and one of ours had gone
stale. The new rules were then run over real documents: the Amstelvar A2 and
reference designspaces, GoogleSansFlex, and 72 local DS5 files with labels.

The version jumps from 0.1.2 to 0.5.0. The work was done in steps that were
never published, and the repository still carries v0.3.x tags from the
application these checks were extracted from.

### Fixed

- **Checks no longer disappear silently.**
  - A check that raised used to be logged and dropped, along with the rest of
    its phase, while the exit code looked normal. It is now a finding of its
    own (**0.1**). Three such crashes were real and are fixed as well:
    - a rule with no `<conditionset>` took every later rule with it;
    - two instances at one location with no family name lost 3.4;
    - an instance naming an unknown location label stopped the glyph-order
      phase.
  - **One discrete slice no longer silences the next.** The structural stop
    was reset once per run, not once per slice. After a problem in the
    upright, every italic slice was checked for its file and nothing else.
  - **A designspace with only discrete axes** reported "no axes defined" in
    every slice and then stopped. Each slice has no axes by construction, so
    the document is now checked once for its axes, before it is split.
  - **A bad `<variable-fonts>` entry no longer blanks the discrete slices.**
    fontTools resolves the declared variable fonts while it splits the
    document, and raises on 1.19 or 1.20. The slices are now cut from a copy
    that declares none.
- **A missing UFO no longer stops the run.** 2.1 and 2.2 are still errors, but
  the masters that did open are checked. On Amstelvar A2 v2, 13 of 150 UFOs
  are missing and the other 137 used to go unexamined. 4.11 says when its span
  was measured without some masters.
- **2.3 and 3.2 could never fire.** fontTools drops a location dimension that
  names an undeclared axis while it reads the file. What is left is a log
  warning and a source quietly moved to that axis' default, usually after an
  axis was renamed. Both checks now read the file itself, and 3.2 covers
  location labels too.
- **Duplicate source locations are compared as varLib compares them (2.6)**,
  with omitted axes filled in. `{Weight: 900}` and `{Weight: 900, Width: 100}`
  at the default Width are one location to varLib ("Locations must be
  unique"), and they used to be two to us.
- **An empty glyph is judged the way varLib builds it (4.12).** When the
  default draws a glyph, varLib reads an empty copy in another master as
  missing and interpolates the outline across it. The copy's advance width
  still interpolates, because HVAR only skips 0xFFFF. So:
  - such a master is no longer compared in the outline checks, which used to
    report 4.0/4.2/4.9 incompatibilities the build never sees (on the Amstelvar
    reference Roman, 4.9 went from 136 to 106 and 4.0 from 82 to 53);
  - it leaves an axis-end gap (4.11) like a missing glyph;
  - 4.12 now says the outline skips the master while the advance width does
    not. It used to say "the shape collapses", which was wrong.
- **Rule glyphs are checked against the default master (7.5)**, minus
  `public.skipExportGlyphs`, which is what varLib checks them against.
  Checking the union of all masters passed a glyph drawn only in a sparse
  master, and the build then refused the rule. This is now an error.
- **7.0 reported the wrong rule.** It flagged an empty `<conditionset/>`,
  which the spec defines as always-on. It missed the case that matters: a rule
  with no conditionset at all, which never applies and which fontTools drops.
- **Font info is compared against the designspace default (6.x)**, not against
  whichever source is listed first.
- **The whole-document checks run once in every designspace**, not once per
  slice.

### Changed

- **A master with no kerning (5.0) is a warning, not a structural error**, and
  says what happens. Since ufo2ft 3.9 (ufo2ft#995) such a master is skipped and
  the kerning interpolates across it. Up to 3.8, every pair resolves to 0
  there, which is what the old message described.
- **A map without an entry at the axis minimum or maximum (1.6, 1.7) is an
  error.** varLib refuses to build it. Neither finding stops the run.

### Added

- **Axes and avar2 (category 1)**
  - **1.15**: an axis map with no entry at the axis default. varLib refuses
    it: "there must be a mapping for the axis default value".
  - **1.16**: a discrete axis whose default is not one of its values. The
    masters at the default fall into no slice.
  - **1.17**: no continuous axis at all. This is information only, because a
    family of static fonts is a fine thing to describe this way.
  - **1.18**: an avar2 mapping whose input is the default location. varLib
    keeps it only as the base of a variation store that it then discards, so
    the mapping never applies and every other mapping is measured from it.
    With Weight 100/400/900, adding `400 → 650` to `900 → 700` moves
    normalized 1.0 from 0.6 to 0.1. Found in Amstelvar A2 v2
    (`YTOS 11 → 10`).
  - **1.19–1.22**: the variable fonts a DS5 document declares.
    - 1.19: an unknown axis; splitting raises on it.
    - 1.20: a range over a discrete axis; splitting raises on this too.
    - 1.21: a subset that selects nothing, so the font is silently never
      built.
    - 1.22: `userdefault="0"`, which fontTools reads as not set
      (`userDefault or axis.default`).
  - **1.23**: two avar2 mappings whose inputs normalize to one point. varLib
    stops with "Locations must be unique", and that includes two
    default-input mappings on different axes.
  - **1.24**: a mapping that names an unknown or discrete axis. The split
    drops it, silently for an input. When the name is an axis tag, the
    finding suggests the axis name.
  - **1.25**: a mapping value past the axis end, which is clamped. This hits
    51 of 93 mappings in the Amstelvar A2 Roman and 37 of 100 in the Italic.
  - **1.26**: an output past the outermost master on that axis. It moves
    nothing, or tapers back toward the default.
  - **1.27**: one mapping's output read as another's input. Deltas are
    evaluated before avar2 applies, so the chain never fires.
  - **1.28**: a hidden axis with masters that no mapping touches
    (information).
  - **1.29**: a visible axis that avar2 makes run backwards. This is decided
    on the avar table compiled in memory from the document, and only when a
    mapping writes to a visible axis.
- **Sources and instances (categories 2, 3)**
  - **2.10 / 3.11**: a source or instance at a discrete-axis value the axis
    does not declare. It belongs to no slice, and fontTools drops it without a
    message.
  - **3.12**: an instance naming a location label that does not exist. The
    file reads, but the split and the build fail on it.
  - **3.13**: two instances with one family and style name at different
    locations.
- **Point by point, on request: `--interpolatable`** (`lint(...,
  interpolatable=True)`). This runs fontTools' `varLib.interpolatable` over
  the masters that are already open, and catches masters that agree on every
  count but interpolate badly.
  - **4.14**: contours in a different order.
  - **4.15**: a contour that starts at a different point, or runs the other
    way.
  - **4.16**: a contour that thins out halfway.
  - **4.17**: a contour that kinks halfway (information).
  - **4.18**: glyphs left unchecked for want of a solver (scipy or munkres;
    the new `interpolatable` extra installs munkres).

  A problem shared by several master pairs is one finding.
  - **Amstelvar reference Roman:** 8 × 4.14, 16 × 4.15, 25 × 4.16 and
    1 × 4.17. The run takes 27 s instead of 13 s.
  - **GoogleSansFlex** (657 masters, where 0.1.2 found nothing): reversed and
    rotated start points in 4 glyphs, `backslash` among them, contour order in
    1 and thinning in 3. The run takes 5 min 20 s.
- **7.7**: two rules that substitute one glyph where their regions overlap.
  varLib does not settle this by declaration order. It numbers the lookups by
  sorting their substitutions, so with `a → a.zzz` declared before
  `a → a.aaa`, the variable font shows `a.aaa` and static instances show
  `a.zzz`. The finding names the rule the variable font will use.
- **Labels, a new category 10**: what the build makes of DS5 axis and
  location labels.
  - **10.0: the instance name the variable font actually gets.** When a
    document has labels, splitting it for the build names each instance from
    the labels at its location, and a `stylename` without `xml:lang="en"` is
    replaced by that name in fvar. This is an error when the name is empty,
    which happens when every label there is elidable and there is no
    `elidedfallbackname`. In the local corpus, 50 of 72 labelled documents
    give their Regular an empty name, and 54 rename at least one instance.
  - **10.1**: a value no label covers. It drops out of the derived name.
  - **10.2**: elidable labels with no `elidedfallbackname`.
  - **10.3**: a label outside its axis or outside a declared variable font. It
    is left out of STAT.
  - **10.4**: a location label that leaves an axis out, so it never names an
    instance.
  - **10.5**: range labels that are inverted, exclude their own value,
    overlap, or also carry a link (STAT then drops the range).
  - **10.6**: style links that point nowhere, or are missing while instances
    depend on the labels for them.
  - **10.7**: two labels at one value, and a discrete value without a label.
- **README: "What it does not see"**: generated features, compiled-table
  limits, renderers, muting. These are the things only a built font shows.

## [0.1.2] - 2026-09-23

### Fixed

- **Four checks had silently stopped working against fontPens 0.4** (4.0
  contour count, 4.3 on-curves, 4.4 off-curves, 4.5 curve type). They read a
  `DigestPointStructurePen` digest and matched on `("beginPath", ...)` tuples;
  fontPens 0.4 emits bare strings, so the parser found no contours and the
  four checks reported nothing — no error, no warning, four checks quietly
  doing nothing. They read the glyph directly now, which is simpler and not a
  bet on another project's internal format. The digest is still used where it
  belongs: as an opaque value for comparing structures (4.9).

  Found by comparing a run inside a host application (fontPens 0.2.4) with a
  run from the command line (0.4.0) over the same designspace: 2013 findings
  against 1821. The suite passed either way, because nothing asserted those
  four codes. Something does now.

## [0.1.1] - 2026-09-23

Found by running 0.1.0 over [Amstelvar](https://github.com/googlefonts/amstelvar-avar2),
a parametric family with 91–93 axes and up to 150 masters — a shape nothing in
the original test set resembled. Four of its five designspaces exposed a
different fault.

### Fixed

- **A source that does not name every axis is no longer an error (2.3).**
  Designspace 5 lets a source list only the axes it is not default on, and
  fontTools fills in the rest — `findDefault` itself relies on that. Reading an
  omitted axis as missing produced **1518 structural errors** on a 93-axis
  designspace and stopped the run before a single glyph was compared. What is
  reported now is the real error: a location naming an axis the document does
  not have.
- **An axis gap needs the glyph to vary on that axis (4.11).** A glyph whose
  masters all sit at one coordinate on an axis carries no delta along it, so
  nothing fades out and nothing reverts; only a glyph that varies and then
  stops short snaps back to the default master's shape. The old reading called
  every untouched glyph in a parametric family a gap: **18609 findings** on the
  italic sources, all of them meaning "this master does not change this glyph",
  which is what the arrangement is for.
- **A malformed kerning key no longer costs the whole kerning category (5.9).**
  One Amstelvar master has a pair with an empty first side; fontParts refuses
  the entire kerning object over it, and the phase died halfway, silently
  taking 517 findings with it. The kerning is now read around the normalizer,
  the unreadable keys are reported as a problem of their own, and the pairs
  that can be read are still checked.

### Added

- **4.13, a glyph drawn only in the default master.** It never varies, which
  is right for `.notdef`, `.null` and composed-accent helpers and an oversight
  for anything else. Reported once per glyph, as information. Previously these
  arrived as one axis-end error per axis: 25 such glyphs produced 150 errors.
- **`CheckResult.severity`**, an optional per-check override of the severity
  the category implies.

### Changed

- **Group members in a different order is informational (5.7).** ufo2ft sorts
  a group's members before use (`tuple(sorted(members))`), so the order never
  reaches the build. It is worth knowing when reading a diff of `groups.plist`
  and not worth an alarm — it was 846 of 1821 findings on one designspace,
  against 43 structural ones.

## [0.1.0] - 2026-09-22

First release. The checks were extracted from the font editor
[font-rover](https://github.com/typedev/font-rover), where they grew out of a
reimplementation of [designspaceProblems](https://github.com/LettError/DesignspaceProblems)
by Erik van Blokland — see [NOTICE](NOTICE).

### Added

- Ten check categories over a designspace and its UFO masters: file, axes,
  sources, instances, glyph compatibility, kerning, font info, rules, features
  and glyph order.
- `lint()` for callers whose fonts are already open, `lint_path()` for callers
  with a path, `iter_lint()` to stream results, and `Linter` for phase and
  progress control.
- A CLI: `designspace-lint <path>`, with `-v`, `-q` and `--json`, exiting 1 on
  problems and 2 when the designspace cannot be read.
- Checks whose rules were verified against fontTools and ufo2ft rather than
  assumed, and whose messages name what the build will do:
  - **4.11** a glyph that does not reach one end of an axis reverts to the
    default master's shape past its last master;
  - **4.12** a glyph left empty next to masters that draw it;
  - **5.0** a master with no kerning, where every pair resolves to 0;
  - **5.8** a glyph in two kerning groups of the same side, whose second group
    ufo2ft discards whole;
  - **8.3** `features.fea` mixed across masters, which silently moves the build
    off the variable-feature path.
- Layer-based designspaces are handled throughout: masters sharing a UFO are
  identified by path *and* layer, and glyphs are read from the layer a master
  actually draws.
- Codes 4.0–4.10 keep the meanings designspaceProblems gave them.
