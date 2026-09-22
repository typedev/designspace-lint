# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
