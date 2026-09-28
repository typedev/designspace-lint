# designspace-lint

**What a designspace will do when it is built — before you build it.**

A designspace can be perfectly valid and still produce a variable font nobody
intended. A glyph missing from the master at the end of an axis quietly reverts
to the default's shape past that point. An avar2 mapping written at the default
location is thrown away, and every other mapping shifts by what it would have
moved. Two rules that swap one glyph over a shared region are settled by how
their substitutions sort, not by the order you wrote them. A `features.fea`
that differs from the default's pushes the whole build onto another path,
where `varLib` fails somewhere that has nothing to do with the cause. None of
this is an error at build time; the font just comes out wrong.

This library reports those cases, and each report names the **consequence**,
not only the discrepancy.

```console
$ designspace-lint Family.designspace
error 4.11 /eacute Weight 400 of 900: missing at Weight maximum (900); reverts to the default shape past 400
error 1.18 mapping 27: avar2 mapping from the default location is dropped: YTOS 11 -> 10
warn  4.2 /acute missing in 12 sources: anchor '_topacute' missing in 12 sources
3 problem(s), 2 structural
```

Exit code is `0` when clean, `1` when there are problems, `2` when the
designspace cannot be read — so a build script can gate on it directly. A
master that cannot be opened is reported and the others are still checked, and
a check that fails partway is reported as 0.1 rather than dropped, so a clean
result means every check ran.

## Install

```console
pip install designspace-lint            # the checks and the CLI
pip install "designspace-lint[features]"  # + the features.fea comparison (ufo2ft)
pip install "designspace-lint[interpolatable]"  # + a solver for --interpolatable
```

### Point by point: `--interpolatable`

The glyph checks compare structure. Two masters can agree on every count and
still interpolate badly: a contour that starts at another point or runs the
other way twists between them, contours in another order swap shapes, a curve
thins out or kinks halfway. varLib builds all of it without a word.
`--interpolatable` (or `lint(..., interpolatable=True)`) runs fontTools'
`varLib.interpolatable` over the masters already open and reports these as
4.14–4.17. It roughly doubles the run time, so it is off by default. Glyphs of
more than six contours need an assignment solver; without the extra they are
counted and reported once (4.18) instead of checked.

## Use it from Python

```python
from designspace_lint import lint_path

for problem in lint_path("Family.designspace"):
    print(problem.category, problem.code, problem.description)
```

When the fonts are already open — inside an editor, or a build script that has
loaded them anyway — hand them over instead of paying to open them twice. Any
object with `path`, `doc` and `sources` will do, where each source has `font`,
`path`, `name`, `location`, `layer_name` and the layer accessors described by
`designspace_lint.protocols.SourceLike`:

```python
from designspace_lint import lint

problems = lint(my_designspace)     # nothing is re-opened
```

### Building on the results

A tool that shows the findings needs more than the numbers, and all of it is
public, so a new release does not need code changes on the consuming side:

- **`CODES`** (`designspace_lint.codes`) describes every `(category, code)`:
  a title, a stable `group` slug and its title, the `default_severity` and
  every severity it can take, the phase, whether it needs `interpolatable`,
  whether it is `retired`, and its `locators`. Build filter groups from it.
  A test keeps it in step with the checks.
- **`severity`** is set on every result that comes through `lint()`.
  `effective_severity(result)` gives the same answer for a result from a
  checker called directly.
- **Locators**: the `raw_data` keys `CODES[...].locators` lists are present on
  every finding with that code (`instanceName`, `instanceIndex`,
  `instanceIndices`, `sourceName`, `layerName`, `axisName`, `ruleName`,
  `glyphName`, `mappingIndex`). Use them to find what a finding is about instead of
  parsing `location`.
- **Scoped runs**: `lint(ds, phases=["glyphs"], glyphs=["a", "b"])`
  rechecks a few glyphs; "file" and "geometry" always run.
- **Helpers**: `label_for_source(source)` names a master the way findings do.
  `raw_glyph_order(font)` and `dedupe_glyph_order(order)` read a glyph order
  that fontParts would refuse. `undeclared_axis_dimensions(path)` (or
  `..._from_string(text)`) lists the location dimensions fontTools will drop
  on read, which is worth checking before an editor saves over the file.

