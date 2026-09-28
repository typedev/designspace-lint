# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.0] - 2026-09-28

avar2 mappings and DesignSpace 5 labels. Before any rule was written, both
areas were researched again against fontTools 4.65 and ufo2ft 3.9 source, with
the tables built in memory. The rules were then run over real documents: the
Amstelvar A2 designspaces for avar2, and 72 local DS5 files with labels.

### Added

- **Category 10, Labels**: what the build makes of axis and location labels.
  - **10.0: the instance name the variable font actually gets.** When a
    document has labels, splitting it for the build names each instance from
    the labels at its location. A `stylename` without `xml:lang="en"` is
    replaced by that name in fvar. It is an error when that name is empty:
    every label there is elidable and there is no `elidedfallbackname`. In
    the local corpus, 50 of 72 labelled documents give their Regular an empty
    name in the variable font, and 54 rename at least one instance.
  - **10.1**: a value no label covers. It drops out of the derived name.
  - **10.2**: elidable labels with no `elidedfallbackname`, which is the root
    of 10.0's empty names.
  - **10.3**: a label outside its axis, or outside a declared variable font's
    range. It is left out of STAT.
  - **10.4**: a location label that leaves an axis out. fontTools compares it
    with full locations, so it never names an instance.
  - **10.5**: range labels that are inverted, that exclude their own value,
    that overlap (the first one in document order wins), or that also carry
    a link (STAT drops the range).
  - **10.6**: a `linkeduservalue` pointing at no label. Also a wght or
    ital/slnt axis with no links while instances depend on the labels for
    style linking.
  - **10.7**: two labels at one value, and a discrete value without a label.
- **1.23–1.29, avar2 mappings.**
  - **1.23**: two mappings whose inputs normalize to the same point. varLib
    stops with "Locations must be unique". That includes two default-input
    mappings on different axes.
  - **1.24**: a mapping that names an unknown or discrete axis. The split
    drops it, silently for an input. If the name is an axis tag, the finding
    suggests the matching axis name.
  - **1.25**: a mapping value past the axis end, which is clamped. In
    Amstelvar A2 this is 51 of 93 mappings in the Roman and 37 of 100 in the
    Italic. Several of them collapse onto one plateau; the v2 Roman has none.
  - **1.26**: an output past the outermost master on that axis. It moves
    nothing, or tapers back toward the default.
  - **1.27**: one mapping's output read as another's input. Deltas are
    evaluated before avar2 applies, so the chain never fires.
  - **1.28**: a hidden axis with masters that no mapping touches
    (information).
  - **1.29**: a visible axis that avar2 makes run backwards somewhere along
    it. This is decided on the avar table itself, compiled in memory from the
    document, and only when some mapping writes to a visible axis. Hidden
    parametric axes may go back and forth.
- **README: "What it does not see"**, the things that only a built font
  shows: generated features, compiled-table limits, renderers, muting.

### Changed

- **3.11, 3.13, 7.7 and the new 1.25–1.27 are warnings.** The CLI treats a
  finding in categories other than 4, 5, 6 and 9 as information unless the
  check says otherwise. These checks did not say, so they printed as
  information.

## [0.4.0] - 2026-09-28

(There is no 0.3: the repository carries v0.3.x tags from the application
these checks were extracted from, so this release takes the next free number.)

The items 0.2.0 left for later. Each rule was checked against fontTools 4.65
and ufo2ft 3.9 source first.

### Added

- **Point by point, on request: `--interpolatable`** (`lint(...,
  interpolatable=True)`). This runs fontTools' `varLib.interpolatable` over the
  masters that are already open. It catches what a structural comparison
  cannot: masters that agree on every count but interpolate badly.
  - **4.14**: contours in a different order.
  - **4.15**: a contour that starts at a different point, or runs the other way.
  - **4.16**: a contour that thins out halfway.
  - **4.17**: a contour that kinks halfway (information).
  - **4.18**: a count of the glyphs that were left unchecked. `interpolatable`
    needs scipy or munkres to match more than six contours, and the new
    `interpolatable` extra installs munkres.

  A problem shared by several master pairs is one finding, which names the
  pair `interpolatable` is surest about and lists the rest.
  - **Amstelvar reference Roman:** 8 × 4.14, 16 × 4.15, 25 × 4.16 and
    1 × 4.17, where 0.2 reported nothing. The run went from 13 s to 27 s.
  - **GoogleSansFlex** (657 masters, 0.2: no findings): reversed and rotated
    start points in 4 glyphs, `backslash` among them, contour order in 1 glyph
    and thinning in 3. Kinks showed up in 58 glyphs. The run took 5 min 20 s.

  A component whose base is missing from a master is drawn as nothing, which
  is what ufo2ft's placeholder for it amounts to.
- **1.19–1.22**: the variable fonts a DS5 document declares.
  - **1.19**: an unknown axis. Splitting the document raises on it.
  - **1.20**: a range over a discrete axis. Splitting raises on this too.
  - **1.21**: a subset that selects nothing. The font is silently never built.
  - **1.22**: `userdefault="0"`. fontTools reads it with
    `userDefault or axis.default`, so it falls through to the axis default.

### Fixed

