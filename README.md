# Plascord: Universal Display Calibrator

Plascord measures a display with a colorimeter and builds corrections that apply system-wide, including in
fullscreen games. It shows exact test patches (true HDR10 or SDR signal values, with no operating-system tone
mapping in the way), reads the meter, and turns the measured response into a correction. On Windows that is
currently an HDR (MHC2) colour profile.

Its first target is the Alienware AW3225QF QD-OLED. That monitor shows the steps just above black far too bright:
up to 2.8x the HDR target around 0.05 nit, in every HDR preset and in SDR. With the current True Black 400 profile,
the measured response is within 7% of target from 0.075 to 20 nits
([plan-hdr-nearblack-lut.md](research/docs/plan-hdr-nearblack-lut.md)).

Planned: Linux support (a Vulkan patch generator and the Linux colour pipeline), separate modules for specific
displays and TVs, an MCP server so an LLM can run calibrations deterministically, and later a user interface. Out
of scope: modifying display firmware.

**Status:** early, Windows only. The tools are command-line Python plus one C++ program. The example profiles in
[profiles/](profiles/) were measured on one unit. Panels vary, so measure your own before trusting them.

## Using it

Setup, the meter software to install, and every command: [research/docs/building-and-tools.md](research/docs/building-and-tools.md).

## Working on this project

Every person and every agent starts at **[AGENTS.md](AGENTS.md) -> [research/docs/START-HERE.md](research/docs/START-HERE.md)**
and follows its reading order. `CLAUDE.md` (Claude Code) and `GEMINI.md` (Gemini CLI) import `AGENTS.md`; Codex,
Cursor and Copilot read `AGENTS.md` directly; any other tool can be pointed at it.

What keeps it working:

| Piece | What it does |
|---|---|
| One entry point | START-HERE: reading order (small docs before big ones), the team's rules, the current state of every area, an index of every doc. |
| The change map | One short card per change (`research/changes/`): what it does, **invariants** (what must stay true), interactions, evidence, pitfalls. Rejected attempts get cards too. Before editing a file, `changemap.py file <path>` shows every card for it, so nobody breaks a fix they never read about. |
| Status words | found / confirmed / built / run / **verified (a named person confirmed it, quoted)**. "Fixed" alone is not allowed. |
| The work queue | `plan-work-queue.md`: every planned feature, fix, active issue and research question as a `Q-<n>` row (Now / Next / Later, owner, branch, state). Rows stay one line; the ID ties branches, cards, docs and commits together; `check` fails when a branch's item isn't marked in progress. |
| Branch reference files | Large features are built on `feature/` branches, and every in-progress branch carries `research/branches/<branch>.md` (owner, plan, files and interfaces it changes, conflicts, merge plan). `changemap.py branches` fetches and reads every active branch's file, so overlaps and conflicts are planned for before merge time. |
| Reference docs | Per area: invariants, symptom -> where to look, **things not to retry**. Updated the day something is found. |
| Handoffs | Every session ends with a dated handoff that says "start here next time". |
| A check in CI | `changemap.py check` fails on cards naming files, symbols, switches or commits that don't exist, broken links, or a stale index. |

The full standard: [research/docs/conventions.md](research/docs/conventions.md).

## Layout

```
AGENTS.md                     every agent's entry point (CLAUDE.md and GEMINI.md import it)
tools/                        the calibrator: measurement probe, HDR10 patch generator, profile builder and installer
profiles/                     example profiles (one unit; measure your own)
.claude/skills/               procedures: branch-work, handoff, change-card, new-doc
.github/                      PR template, issue forms, docs-check workflow
research/
  docs/                       START-HERE, conventions, work queue, roadmap, plans, studies, references, handoffs
    data/                     measurement CSVs the docs quote
  changes/                    the change map: <area>/<id>.md cards, INDEX.md, TESTS.md (generated), LANDMINES.md
  branches/                   one reference file per in-progress branch (each lives on its own branch)
  templates/                  blank card, branch, plan, study, impl, reference, handoff
  tools/changemap.py          lookups and the check (Python 3.8+, standard library only)
```

## The docs tool

```
python research/tools/changemap.py file <path>      # cards for a file, with their invariants: run before editing
python research/tools/changemap.py find <text>      # search the cards
python research/tools/changemap.py new <area> <id>  # a new card
python research/tools/changemap.py queue            # the work queue's Now and Next; queue Q-12 for one item
python research/tools/changemap.py branches         # other active branches vs yours: overlaps, conflicts
python research/tools/changemap.py new-branch <b>   # a branch's reference file
python research/tools/changemap.py check            # validate everything (CI runs this)
python research/tools/changemap.py index            # rebuild INDEX.md / TESTS.md
```

Settings: [research/tools/changemap.config.json](research/tools/changemap.config.json). Format:
[research/changes/README.md](research/changes/README.md).

## Line endings

`.gitattributes` makes the repository LF for everyone (git converts on add), so a CRLF editor on one machine
can't turn a one-line change into a whole-file diff. Once per clone, run
`git config blame.ignoreRevsFile .git-blame-ignore-revs`. Rules and the normalizing procedure:
[conventions.md](research/docs/conventions.md#line-endings).

## Repository settings

- **Pull requests**: allow merge commits only (turn off squash and rebase merging). Cards point at commit hashes,
  and the other two methods rewrite them.
- **Branch protection on `main`**: pull requests required, the `docs-check` workflow required.

Agent memory (Claude's or any other tool's) is per person and per machine. Everything the team shares lives in the
repo.

## Licence

MIT ([LICENSE](LICENSE)). ArgyllCMS, which Plascord runs for meter readings, is a separate program under the
AGPL-3.0 and is not included: each person installs it (building-and-tools.md).
