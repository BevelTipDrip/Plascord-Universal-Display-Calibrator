---
id: lut-snap
title: Snap corrected LUT outputs to the panel step closest to the target, stored as code + 0.25, because the display pipeline truncates LUT output to whole 10-bit codes
area: profiles
status: active
default: on
origin: ours
owner: BevelTipDrip
commits: c491027
prs:
queue: Q-2
files: tools/build_mhc2.py
symbols: snap_lut, no_snap
switches:
tests: T-NB7, T-NB8, T-NB9
docs: profiles-reference.md, plan-hdr-nearblack-lut.md#stages
depends_on: mhc2-lut
conflicts_with:
supersedes:
related:
checked:
---
## What it does

`snap_lut` runs after `build_lut` (off with `--no-snap`). For each input below `--blend-start` whose output is above
the lowest measured code, it compares the two whole codes around the fractional output and keeps the one whose
measured light is closer in log to the target, written as code + 0.25 so truncation and rounding both land on it.
Then it enforces a non-decreasing LUT again.

## Invariants

- Only the corrected range is snapped (target under `--blend-start`, output above the first measured code).
- The stored value is a whole code + 0.25 (never + 0.5 or more, which a rounding pipeline would push up a code).
- The LUT stays non-decreasing after snapping.

## Interactions

- Its choice depends on [mhc2-lut](mhc2-lut.md)'s fitted response; a coarse sweep (T-NB2) gives poor steps.

## Evidence

- T-NB7 (v1, unsnapped): 0.05 nit -> 0.027 (0.55x), 0.1 -> 0.079 (0.79x).
- T-NB8, T-NB9 (v2, snapped): 0.05 -> 0.060 (1.20x, nearest step), 0.075 -> 0.076, 0.1 -> 0.108.

## History and pitfalls

- Found 2026-11-18: the pipeline sent 40 for a LUT value of 40.87 (T-NB7); v1 profiles undershoot by one step.