- **2.3 and 3.2 could never fire.** fontTools drops a location dimension that
  names an undeclared axis while it reads the file. What is left is a log
  warning and a source quietly moved to that axis' default, usually after an
  axis was renamed. Both checks now read the file itself, and 3.2 covers
  location labels too.
- **An empty glyph is judged the way varLib builds it (4.12).** When the
  default draws a glyph, varLib reads an empty copy in another master as
  missing and interpolates the outline across that master. The copy's advance
  width still interpolates, because HVAR only skips 0xFFFF. So:
  - Such a master is no longer compared in the outline checks. It used to
    produce 4.0/4.2/4.9 incompatibilities the build never sees; on the
    Amstelvar reference Roman, 4.9 went from 136 to 106 and 4.0 from 82 to 53.
  - It now leaves an axis-end gap (4.11) like a missing glyph.
  - 4.12 says that the outline skips the master while the advance width does
    not. It used to say "the shape collapses", which was wrong.
- **The whole-document checks run once in every designspace**, not only in
  those with discrete axes. 3.12 is reported once.
- **A bad `<variable-fonts>` entry no longer blanks the discrete slices.**
  fontTools resolves the declared variable fonts while it splits the
  document, and raises on 1.19 or 1.20. The slices are now cut from a copy
  that declares none, so everything else is still checked.

## [0.2.0] - 2026-09-27

Prompted by an independent coverage audit (`docs/audit/2026-09-coverage/`).
Every claim acted on here was checked again against fontTools 4.65 and ufo2ft
3.9 source first (`VERIFICATION.md` there). Several did not hold as written,
and one of ours had gone stale.

### Fixed

- **Checks no longer disappear silently.** A check that raised used to be
  logged and dropped, along with the rest of its phase, while the exit code
  looked normal. It is now a finding of its own (**0.1**). Three such crashes
  were real and are fixed as well:
  - a rule with no `<conditionset>` took every later rule with it;
  - two instances at one location with no family name lost 3.4;
  - an instance naming an unknown location label stopped the glyph-order phase.
- **One discrete slice no longer silences the next.** The structural stop
  was reset once per run, not once per slice, so after a problem in the
  upright every italic slice was checked for its file and nothing else.
- **A designspace with only discrete axes** reported "no axes defined" in
  every slice and then stopped. Each slice has no axes by construction; the
  document is now checked once for its axes, before it is split.
- **A missing UFO no longer stops the run.** 2.1 and 2.2 are still errors,
  but the masters that did open are checked. On Amstelvar A2 v2, 13 of 150
  UFOs are missing and the other 137 used to go unexamined. 4.11 says when its
  span was measured without some masters.
- **Duplicate source locations are compared as varLib compares them (2.6)**,
  with omitted axes filled in. `{Weight: 900}` and `{Weight: 900, Width: 100}`
  at the default Width are one location to varLib ("Locations must be
  unique") and were two to us.
- **Rule glyphs are checked against the default master (7.5)**, which is what
  varLib checks them against, minus `public.skipExportGlyphs`. Checking the
  union of all masters passed a glyph drawn only in a sparse master, and the
  build then refused the rule. Now an error.
- **7.0 reported the wrong rule.** It flagged an empty `<conditionset/>`,
  which the spec defines as always-on, and missed the case that matters: a
  rule with no conditionset at all, which never applies and which fontTools
  drops.
- **Font info is compared against the designspace default (6.x)**, not
  against whichever source is listed first.

### Changed

- **A master with no kerning (5.0) is a warning, not a structural error**, and
  says what happens. Since ufo2ft 3.9 (ufo2ft#995) such a master is skipped
  and the kerning interpolates across it. Up to 3.8 every pair resolves to 0
  there, which is what the old message described.
- **A map without an entry at the axis minimum or maximum (1.6, 1.7) is an
  error.** varLib refuses to build it. Neither stops the run.

### Added

- **1.15**: an axis map with no entry at the axis default. varLib refuses:
  "there must be a mapping for the axis default value".
- **1.16**: a discrete axis whose default is not one of its values. The
  masters at the default fall into no slice.
- **1.17**: no continuous axis at all. This is informational, because a
  family of static fonts is a fine thing to describe this way.
- **1.18**: an avar2 mapping whose input is the default location. varLib
  keeps it only as the base of a variation store that it discards, so the
  mapping never applies, and every other mapping is measured from it. With
  Weight 100/400/900, adding `400 → 650` to `900 → 700` moves normalized 1.0
  from 0.6 to 0.1. Found in Amstelvar A2 v2 (`YTOS 11 → 10`).
- **2.10 / 3.11**: a source or instance at a discrete-axis value the axis
  does not declare. It belongs to no slice, and fontTools drops it without a
  message.
- **3.12**: an instance naming a location label that does not exist. The
  file reads, but the split and the build fail on it.
- **3.13**: two instances with one family and style name at different
  locations.
- **7.7**: two rules that substitute one glyph where their regions overlap.
  varLib does not settle this by declaration order. It numbers the lookups by
  sorting their substitutions, so declared `a → a.zzz` then `a → a.aaa`, the
  variable font shows `a.aaa`, while static instances show `a.zzz`. The
  finding names the rule the variable font will use.

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
