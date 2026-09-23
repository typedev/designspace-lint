# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
