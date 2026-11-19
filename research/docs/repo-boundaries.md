# Repo boundaries

Parent: [START-HERE.md](START-HERE.md). The bar for a pull request: [pr-checklist.md](pr-checklist.md).

## Remotes

| Remote | URL | Rule |
|---|---|---|
| `origin` | https://github.com/BevelTipDrip/Plascord-Universal-Display-Calibrator (public) | The team's repo. `main` is protected: changes reach it only through pull requests. |

Not a fork: there is no `upstream`.

## Branches

| Branch | Contains | Reference file | Pushed? |
|---|---|---|---|
| `main` | Reviewed work only. Nothing is committed to it directly. | no | Only by merging a pull request. |
| `feature/<topic>` | **A large feature change** (below): code, cards, docs. May have several contributors. | **required** | Freely, to `origin`, from the first commit. |
| `fix/<topic>` | One small change, one pull request. | **required** (short) | Freely, to `origin`. |
| `docs/<topic>` | Docs-only changes: work-queue claims, handoffs, doc fixes. | no | Freely. |

**A change is large**, and must be built on a `feature/<topic>` branch and merged by pull request, when any of
these holds: it touches more than one area; it changes an interface, data format, schema, config key or switch that
other code or people use; it needs a plan doc; it takes more than one session or more than about a day; it is more
than one pull request's worth of review. When unsure, treat it as large.

**Every in-progress branch has a reference file**, `research/branches/<branch name>.md`, committed on the branch
itself as its first commit, and the branch is pushed so others can see it. It says who owns the branch, what it
delivers, which files, areas and interfaces it will change, its state, its conflicts with other branches and its
merge plan. Format, and when to update it: [research/branches/README.md](../branches/README.md). `changemap.py check`
fails on a branch without one.

## Working on a branch alongside others

Plan for conflicts before they happen, not at merge time:

1. **Before starting a branch, and before every session on it:** `python research/tools/changemap.py branches`.
   It fetches `origin` and shows every other active branch's reference file against yours: files you both change,
   files one of you plans to change and the other already changes, shared areas, interfaces they change, and the
   files that would conflict if merged now.
2. **For each overlap**, read the other branch's reference file (its Planned changes, Merge plan, Conflicts). Write a
   row in your file's "Conflicts with other branches": the branch, the overlap, the plan, who you agreed it with, the
   date. Plans: who merges first; splitting out a shared piece into its own small PR that both build on; one
   branch waiting; or the second branch adapting at merge.
3. **Before changing an interface another active branch lists** (or uses), tell its owner and agree it first.
4. **Keep your file's `files` / `areas` / `interfaces` current and pushed**, so other people's checks see your
   plans, not only what you have already changed.
5. **Bring `main` in often** (at least daily while active, and before opening the pull request): merge `main` into
   your branch. No rebasing once a branch is pushed. Whoever merges second resolves the conflicts, unless the merge
   plans say otherwise.
6. **Before merging:** `branches` once more; status `in review`; resolve what it shows. In the pull request's last
   commit, set status `merged` and move the queue row to `plan-work-queue-done.md`; the file stays on
   `main` as the branch's record.

## Merging

- **Merge commits only** (repo settings: allow merge commits; turn off squash and rebase merging). Squash and rebase
  merges rewrite commit hashes, and the cards' `commits:` would point at commits that are not on `main`.
- A pull request carries its code, its cards, its doc updates and its branch reference file together, and passes
  `changemap.py check` (the `docs-check` workflow runs it). Docs and code merge together, so they stay consistent.
- Never force-push a branch someone else has pulled; never force-push `main`.
- Delete a merged branch only with its owner's go (`changemap.py branches` lists the merged ones).

## What may be committed

- Code, docs, cards, measurement CSVs in `research/docs/data/` (under ~1 MB each), example profiles in `profiles/`.
- **Never:** secrets, keys, tokens, `.env` files, personal data, other people's licensed files, build output.
  In this project that includes: ArgyllCMS binaries (AGPL-3.0; each person installs them), meter correction files
  (`.ccmx` / `.ccss`; each person downloads them, e.g. from DisplayCAL's colorimeter corrections database), vendor software and firmware (the Dell updater), and
  anything about bypassing display firmware protections.
- Large data (raw captures, dumps) stays outside git, on the owner's machine; docs name its path.

## Other repos and references

| Repo / source | Where | Rule |
|---|---|---|
| HCFR | https://github.com/arthur-liberman/hcfr-code (GPL-2.0); installed at `C:\Program Files (x86)\HCFR Calibration` | Read only. The probe's low-light averaging ("Adapt") follows HCFR's meter wrapper (`ArgyllMeterWrapper.cpp`); copying code needs GPL-compatible handling: ask first. |
| ArgyllCMS | https://www.argyllcms.com/ (AGPL-3.0) | Read only. Run as a separate program (`spotread`); not linked, not shipped. |
| ledoge (dwm_lut, novideo_srgb) | https://github.com/ledoge | Read only. Prior art for GPU LUTs and MHC2 profiles on Windows. |
| Dell AW3225QF firmware updater | `Monitor Software/` on BevelTipDrip's machine | Read only, never committed, never run. The firmware route is not pursued (plan-roadmap.md, out of scope). |
| BevelTipDrip's earlier meter project | BevelTipDrip's machine | Read only, never edit. Earlier AW3225QF HDR readings: [plan-hdr-nearblack-lut.md](plan-hdr-nearblack-lut.md#what-is-known-today). |

Licence of this project: MIT ([LICENSE](../../LICENSE)).
