# Change map

One card per change: what it does, the code it changes, its switches and defaults, **what must stay true for it to
work (invariants)**, how it interacts with other changes, the evidence, and what went wrong before. Rejected and
reverted attempts have cards too, so nobody tries them again without knowing why they failed.

The cards let a person or agent find everything about a piece of code in a few lines, without reading the big plan
docs, and keep old bugs from coming back when someone edits nearby.

## Use it before touching code

```
python research/tools/changemap.py file src/sync/retry.py     # every card for a file, with its invariants
python research/tools/changemap.py switch MYAPP_FAST_SYNC      # its card, default and code sites
python research/tools/changemap.py commit 7246f88              # the card a commit belongs to
python research/tools/changemap.py test T-SYNC3                # where a test run is written up
python research/tools/changemap.py find "retry"                # search the cards
python research/tools/changemap.py doc plan-sync.md            # a doc's outline with anchors
```

[INDEX.md](INDEX.md) lists every card on one line; [TESTS.md](TESTS.md) every test ID and its write-up. Both are
generated (`changemap.py index`): do not edit them; on a merge conflict take either side and run `index` again.

## Keep it true

After a change to code: write or update the card (same commit as the code), then

```
python research/tools/changemap.py new <area> <id>   # a new card from research/templates/card.md
python research/tools/changemap.py check             # 0 errors needed; also reports commits and switches no card covers
python research/tools/changemap.py index             # rebuild INDEX.md and TESTS.md
```

`check` recomputes `_facts/` (generated, not committed: `commits.tsv`, `switches.tsv`, `headings.tsv`, `tests.tsv`)
and fails on: a card naming a file, symbol, switch, commit, doc or anchor that does not exist; a card referring to
an unknown card; a broken relative link in the docs; an `INDEX.md` / `TESTS.md` that is out of date.
`check --list` prints the uncovered commits and switches. Settings (areas, code paths, switch patterns, default
columns): `research/tools/changemap.config.json`.

A card is written by one person or agent and, for anything that matters, **checked** against the code and the docs
by a separate one (a second agent with no stake in the first's conclusions works well). The checker fixes what is
wrong and sets `checked:` to the date. Traps the checker finds but nobody has acted on go in
[LANDMINES.md](LANDMINES.md).

## Card format

`research/changes/<area>/<id-in-lower-case>.md`. Front matter is `key: value`, lists comma-separated:

| Key | Value |
|---|---|
| `id` | Short and unique; the name the docs use where there is one (`R2`, `fast-sync`, `retry-409`) |
| `title` | One line: what it does, mechanism first |
| `area` | The folder; areas are listed in `changemap.config.json` |
| `status` | `active`, `rejected` (measured or reviewed, not kept; code may stay behind an off switch, or was never built: say so in the title), `reverted` (code gone), `superseded` (+ `superseded_by: <id>`), `diagnostic`, `chore` (refactors, build fixes, comments, tests) |
| `default` (or one key per target, e.g. `default_windows`, `default_linux`) | `on`, `off`, `n/a`, `mixed` (explain under Interactions) |
| `origin` | `ours`, or where it came from (`upstream v1.4`, `<repo> <commit>`) |
| `owner` | Who to ask about it (names) |
| `commits` | Short hashes, oldest first |
| `prs` | `#12`, or URLs |
| `queue` | The work-queue item(s) it came from (`Q-12`) |
| `files` | Repo-relative paths it changes (the main files, not every touched line) |
| `symbols` | Functions, types or variables it adds or changes (each must occur in one of `files`) |
| `switches` | Env vars, config keys, feature flags (found by `switch_patterns`) |
| `tests` | Test IDs (`T-SYNC3`) |
| `docs` | `file.md#anchor` under `research/docs/` (anchors: `changemap.py doc <file>`) |
| `depends_on`, `conflicts_with`, `supersedes`, `related` | Card IDs; the reason goes under Interactions |
| `checked` | Date a separate agent or person last compared the card with the code and docs. Not "verified": that word is a person's confirmation |

Body, in this order (all required except for `chore` cards):

- `## What it does`: two to five lines, mechanism first.
- `## Invariants`: what must stay true for it to be correct, and what breaks if it does not. Bullets, each one
  checkable in the code. The part to read before changing anything nearby.
- `## Interactions`: other changes it needs, conflicts with, masks or is masked by, with the reason.
- `## Evidence`: test IDs with the numbers, and what people confirmed (named, quoted).
- `## History and pitfalls`: what went wrong, what was tried and dropped, which bug it caused or fixed.

Keep a card under about 60 lines. Its detail lives in the docs it links.

Switches: one per change. A fix to an existing change rides on that change's switch, unless it could change
performance or behaviour in normal use: then it gets its own, so it can be compared on and off.
