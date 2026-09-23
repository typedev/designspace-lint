# designspace-lint

**What a designspace will do when it is built — before you build it.**

A designspace can be perfectly valid and still produce a variable font nobody
intended. A glyph missing from the master at the end of an axis quietly reverts
to the default's shape past that point. A master with no kerning drags the
family's kerning toward zero around its location. A `features.fea` that differs
from the default's pushes the whole build onto another path, where `varLib`
fails somewhere that has nothing to do with the cause. None of this is an
error at build time; the font just comes out wrong.

This library reports those cases, and each report names the **consequence**,
not only the discrepancy.

```console
$ designspace-lint Family.designspace
error 4.11 /eacute Weight 400 of 900: missing at Weight maximum (900); reverts to the default shape past 400
error 5.0 Bold.ufo (Bold): no kerning: the family's kerning sags to 0 here
warn  4.2 /acute missing in 12 sources: anchor '_topacute' missing in 12 sources
3 problem(s), 2 structural
```

Exit code is `0` when clean, `1` when there are problems, `2` when the
designspace cannot be read — so a build script can gate on it directly.

## Install

```console
pip install designspace-lint            # the checks and the CLI
pip install "designspace-lint[features]"  # + the features.fea comparison (ufo2ft)
```

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

## What it checks

| Category | What it looks at |
|---|---|
| 0 File | the document can be read at all |
| 1 Geometry | axis minimum/default/maximum, mappings, duplicate names and tags |
| 2 Sources | locations, missing UFOs, duplicate locations, the default |
| 3 Instances | instance locations and names |
| 4 Glyphs | master compatibility: contours, points, curve types, components, anchors, unicodes, contour direction, empty glyphs, and **how far along each axis a glyph actually reaches** |
| 5 Kerning | kerning groups, masters with no kerning, a glyph in two groups of one side |
| 6 Font Info | units per em, required fields, values that differ |
| 7 Rules | designspace rules |
| 8 Features | whether the masters' `features.fea` keep the build on the variable path |
| 9 Glyph Order | extra glyphs, and orders that break the per-master merge |

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
  because then every pair resolves to 0 there.
- Groups without pairs do not help — verified by building a variable font and
  reading the values back.
- `ufo2ft` compiles one variable feature file from the default master **only**
  when every other master's `features.fea` matches it or all of them are
  empty. A mix of the two is not compatible either, and falling off that path
  is silent.
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
