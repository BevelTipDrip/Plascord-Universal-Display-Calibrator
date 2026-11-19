---
id: nearblack-probe
title: Measurement probe: shows HDR10 or SDR patches, reads the meter through spotread with low-light averaging, checks the reference before and after, writes a CSV per test ID
area: measurement
status: active
default: n/a
origin: ours (averaging rule from HCFR, arthur-liberman/hcfr-code ArgyllMeterWrapper.cpp)
owner: BevelTipDrip
commits: c491027, 6feab98, a63d1d1
prs:
queue: Q-1, Q-6, Q-7, Q-9
files: tools/nearblack_probe.py
symbols: pq10, read_meter, adapt_reads, measure, readings_agree, rows_for, CSV_HEADER, anchor_pass, centre_on_step, mhc2_luts, sent_codes, ANCHOR_CODES, SETTLE_CODES, V2_PROFILE, SdrWindow, HdrGenerator, GammaRamp, data_path, run, HDR_LEVELS, HDR_DENSE_CODES, REF_EVERY, DATA_DIR, parse_ddc_steps, restore_vcps, DDC_VCPS, rgb_search, search_cost, duv, solve3, xyz_of, SEARCH_CODES
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
ArgyllCMS `spotread -O` (with a meter correction), averages 1-5 readings by HCFR's "Adapt" rule (stopping from the
second reading on once they agree within `--agree`, default 1% of Y and 0.003 in xy), and records Y, x,
y against the exact target of the code sent. It reads a reference (100 nits / white) before the sweep, every 25
patches and at the end. `--ddc-steps` (or the older `--ddc-sweep`, black level on all channels) measures
`--ddc-levels` at each of several DDC/CI settings (per-channel gain 16/18/1A, black level 6C/6E/70). It writes
`research/docs/data/nearblack-<label>-<date>.csv`. `--search` instead finds, for each of `--search-codes`, the
per-channel codes (generator `C`) whose light is closest to that input's PQ luminance at `--white` (D65): it
measures how X, Y, Z move per code of each channel, takes Newton steps to the target, and keeps the best reading
by `search_cost` (colour in u'v', luminance in log, too bright x`--raised-weight`). Rows carry `r`, `g`, `b`.
`--anchors` starts each anchor from the codes `--start-profile` (v2) sends and walks: green up, then blue; or red
and blue down together ("magenta down", the darker route); then all three together for brightness; the best reading
by `search_cost` wins; then a polish (one code on each channel alone, up to 3 rounds) and `centre_on_step`
(move a channel off the edge of a panel step when the other side is flat). `--settle-check <baseline CSV>` first reads `SETTLE_CODES` and stops if the panel is more
than `--settle-tol` off the baseline (Q-19).

## Invariants

- The pre-flight reference must be in range (HDR 50-200, SDR 20-1000 cd/m2) or the run stops (`--diagnostic`
  only warns); an end reference more than 5% off marks the CSV `-INVALID`.
- HDR targets are `pq10(n)`: the luminance of the whole 10-bit code actually sent, not the nits requested.
- `finally:` restores the gamma ramp and every DDC/CI value it changed, and closes the generator.
- DDC/CI writes only the codes in `DDC_VCPS`, only within the maximum the monitor reports, and every value is
  restored before the end reference, so the drift check compares the same settings.
- A CSV with DDC steps or search rows holds non-grey readings: `build_mhc2.py` skips rows whose `run` starts with
  `ddc_` or whose `r`, `g`, `b` are not all equal to `code`; keep those column names.
- `--search` and `--anchors` must run with an identity (uncorrected) HDR profile: the codes it finds are the LUT's outputs, so a
  LUT already in the pipeline would be applied twice.
- `data_path` never overwrites a file; the label (test ID) is in the name. The CSV is rewritten after every patch
  (`save`), so a stopped run keeps its readings; a run that fails the drift check is renamed `-INVALID` at the end.
- `--agree 0` restores the full HCFR count for every level.
- `build_mhc2.py` reads the CSV columns by name (`mode`, `code`, `Y_cdm2`): rename them only together.
- The display is held awake from `main()` on (`SetThreadExecutionState`).

## Interactions

- Needs [hdr10-patchgen](../patchgen/hdr10-patchgen.md) for HDR, and `tools/argyll/` (not in git).
- With an MHC2 profile active, HDR results include the profile's LUT: that is how profiles are verified, and why
  baselines need the uncorrected profile set.

## Evidence

- T-NB1 to T-NB9 (2026-11-18) ran with it; T-NB9 reference drift +0.4%.
- `data_path` naming: built, checked by calling it (2026-11-18); not used in a measurement run yet.
- `--ddc-steps`: built 2026-11-18, checked with fake meter / generator / DDC calls (restores to the saved values
  before the end reference; rejects unknown VCP codes); not run on the monitor yet.
- `--search`: built 2026-11-18, checked on a simulated panel (green lagging near black, light changing every 3
  codes below code 60): all 24 default codes within 0.0045 Delta u'v' of D65, luminance 0.90-1.03x near black and
  1.00x from 0.1 nit up, 184 readings. Run 2026-11-18/19 (T-NT1): does not converge near black (coarse steps).
- `--anchors`: built 2026-11-19, checked on a simulated panel (T-NB3's grey staircase per channel, green lagging
  near black): 0.1-30 nits within Delta u'v' 0.003 at 0.92-1.00x in 15-29 patches; 0.02-0.07 nit 0.006-0.025 (the
  simulated steps' limit, brute-force checked at code 47) at 0.64-1.13x. Single-channel walks missed the darker
  red+blue route until the magenta-down walk was added. Not run on the meter yet.
- Stage 1 run 2026-11-19 (T-NT2): 30 nits 1.00x / 0.0013; 1 nit 0.98x / 0.0040; 0.05 nit 0.76x / 0.032 (from
  0.45x / 0.080). Polish and step centring added after it: on the simulated panel, a one-code shift of the steps'
  edges after solving moved input 47 from 0.90x / 0.026 to 0.54x / 0.054 without centring, not at all with it;
  input 64 came out worse with it (0.016 after the shift). Not run on the meter yet.
- `--agree` and saving after each patch: built 2026-11-19, checked with a fake meter (26 standard levels: 100
  readings -> 49; noisy levels keep the full count; an aborted run keeps its rows; drift renames to -INVALID);
  not run on the meter yet.

## History and pitfalls

- 2026-11-18: the display slept mid-run and the run read nothing; added the wake lock and the reference checks.
- 2026-11-18: CSVs moved from `measurements/` to `research/docs/data/` with test-ID names (project setup).
- 2026-11-19: one `spotread` session per run was tried and dropped: piped keystrokes are ignored (it reads the
  console), and its start-up is only ~1.3 s of a reading; the time is the meter's low-light integration (14.6 s per
  reading on black). Fewer readings per patch (`--agree`) is the lever.
- 2026-11-18: DDC values used to be restored only at exit, after the end reference: a gain step would have shown
  as drift and marked the run INVALID. Now restored before it (Q-1).
