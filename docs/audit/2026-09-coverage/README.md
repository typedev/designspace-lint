# Coverage audit of designspace-lint 0.1.2 (September 2026)

An independent check of how much of what can go wrong in a DesignSpace project
the linter actually catches, with avar2, HOI and DS5 in focus.

Audited revision: `2172d82` (0.1.2), fontTools 4.66.0.

> **Read `VERIFICATION.md` alongside this.** The claims that drive changes were
> checked again against fontTools and ufo2ft source; several do not hold as
> written here (rule overlap order, rules without a conditionset, the
> kerning and metrics "sentinel" rows, the interpolatable timings).

## Method

The audit ran in three phases, so that the list of failures could not be shaped by
the tool being measured.

1. **Failure catalog**, `failure-catalog.md`. It lists 163 failure modes, 8 of them
   positive controls. They come from primary sources only: the DesignSpace, OpenType
   and avar2 specs, the fontTools / varLib / designspaceLib source, ufo2ft, and
   upstream issues. The research agents were not allowed to open the linter. A
   compliance section inside the catalog reports a breach; that report is a
   misattribution, and a correction note stands at its head.
2. **Linter inventory**, `lint-inventory.md`. What the linter checks, read from its
   code rather than its docs: every code, its trigger (file:line), its inputs, and
   its known bugs. The linter was also run on public designspaces.
3. **Comparison**: `coverage.md`, with per-category detail in `section-*.md`. Every
   catalog row was classified as covered, partial, not covered, or build-only. The
   classification was verified on 64 probe designspaces and 41 probe UFOs rather than
   inferred. The comparison corrected 11 claims in the catalog and the inventory
   (`coverage.md` §6).

## Result

| Category | Rows | Covered | Partial | Not covered | Build-only | Control |
|---|---:|---:|---:|---:|---:|---:|
| **avar2 / HOI** | 35 | **0** | 0 | **32** | 3 | 0 |
| **Discrete axes / DS5 subsets** | 12 | **0** | 0 | 10 | 1 | 1 |
| **Labels / STAT** | 16 | 2 | 0 | 14 | 0 | 0 |
| Axes and axis maps | 18 | 8 | 3 | 7 | 0 | 0 |
| Sources | 14 | 6 | 2 | 4 | 1 | 1 |
| Instances | 9 | 2 | 1 | 4 | 1 | 1 |
| Rules / FeatureVariations | 24 | 8 | 2 | 5 | 6 | 3 |
| Glyph compatibility | 13 | 9 | 0 | 3 | 1 | 0 |
| Kerning / features / glyph order | 15 | 7 | 2 | 1 | 4 | 1 |
| Font info | 7 | 0 | 1 | 3 | 2 | 1 |
| **Total** | **163** | **42** | **11** | **83** | **19** | **8** |

Out of 155 real failure modes: 27% covered, 7% partial, 54% not covered, and 12%
reachable only by building. "Covered" includes cases where fontTools' own reader
rejects the file and the CLI just passes the error on, so the linter's own share is
smaller than 27%.

The linter is strong where it was designed to be strong: glyph, kerning, feature and
glyph-order compatibility across UFO masters. It has no avar2 support at all
(`axisMappings` is never read, and hidden axes are treated as ordinary ones). It does
not process `<variable-fonts>` / `<axis-subset>` either, and it does not validate
discrete-axis values or labels / STAT.

## Most important gaps

The full ranked list of 15, each with a sketch of the check it needs and its
false-positive risk, is in `coverage.md` §4.

1. **AVAR2-01/02: a mapping whose input is the default location.** varLib stores it
   as the VarStore base value and discards it, and every other mapping's delta is
   taken relative to it. There is no warning. Verified on a compiled table by
   `probes/avar2-default-input.py`: with `Weight=400 → YTOS=10` (YTOS default 11),
   YTOS stays 11 at the default and reaches **21.73 instead of 20** at Weight 1000.
   **The AmstelvarA2-Roman designspace in fontTools' test data contains exactly this
   mapping.**
