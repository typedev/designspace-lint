# Request from Font-Rover: unicode checks (duplicate / several per glyph)

Date: 2026-11-02. Requested by the Font-Rover session; nothing in this repo
has been changed except this file.

## Why

A UFO with one codepoint on two glyphs makes fontmake stop. The cause is in
`ufo2ft.util.makeUnicodeToGlyphNameMapping`, which walks the glyph order and,
on the second claimant, raises:

```
InvalidFontData: cannot map 'A.alt' to U+0041; already mapped to 'A'
```

designspace-lint has nothing for this. 4.10 `DIFFERENT_UNICODES` compares one
glyph *across* masters, and 9.2 (naming mismatch) is retired. A designspace
with such a master passes the lint and fails at build time, which is exactly
the kind of build consequence this package exists to report.

Font-Rover shipped the checks locally (commit `cdda2b8`) as 4.104
`DUPLICATE_UNICODE` and 4.105 `MULTIPLE_UNICODES` in
`font_rover/designspace_validator/local_checks.py`, with an auto-fix for
4.104 in `fixes.py`. The checks belong here, so CLI users get them before
they run fontmake. Once the lint ships them, Font-Rover will retire its local
codes and point the fix at the lint's.

## Requested codes

Two new codes in category 4 (glyphs). Use the next free numbers (4.22 and
4.23 at 0.8.2). Retired 9.2 stays retired. The numbers are your choice; what
is below is the contract Font-Rover's fix relies on.

### 4.x `DUPLICATE_UNICODE`: codepoint given to more than one glyph

- **Severity:** ERR (structural). The build does not happen.
- **Group:** a new `unicodes` group ("Unicodes"), or `compatibility` if you
  prefer not to add a group. Font-Rover currently shows it under "Unicodes".
- **Scope:** each source's own layer: the default layer of a UFO source, the
  named layer of a layer source. A layer shared by two sources is checked
  once. Background and other non-source layers are not checked: no build
  reads their unicodes.
- **One row per (source, codepoint).**
- **raw_data (locators, guaranteed):**
  - `glyphName`: the first claimant
  - `sourceName`, `layerName` (None for a UFO's default layer)
  - `glyphNames`: every claimant, **in the source font's glyph order**
    (the order ufo2ft reads them in, so `[0]` is the glyph it maps before it
    stops; names not in the order go after, by name)
  - `codepoint`: int
- **Message:** consequence first. Font-Rover's text:
  - description: `U+0041 is given to 2 glyphs: 'A', 'A.alt'`
  - details: `A codepoint maps to one glyph only. fontmake (ufo2ft) stops on
    the second one: "cannot map 'A.alt' to U+0041; already mapped to 'A'".
    Keep the codepoint on one glyph and take it off the others.`
- **Partial recheck** (`Linter(phases=["glyphs"], glyphs=...)`): report a
  codepoint when **any** of its claimants is in the requested set.
  Otherwise the row disappears when only the "other" glyph is rechecked.

### 4.y `MULTIPLE_UNICODES`: glyph with several codepoints

- **Severity:** INFO. It is legal: ufo2ft maps every codepoint of the glyph
  in the same loop (space + no-break space, Delta + Increment, Omega + Ohm).
  It is only worth knowing because tools that read one unicode per glyph
  (`glyph.unicode`) see only the first.
- **One row per (source, glyph).**
- **raw_data:** `glyphName`, `sourceName`, `layerName`, `codepoints`
  (list of int **in the glyph's own order**, so `[0]` is what `glyph.unicode`
  returns).
- **Message:** description `'C' has 2 unicodes: U+0043, U+2102`; details
  explain that it is legal, that one-unicode tools see only the first, and
  that characters meant to look different need their own glyphs.
- No consumer fix is planned.

## Interaction with existing codes

- A duplicate in one master only also yields 4.10 `DIFFERENT_UNICODES` for the
  second glyph, because its unicodes differ between masters. Both rows are
  right: 4.10 says the masters disagree, the new code says this master will
  not build. No suppression is needed.
- Font-Rover's fix keeps the codepoint on the chosen glyph and removes only
  that codepoint from the others, optionally in every master. It skips a
  master where the chosen glyph lacks the codepoint, because the codepoint
  would otherwise leave the font there.

## Implementation notes (from Font-Rover's version)

- Read defcon's `layer.unicodeData` (codepoint → glyph names). defcon builds
  it from the glif headers via `glyphSet.getUnicodes()`, without loading any
  glyph, and keeps it current through notifications when a glyph's unicodes
  change. Fall back to iterating glyphs for a non-defcon layer.
- For 4.y, find the glyphs from the inverted `unicodeData`. Load only those
  glyphs, to read their own codepoint order.
- Use the package's safe glyph-order helper for the claimant order. A
  duplicate entry in `glyphOrder` must not break this check.

## A single UFO (please consider)

Font-Rover also runs these checks on a single UFO, which the lint does not
read. To keep one implementation, please expose the per-layer logic as a
public, toolkit-free function that returns `CheckResult`s. For example:

```python
unicode_findings(layer, *, source_name, layer_name, location, glyphs=None)
    -> Iterator[CheckResult]
```

The engine would call it per source, and Font-Rover would call it for each
compiled layer of a standalone UFO. If you would rather not, Font-Rover keeps
its local copy for single UFOs only.

## Tests worth porting

These come from `tests/test_validator_local_checks.py` in Font-Rover:

- glyphs `Bdup`(U+0042), `A`(U+0041), `A.alt`(U+0041, U+00C0), `B`(U+0042),
  `C`(U+0043, U+2102), glyphOrder `A A.alt B Bdup C`
  - 4.x = `{0x41: [A, A.alt], 0x42: [B, Bdup]}`. Note that `Bdup` sorts after
    `B` by glyph order, although it was created first.
  - 4.y = `A.alt`, `C`. After `C.unicodes = [0x2102, 0x43]` the order is kept.
- a background layer repeating U+0041 on `A` and `A.alt` gives no row
- partial recheck with `glyphs=["Bdup"]` gives only U+0042
- a designspace of two masters, duplicate in one: one row, that master's
  `sourceName`

## Release

As usual: a "For consumers" changelog section listing the new codes and
locators. Font-Rover will then bump the pin, drop local 104/105 from
`LOCAL_CODES` and register its fix under the new `(4, x)` key.
