---
id: mhc2-lut
title: MHC2 profile builder: inverts the measured near-black response into a per-code 1D LUT, ramps below the meter floor, blends to identity at 20-30 nits, writes it into a copy of the Windows HDR Calibration profile
area: profiles
status: active
default: n/a
origin: ours
owner: BevelTipDrip
commits: c491027, a63d1d1
prs:
queue: Q-2
files: tools/build_mhc2.py
symbols: load_response, Response, build_lut, smoothstep, read_icc, mhc2, write_icc, mluc, DEFAULT_BASE, IDENTITY_MATRIX
switches:
tests: T-NB3, T-NB9
docs: plan-hdr-nearblack-lut.md#design, profiles-reference.md
depends_on: nearblack-probe
conflicts_with:
supersedes:
related: lut-snap, set-hdr-profile
checked:
---
## What it does

`tools/build_mhc2.py --csv <dense run> --name <profile name> [--peak N]` averages the grey HDR rows per code
(skipping DDC-step and per-channel search rows), keeps
readings at or above `--floor` (0.008), fits a monotone curve (pool adjacent violators) and inverts it in log
space: for each of 1024 input codes, the output code whose measured light equals the input's PQ luminance. Below
the first solvable input it ramps linearly from 0; between `--blend-start` and `--blend-end` (20-30 nits) it
blends to identity. It copies the base profile, replaces the `MHC2` LUTs (three `sf32` tables), `desc` and
optionally the peak and `lumi`, and recomputes the profile ID. `--neutral` writes an identity matrix instead of
the base's (the Windows HDR Calibration matrix carries that app's saturation boost); `--identity-lut` (no `--csv`)
writes Windows' own 2-entry identity LUT. Both together: a profile that changes nothing, for measuring.

## Invariants

- The LUT is monotone non-decreasing and starts at 0.
- Identity from `--blend-end` up.
- The base profile's min luminance is kept; its matrix too, unless `--neutral` (identity).
- Without `--neutral` and `--identity-lut` the output is byte-identical to before these options (checked
  2026-11-18 by rebuilding v2 from T-NB3).
- Tags are 4-byte aligned; shared tag data stays shared; the MD5 profile ID is computed with flags, intent and ID
  zeroed.

## Interactions

- Output is snapped by [lut-snap](lut-snap.md) unless `--no-snap`.
- `DEFAULT_BASE` is a file on BevelTipDrip's machine; elsewhere pass `--base`.

## Evidence

- True Black 400 v2 built from T-NB3: T-NB9 within 7% of target from 0.075 to 20 nits.

## History and pitfalls

- First draft left inputs below the floor as identity, which jumped at the floor; replaced by the ramp.
- `Response.inverse` hit `log(0)` for a zero target; it returns None for Y <= 0.
