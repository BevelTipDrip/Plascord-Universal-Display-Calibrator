# START HERE: Plascord (Universal Display Calibrator)

Entry point for every session, for every person and every agent. **Keep it current:** when the state below changes,
update this page in the same commit. A new doc gets a row in the Document index the day it is written.

Plascord measures a display with a colorimeter and builds corrections that apply system-wide, fullscreen games
included. It shows exact test patches (true HDR10 or SDR signal values, with no OS tone mapping), reads the meter
through ArgyllCMS, and turns the measured response into a correction: today a Windows HDR (MHC2) profile. It is
for display owners with a meter, and for the LLM agents they run it with. The first target is the Alienware
AW3225QF's raised near-black. Planned: Linux (Vulkan patch generator), per-display modules, an MCP server so an
LLM can run calibrations deterministically, and a UI. Out of scope: modifying display firmware.

## Read in this order

1. This page.
2. **The change map: [research/changes/INDEX.md](../changes/INDEX.md)** (one line per change) and
   [LANDMINES.md](../changes/LANDMINES.md). **Before editing a file run
   `python research/tools/changemap.py file <path>`** and read the invariants of every card it lists. Lookups without
   reading the big docs: `changemap.py switch <name>` / `commit <hash>` / `test <id>` / `find <text>` /
   `doc <file.md>`. After a code change: update the card, then `changemap.py check`
   ([README](../changes/README.md)).
3. **The work queue: `python research/tools/changemap.py queue`** (Now and Next, compact) or
   [plan-work-queue.md](plan-work-queue.md): every planned feature, fix, active issue and research question, in
   order, with who has what. `changemap.py queue Q-<n>`: one item and every branch, card, doc and commit naming it.
