# Handoff 2026-11-18: project set up from the docs template

Author: BevelTipDrip (with Claude). Parent: [START-HERE.md](START-HERE.md). Previous handoff on this topic: none.
Branch: `main` (setup is the one change made there directly, before branch protection). Queue items: Q-1 to Q-17
(all open; none started).

## State

- The AW3225QF near-black work (tools, 14 measurement CSVs, 2 example profiles) is now in the docs standard:
  START-HERE, work queue, roadmap, plan doc with test write-ups T-NB1 to T-NB9, three area reference docs, six cards.
- True Black 400 v2 profile: run (T-NB9), within 7% of target from 0.075 to 20 nits; not verified by a person in
  use. Peak 1000 profile: v1, never measured (Q-2).
- The only code change in setup: `tools/nearblack_probe.py` now writes to `research/docs/data/` with test-ID names
  (`data_path`); built, checked by calling it, not used in a run yet.
- Not in git, by decision: ArgyllCMS binaries, the meter correction (`.ccmx`), the Dell updater, build output, the
  superseded True Black 400 v1 and diagnostic profiles (kept locally, in `.gitignore`).

## What landed

| Change | Commit | Card | State |
|---|---|---|---|
| Tools, data and profiles imported | `c491027` | all six | as before setup (see the cards) |
| Docs standard adopted | (this commit) | changemap | built, `changemap.py check` 0 errors |
| Probe writes `research/docs/data/nearblack-<label>-<date>.csv` | `c491027` | nearblack-probe | built, not run |

## Other branches

None (new repo).

## Traps

1. NVIDIA "Override to reference mode" makes Windows ignore HDR profiles: keep it unticked
   ([profiles-reference.md](profiles-reference.md)).
2. The display sleeps after 60 s idle; tools hold it awake, the reference checks catch failures.
3. Windows can drop the monitor from colour management after a restart (Q-11).

## Start here next time

Q-1, the near-black colour shift: write `plan-nearblack-tint.md` (skill `new-doc`) from the chromaticity columns of
`data/nearblack-t-nb3-tb400-dense-2026-11-18.csv` (codes 27-64) and decide how a per-channel MHC2 LUT (the three
`sf32` tables can differ) moves the near-black white point toward D65 without losing the luminance fix.

## Next steps / pending

1. Create the GitHub repo and push `main` (BevelTipDrip's go); then repo settings: merge commits only, branch
   protection on `main` with `docs-check` required.
2. Q-1, then Q-2 and the rest of Next in [plan-work-queue.md](plan-work-queue.md).

## Open questions

- None. (The ccmx comes from DisplayCAL's colorimeter corrections database: BevelTipDrip, 2026-11-18; docs link
  the database, the file stays out of git.)