The `(category, code)` numbers never change meaning. A public name is
deprecated for one minor release before it goes, and each release's
changelog has a "For consumers" section.

## What it checks

| Category | What it looks at |
|---|---|
| 0 File | the document can be read at all, and every check could finish |
| 1 Geometry | axis minimum/default/maximum, mappings, duplicate names and tags, discrete axis values, **avar2 mappings**: from the default, duplicate inputs, unknown axes, clamped values, outputs past the masters, chains; the declared `<variable-fonts>` |
| 2 Sources | locations (as written in the file, before fontTools drops unknown axes), missing UFOs, duplicate locations as varLib compares them, the default, sources off a discrete axis' values |
| 3 Instances | instance locations and names, unknown location labels, one name at two locations |
| 4 Glyphs | master compatibility: contours, points, curve types, components, anchors, unicodes, contour direction, empty glyphs, **how far along each axis a glyph actually reaches**, and with `--interpolatable` start points, contour order and shapes that thin out or kink |
| 5 Kerning | kerning groups, masters with no kerning, a glyph in two groups of one side |
| 6 Font Info | units per em, required fields, values that differ |
| 7 Rules | rule conditions, rules that never apply, rule glyphs missing from the default master, **overlapping rules** |
| 8 Features | whether the masters' `features.fea` keep the build on the variable path |
| 9 Glyph Order | extra glyphs, and orders that break the per-master merge |
| 10 Labels | DS5 axis and location labels: **the instance names the build derives from them**, values no label covers, labels STAT drops, ranges and style links |

The `(category, code)` pairs are a **public contract**. A retired check keeps
its number, and new checks only ever get new ones.

### The rules come from what the tools actually do

Every rule here was checked against `fontTools` and `ufo2ft` rather than
assumed, and several of them contradict what seems reasonable:

- A glyph may skip a master **in the middle** of an axis — varLib builds a
  per-glyph model from the masters that have it. Skipping the master at the
  **end** of an axis is the dangerous one: measured on a 0 / 0.5 / 1.0 axis
  carrying 100 / 150 / 300 with the last master missing, 0.75 gives 125 and
  1.0 gives 100 instead of 225 and 300. The font builds without a word.
- **Differing kerning pair sets are normal** and are not reported: a pair a
  master does not list resolves to its group value or to 0, which is exactly
  what its absence means in a UFO. A master with *no* kerning is reported,
  and what it does depends on ufo2ft: up to 3.8 every pair resolves to 0
  there and the kerning sags toward it; since 3.9 the master is skipped and
  the kerning interpolates across it.
- Groups without pairs do not help — verified by building a variable font and
  reading the values back.
- `ufo2ft` compiles one variable feature file from the default master **only**
  when every other master's `features.fea` matches it or all of them are
  empty. A mix of the two is not compatible either, and falling off that path
  is silent.
- **Overlapping rules are not settled by declaration order.** varLib makes
  one lookup per rule and numbers the lookups in sorted order of their
  substitutions; in the overlap, the first to rewrite a glyph wins. Declared
  `a → a.zzz` then `a → a.aaa`, the variable font shows `a.aaa`, while static
  instances, which apply rules in declaration order, show `a.zzz`.
- A rule with no `<conditionset>` never applies, and fontTools drops it. An
  *empty* `<conditionset/>` is the spec's always-on rule.
- **An avar2 mapping from the default location is discarded.** varLib keeps it
  only as the base of the variation store it then throws away, and measures
  every other mapping from it: with Weight 100/400/900, adding `400 → 650` to
  `900 → 700` moves normalized 1.0 from 0.6 to 0.1 and leaves the default
  where it was.
- **An avar2 mapping value past the axis end is clamped**, and the mappings
  are evaluated at the coordinates the user set, before any of them applies:
  one mapping's output never feeds another's input. Two mappings whose inputs
  normalize to the same point stop the build, two default-input mappings on
  different axes included.
- **Instance names come from the labels.** When the document has labels, the
  build names each instance from the labels at its location, and a
  `stylename` with no localised `<stylename xml:lang="...">` beside it is
  replaced by that in the variable font. Where every label is elidable and there is no `elidedfallbackname`,
  the name is empty.