4. **The active branches: `python research/tools/changemap.py branches`** (fetches; each other branch's owner,
   goal, state, and its overlaps and conflicts with yours). On a branch: your own reference file
   `research/branches/<branch>.md`, then the reference files of the branches that overlap it. Rules:
   [repo-boundaries.md](repo-boundaries.md#working-on-a-branch-alongside-others).
5. The newest handoff for the area you work on: `research/docs/handoff-YYYY-MM-DD-<topic>.md` (names sort by date).
6. [building-and-tools.md](building-and-tools.md): setup, build, run, test, debug. **Do not re-install the
   toolchain or re-derive the build: it is written down there.**
7. Before touching an area, its reference doc (`<area>-reference.md`, in the Document index below): invariants,
   symptoms, things not to retry.
8. Procedures as skills (`.claude/skills/<name>/SKILL.md`; Claude Code loads them by name, other agents read them as
   plain procedures): `branch-work`, `handoff`, `change-card`, `new-doc`. Update a skill in the same commit as the
   tool or rule it describes.
9. Before writing any doc, card or commit message: [conventions.md](conventions.md).

## People

| Name | GitHub | Role / areas | Notes |
|---|---|---|---|
| BevelTipDrip | [BevelTipDrip](https://github.com/BevelTipDrip) | Owner; all areas | Measures on an AW3225QF with a ColorMunki Display; more collaborators to come |

Decisions are attributed by name and date in the docs: "(Alex, 2026-11-18)". Order of work is decided by
BevelTipDrip.

## Rules (the team's)

- **Ask a named person for an explicit go before:** push to `main`, force-push, tag or release; delete branches or
  files you did not create; anything that costs money or sends anything outside the machine (pushing your own
  branch is the exception); **show test patches or take meter readings** (someone must have the meter on the
  screen and the room dark); **write DDC/CI values to a display; change colour profiles, HDR on/off or GPU driver
  settings; install vendor software** (e.g. Alienware Command Center); **anything that touches a display's
  firmware**. Agreeing to prepare something is not a go to
  start it; a go covers that one action.
- **Never push to `main`, force-push, tag or release without asking.** Branches and merges:
  [repo-boundaries.md](repo-boundaries.md).
- **Work queue:** nothing is worked on without a `Q-<n>` row in [plan-work-queue.md](plan-work-queue.md); a
  problem found along the way gets a row before it is fixed; the row moves with the work, in the same commit.
  Rules: [conventions.md](conventions.md#work-queue).
- **Branches:** nothing is committed straight to `main`. **Large feature changes are built on a `feature/<topic>`
  branch** (large: more than one area, an interface or format others use, a plan doc, more than a session or about
  a day; when unsure, large). **Every in-progress branch has a reference file** `research/branches/<branch>.md`,
  committed on the branch and pushed ([README](../branches/README.md)).
- **On a branch, check the other active branches before starting and before every session**
  (`changemap.py branches`), read the reference files of those that overlap yours, and record each overlap and its
  plan in your file ("Conflicts with other branches"). Agree changes to an interface another branch lists with its
  owner first. Merge `main` into your branch at least daily; no rebasing once pushed.
- Never roll back, overwrite or delete anyone's work without asking.
- **Line endings:** the repository stores LF (`.gitattributes`); git converts on add. Once per clone:
  `git config blame.ignoreRevsFile .git-blame-ignore-revs`. Untracked files (local config, `.env`) keep their
  endings: edit them byte-safely, never Git Bash `sed -i`. Details: [conventions.md](conventions.md#line-endings).
- Check in instead of assuming. Two plausible readings of a request (which branch, build, file, setting, person):
  ask, naming the candidates.
- Before writing code for each item of a list: explain it, propose the change, wait for the answer.
- One change per test, each behind a switch that defaults to the old behaviour where the project has switches; say in
  advance what each outcome would mean.
- **"Verified" means a person confirmed it** (named, quoted), with the log line or number that goes with it. The
  other status words: [conventions.md](conventions.md#status-words).
- When results vary run to run, stop flipping settings after one or two inconclusive tries: build tooling that names
  the failing object and code path, or make the failure deterministic.
- Report outcomes as they are: what was not tested is said, failed checks are quoted.
- Read only, never edit: the references in [repo-boundaries.md](repo-boundaries.md#other-repos-and-references)
  (HCFR, ArgyllCMS, vendor software, other projects).
- **Measurements:** every run whose result anything depends on has a test ID (`T-NB10`), passed to the probe as
  `--label`, and is written up in the plan doc that owns it. Patches are true signal values (HDR10 PQ codes, not
  Windows' SDR-in-HDR mapping), and nothing in the OS may alter them unnoticed: before a run, check the active
  colour profiles and the GPU driver's colour settings ([measurement-reference.md](measurement-reference.md)).
- **Meter limits:** readings under about 0.015 cd/m2 are below what the ColorMunki Display resolves; treat them as
  unverified, never as zero light.
- **Every module brings its own tests:** how a module is tested is designed with it and written in its plan doc
  (meter runs, deterministic checks, or both).
- **Platforms:** Windows today; code that is not inherently platform-specific should not assume Windows, so Linux
  can follow.

## Current state (last updated 2026-11-19 by Claude, for BevelTipDrip)

The state of each area today, one row each, with links. Details live in the linked docs and cards.

| Area | State |
|---|---|
| Repo | Local git repo, `main`; GitHub remote not created yet ([repo-boundaries.md](repo-boundaries.md)) |
| Toolchain | Windows 11, Python 3.8.10, VS 2026 Build Tools, ArgyllCMS 3.5.0, ColorMunki Display ([building-and-tools.md](building-and-tools.md)) |
| Build | `tools/hdrgen/build.ps1` builds the patch generator; the Python tools need no build |
| measurement | `tools/nearblack_probe.py` run: 9 HDR test runs on the AW3225QF (T-NB1 to T-NB9). SDR not measured yet (Q-7). Card [nearblack-probe](../changes/measurement/nearblack-probe.md) |
| ddc | `tools/ddc/` built on `feature/ddc-module` (Q-20): DDC/CI package, 62 unit tests pass on a fake backend; not run on a monitor, nothing written to a display. Open questions for BevelTipDrip in [plan-ddc-module.md](plan-ddc-module.md#open-questions-for-beveltipdrip). Card [ddc-module](../changes/ddc/ddc-module.md) |
| patchgen | HDR10 generator (Windows, D3D11) run in every HDR test. No Linux / Vulkan generator yet (Q-14). Card [hdr10-patchgen](../changes/patchgen/hdr10-patchgen.md) |
| profiles | AW3225QF True Black 400 v2 profile run: within 7% of target from 0.075 to 20 nits (T-NB9). Peak 1000 profile is v1 (no snapping, coarse data; Q-2). Near-black tint not corrected (Q-1). [plan-hdr-nearblack-lut.md](plan-hdr-nearblack-lut.md) |
| Next | The work queue's Now and Next: `changemap.py queue` ([plan-work-queue.md](plan-work-queue.md)). |

## Document index

| Doc | What |
|---|---|
| [../changes/INDEX.md](../changes/INDEX.md) | **The change map:** every change, its code, switches, defaults, invariants, interactions, evidence ([LANDMINES.md](../changes/LANDMINES.md): traps found; [TESTS.md](../changes/TESTS.md): every test ID) |
| [plan-work-queue.md](plan-work-queue.md) | **The work queue:** all planned work as `Q-<n>` rows, Now / Next / Later, owners, branches, states ([done and dropped](plan-work-queue-done.md)) |
| [../branches/README.md](../branches/README.md) | **Branch reference files:** one per in-progress branch, on that branch; `changemap.py branches` reads them all |
| [plan-roadmap.md](plan-roadmap.md) | Goals, stages, Progress table |
| [plan-ddc-module.md](plan-ddc-module.md) | DDC/CI package (`tools/ddc/`): design, safety rules, tests, Linux route, open questions (Q-20) |
| [plan-hdr-nearblack-lut.md](plan-hdr-nearblack-lut.md) | AW3225QF HDR near-black correction (MHC2 LUT): findings, design, test write-ups T-NB1 to T-NB9 |
| [measurement-reference.md](measurement-reference.md) | Measurement area: meter, probe, the setup that must hold before a run, things not to retry |
| [ddc-reference.md](ddc-reference.md) | DDC/CI area: the package's files, write-safety invariants, before any write, symptoms |
| [patchgen-reference.md](patchgen-reference.md) | Patch generator area: HDR10 swapchain, what makes a patch a true signal value |
| [profiles-reference.md](profiles-reference.md) | Profiles area: MHC2 format, how Windows applies it, GPU truncation, things not to retry |
| [handoff-2026-11-18-setup.md](handoff-2026-11-18-setup.md) | Handoff: project set up from the docs template |
| [handoff-2026-11-19-ddc-module.md](handoff-2026-11-19-ddc-module.md) | Handoff: DDC/CI package groundwork (Q-20), open questions for BevelTipDrip |
| [conventions.md](conventions.md) | The documentation standard: doc types, names, status words, evidence, test IDs, commits |
| [building-and-tools.md](building-and-tools.md) | Toolchain, build, run, test, debug, paths, traps |
| [repo-boundaries.md](repo-boundaries.md) | Remotes, branches, merge method, what may be committed, read-only references |
| [pr-checklist.md](pr-checklist.md) | The bar for every pull request |
| `data/` | Measured logs and captures, linked from the docs ([README](data/README.md)) |

## Elsewhere

- HCFR (meter software; its low-light averaging is copied in the probe): https://github.com/arthur-liberman/hcfr-code
- ArgyllCMS (spotread, AGPL-3.0): https://www.argyllcms.com/
- ledoge's dwm_lut and novideo_srgb (MHC2 / GPU LUT prior art): https://github.com/ledoge
- Microsoft: "Display color calibration pipeline" and the MHC2 profile tag (Windows hardware docs)