2. **RULE-05/06: overlapping conditionsets on the same glyph.** The earlier rule wins
   by declaration order, silently.
3. **DISC-10: a source at an undeclared discrete-axis value.** No diagnostic anywhere.
4. **RULE-13: a rule without `<conditionset>` crashes the rules phase.** Every later
   rule then goes unchecked.
5. **RULE-17: check 7.5 looks for a substitution glyph in the union of all masters.**
   It does not look in the default master, so sparse masters get a false all-clear.
6. **A document whose axes are all discrete.** Every slice reports "1.0 No axes
   defined", and together with the structural-stop leak this blanks out the whole run.
   This is a linter bug, not a catalog row.
7. **AXIS-04: no `<map>` entry at the axis default.**
8. **`<variable-fonts>` / `<axis-subset>`**: unprocessed.
9. **GLYPH-13† / INFO-07†: gvar and HVAR/MVAR use different sentinels.** A master can
   be excluded from outlines but still count in spacing or underline metrics.
10. **SRC-02/03: check 2.6 misses duplicate locations spelled differently**, e.g. one
    with the default written out and one without.

Silent phase aborts: when one of these fires, the engine logs a warning to stderr,
drops the rest of that phase, and the exit code still looks normal.

- a rule without a conditionset;
- a duplicate location for an instance without `familyname`;
- the structural-stop flag, which is not reset per discrete slice (a later slice
  then runs only its file phase);
- an instance that references an undeclared location label (glyph-order phase).

A missing UFO stops the run after the sources phase: instances, rules and the UFOs
that are present all go unchecked. In the Amstelvar A2 v2 designspace, 13 of 150
UFOs are missing, so the other 137 were never looked at.

## What only a build can show

`coverage.md` §5 covers this. `fontTools.varLib.interpolatable` was run on real
projects:

| Project | interpolatable | the linter |
|---|---|---|
| Amstelvar | 13.3 s | 17 s |
| GoogleSansFlex | 378.5 s / 0.9 GB | 132 s / 3.3 GB |

On GoogleSansFlex, interpolatable found point-rotation problems where the linter
reported nothing (log: `interpolatable_googlesansflex.log`). The recommendation is
to run it behind an opt-in flag. A trial `varLib.build` was not measured, and is only
reasonable as an explicit "verify" mode.

## Confidence

- About 40 catalog sub-claims are marked UNVERIFIED, mostly ufo2ft internals.
  Renderer-specific avar2 behaviour was not tested.
- The catalog's axes/labels and sources/instances parts were researched with less
  supervision than the rest. If a result there looks surprising, check it first.
- Several rows depend on the fontTools version: AXIS-05 and AXIS-15 fail at read time
  on 4.66.0 but were silent on 4.60.1 (see `coverage.md` §6).

## Layout

| Path | Contents |
|---|---|
| `failure-catalog.md` | the 163 failure modes, per category, with evidence |
| `lint-inventory.md` | what the linter checks, from its code |
| `coverage.md` | summary, per-row matrix, probe results, ranked gaps, build-only analysis, corrections |
| `section-*.md` | per-category working notes behind `coverage.md` |
| `interpolatable_googlesansflex.log` | the interpolatable run on GoogleSansFlex |
| `probes/coverage/` | the 64 probe designspaces and 41 UFOs used for the comparison |
| `probes/inventory/` | probes and runner scripts (`make_probes.py`, `run_one.py`) from the inventory |
| `probes/catalog/` | fontTools experiments behind catalog claims |
| `probes/avar2-default-input.py` | stand-alone reproduction of AVAR2-01 |

Paths inside the reports and scripts were rewritten from the audit's scratch directory
to these relative locations. Some scripts still expect to be run from the directory
they were written in, so adjust paths before re-running them.
