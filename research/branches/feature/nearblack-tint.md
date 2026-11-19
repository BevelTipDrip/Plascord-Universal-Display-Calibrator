---
branch: feature/nearblack-tint
owner: BevelTipDrip
status: active
started: 2026-11-18
base: main @ 1b1783f
goal: Bring the grey scale to D65 at every level (whole-scale magenta lean and the near-black shift), with DDC/CI RGB gain and per-channel MHC2 LUTs, on top of the near-black luminance fix
areas: patchgen, measurement, profiles
files: tools/hdrgen/hdr10_patchgen.cpp, tools/nearblack_probe.py, tools/build_mhc2.py, research/docs/plan-nearblack-tint.md, research/docs/data/*, profiles/*
interfaces: generator stdin protocol (adds an RGB patch command; existing commands unchanged), probe CSV columns (adds per-channel codes), build_mhc2.py command line (per-channel LUTs)
work_queue: Q-1
docs: plan-nearblack-tint.md
cards:
---
## Goal and scope

The AW3225QF's grey scale leans magenta everywhere (y about 0.321 at 30-100 nits, 0.315 at 1 nit, against D65's
0.329) and turns blue/purple near black (xy about 0.27/0.21 at 0.02 nit). This branch tests the monitor's DDC/CI
RGB gain for the whole-scale part, measures how each channel behaves at each level, and builds profiles whose three
LUTs differ, so grey is D65 down to the panel's lowest steps without losing the luminance fix.
In scope: the white point of the whole grey scale (target D65, BevelTipDrip 2026-11-18), True Black 400 first,
Peak 1000 after Q-2. Out of scope: SDR (Q-7), gamut / saturation (the Windows HDR Calibration matrix).

## Planned changes

| What | Where | Changes something others use? |
|---|---|---|
| RGB patch command (per-channel 10-bit codes) | `tools/hdrgen/hdr10_patchgen.cpp` | yes: the generator's stdin protocol gains a command; existing ones unchanged |
| Per-channel measurement mode (grey plus channel offsets) | `tools/nearblack_probe.py` | yes: CSV gains per-channel code columns; existing columns unchanged |
| Probe option to measure greys at given DDC/CI RGB gains (restored after) | `tools/nearblack_probe.py` | yes: new option; existing options unchanged |
| Per-channel LUT solver | `tools/build_mhc2.py` | yes: new options; default output unchanged until decided |
| Plan, test write-ups, data, profiles | `research/docs/`, `profiles/` | no |

## State

Planning: [plan-nearblack-tint.md](../../docs/plan-nearblack-tint.md) written, approach proposed, waiting for
BevelTipDrip's answer before code. Last updated 2026-11-18 by BevelTipDrip (with Claude).

## Conflicts with other branches

Checked 2026-11-18 with `changemap.py branches`.

| Branch | Owner | Overlap (files, areas, interfaces) | Plan | Agreed with |
|---|---|---|---|---|
| none | | | | |

## Merge plan

Merge `main` in before the pull request; nothing else is in flight. The generator command and CSV columns are
additions, so older CSVs and callers keep working. Merged by pull request once a person has checked the
corrected near black on screen.

## Log

- 2026-11-18 BevelTipDrip (with Claude): started from main @ 1b1783f; plan doc written.