- Duplicate masters are duplicates after the omitted axes are filled in:
  `{Weight: 900}` and `{Weight: 900, Width: 100}` (the default) are one
  location to varLib, which refuses them.
- **An empty glyph is a missing glyph to the outline, not to the spacing.**
  When the default draws a glyph, varLib reads an empty copy in another master
  as absent and interpolates the shape across it, while the advance width of
  that empty copy still interpolates. So it is not an incompatibility, and at
  the end of an axis it reverts like a missing glyph (4.11).
- Sparse masters need no naming convention. Which masters a glyph may skip
  follows from the axes; which sources carry kerning, features and a glyph
  order of their own follows from whether they are layers.
- A gap at the end of an axis only counts when the glyph **varies** on that
  axis. One that sits at a single coordinate carries no delta along it, so
  nothing fades out — that is a parametric family's normal arrangement, and a
  glyph drawn only in the default master is reported once as static (4.13)
  rather than once per axis end.
- A designspace 5 source may name only the axes it is not default on; that is
  not a missing value.

Each of those last two was learned the hard way, by running this over
[Amstelvar](https://github.com/googlefonts/amstelvar-avar2) — 91–93 axes, up to
150 masters — where the earlier readings produced 1518 and 18609 findings that
all meant "this is how a parametric family is built". See the changelog for
0.1.1.

### What it does not see

It never compiles anything, so whatever exists only in the built font is out
of reach. The September 2026 coverage audit (`docs/audit/`) sorted these out;
the main ones:

- **Features ufo2ft writes for you.** `kern`, `mark` and `mkmk` are generated
  from kerning and anchors at build time. Category 8 compares the masters'
  `features.fea` text and cannot see what the writers would add or where
  they would disagree across masters.
- **What only the compiled tables show**: lookup overflows and table sizes,
  TrueType hinting, name-table ID reuse, and the order the shaper applies
  feature variations in beyond what 7.7 predicts.
- **Renderers.** avar2 is new; an engine that only reads avar1 ignores the
  whole table. Whether a given app or instancer handles a font correctly is
  not a property of the designspace.
- **Muting.** `mutedGlyphNames`, `muteKerning` and `muteInfo` on instances
  are not taken into account.
- **Point correspondence** only with `--interpolatable`. Even then, component
  transforms are compared by structure, not by what they do between masters.
- **Masters that could not be opened.** They are reported (2.1) and left
  out; checks that measure extents, such as 4.11, then measure without them.

For those, build the font (fontmake, or `fonttools varLib`) and run
`varLib.interpolatable` and your shaping tests on the result.

## Relation to designspaceProblems

This started as a reimplementation of
[designspaceProblems](https://github.com/LettError/DesignspaceProblems) by
**Erik van Blokland (LettError)**, MIT-licensed, and it still owes that project
its shape: the idea of numbering problems by category and code, and most of the
category-4 glyph compatibility checks, come from there. The numbering is kept
deliberately compatible — codes 4.0 to 4.10 mean what they mean in
designspaceProblems — so anyone moving across reads the same numbers.

It was rewritten rather than wrapped because of what using it in a font editor
asked for, and those needs turned out to be structural:

- **Results as data, not as a report.** Every problem is a dataclass carrying
  its location, the masters involved and the diagnosis, so a UI can group,
  filter and navigate them. The original returns a mapping of problem to glyph
  names, which is the right shape for a report and the wrong one for a list
  you click through.
- **No re-opening fonts.** An editor already holds them; the checks take
  whatever satisfies the protocol.
- **Layer-based designspaces.** Several masters in one UFO, told apart by
  layer, have to be compared on the layer they actually draw.
- **Progress and cancellation**, because a family with 84 masters takes long
  enough that a person will want to stop it.
- **Consequences in the message.** The checks grew to say what the build will
  do, which meant verifying each rule against varLib and ufo2ft — and finding
  a few where the reasonable-sounding rule is not the real one.

It is not a drop-in replacement: the entry points and the result type differ.
For the glyph checks the vocabulary is the same.

## License

Apache-2.0. See [LICENSE](LICENSE), and [NOTICE](NOTICE) for the
designspaceProblems attribution.
