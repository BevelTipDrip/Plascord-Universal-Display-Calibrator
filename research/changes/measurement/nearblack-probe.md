---
id: nearblack-probe
title: Measurement probe: shows HDR10 or SDR patches, reads the meter through spotread with low-light averaging, checks the reference before and after, writes a CSV per test ID
area: measurement
status: active
default: n/a
origin: ours (averaging rule from HCFR, arthur-liberman/hcfr-code ArgyllMeterWrapper.cpp)
owner: BevelTipDrip
commits: c491027
prs:
queue: Q-6, Q-7, Q-9
files: tools/nearblack_probe.py
symbols: pq10, read_meter, adapt_reads, measure, SdrWindow, HdrGenerator, GammaRamp, data_path, run, HDR_LEVELS, HDR_DENSE_CODES, REF_EVERY, DATA_DIR
switches:
tests: T-NB1, T-NB3, T-NB9
docs: measurement-reference.md, plan-hdr-nearblack-lut.md#design
depends_on:
conflicts_with:
supersedes:
related: hdr10-patchgen, display-power, mhc2-lut
checked:
---
## What it does

`tools/nearblack_probe.py` puts a centred patch (10% of the screen) on the display: HDR through the native HDR10
generator, SDR through a full-screen tkinter window with the GPU gamma ramp set linear. For each level it runs
ArgyllCMS `spotread -O` (with a meter correction), averages 1-5 readings by HCFR's "Adapt" rule, and records Y, x,
y against the exact target of the code sent. It reads a reference (100 nits / white) before the sweep, every 25
patches and at the end; `--ddc-sweep` repeats key levels at several DDC/CI black levels. It writes
`research/docs/data/nearblack-<label>-<date>.csv`.

## Invariants

- The pre-flight reference must be in range (HDR 50-200, SDR 20-1000 cd/m2) or the run stops (`--diagnostic`
  only warns); an end reference more than 5% off marks the CSV `-INVALID`.
- HDR targets are `pq10(n)`: the luminance of the whole 10-bit code actually sent, not the nits requested.
- `finally:` restores the gamma ramp and every DDC/CI value it changed, and closes the generator.
- `data_path` never overwrites a file; the label (test ID) is in the name.
- `build_mhc2.py` reads the CSV columns by name (`mode`, `code`, `Y_cdm2`): rename them only together.
- The display is held awake from `main()` on (`SetThreadExecutionState`).

## Interactions

- Needs [hdr10-patchgen](../patchgen/hdr10-patchgen.md) for HDR, and `tools/argyll/` (not in git).
- With an MHC2 profile active, HDR results include the profile's LUT: that is how profiles are verified, and why
  baselines need the uncorrected profile set.

## Evidence

- T-NB1 to T-NB9 (2026-11-18) ran with it; T-NB9 reference drift +0.4%.
- `data_path` naming: built, checked by calling it (2026-11-18); not used in a measurement run yet.

## History and pitfalls

- 2026-11-18: the display slept mid-run and the run read nothing; added the wake lock and the reference checks.
- 2026-11-18: CSVs moved from `measurements/` to `research/docs/data/` with test-ID names (project setup).
