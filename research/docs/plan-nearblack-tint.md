# Plan: bring the AW3225QF's grey scale to D65 at every level, near black included

Status: planned 2026-11-18, nothing built; target decided (D65), mechanism proposed, waiting for BevelTipDrip's
answer before code. Parent: [START-HERE.md](START-HERE.md). Owner: BevelTipDrip. Branch: `feature/nearblack-tint`
([reference file](../branches/feature/nearblack-tint.md)). Work queue: Q-1. Read
[profiles-reference.md](profiles-reference.md), [measurement-reference.md](measurement-reference.md) and
[plan-hdr-nearblack-lut.md](plan-hdr-nearblack-lut.md) first. (The file name predates the wider scope.)

## Why

With the luminance fix (True Black 400 v2), near black has the right brightness but a blue/purple cast, and the
rest of the grey scale leans magenta too. BevelTipDrip (2026-11-18): "The next thing I want to tackle is fixing the
near black color shift", and later: "it looks like y is about 0.312-0.317 against D65's 0.329. That's a slight
magenta lean across the whole grey scale, so we should probably fix that and target d65. I can see that even on
brighter greys, not just near black, there is a slight redish tint."

## What is known today

**Grey chromaticity by measured luminance** [V] (T-NB2, T-NB3, T-NB9; True Black 400 unless noted; meter with the
AW3225QF ccmx):

| Measured (nits) | x | y | Note |
|---|---|---|---|
| 30-100 | 0.309-0.310 | 0.320-0.322 | Peak 1000 the same |
| 5-20 | 0.309-0.311 | 0.318-0.321 | |
| 1-3 | 0.308-0.310 | 0.315-0.317 | Peak 1000 0.310-0.316 |
| 0.3-0.5 | 0.308 | 0.311 | |
| 0.13-0.2 | 0.302 | 0.295 | |
| 0.065-0.09 | 0.272 | 0.250 | |
| 0.045-0.065 | 0.273 | 0.240 | |
| 0.01-0.03 | 0.26-0.28 | 0.21 | near the meter's floor |
| D65 target | 0.3127 | 0.3290 | |

(Binned over 146 readings from 0.01 to 3 nits across T-NB1 to T-NB9, plus the brighter rows of T-NB2, T-NB3, T-NB9.)

- **Two parts:** a lean of the whole scale (y 0.008 short of D65 at 30-100 nits, x 0.003 short), and a part that
  grows as the light falls (y 0.014 short at 1 nit, 0.09-0.12 short at the lowest steps). Green is what is missing
  [V for the shift; I for the subpixel].
- **The tint follows the panel's light output, not the input code** [V]: the same output level reads the same xy
  whether the profile or the panel put it there.
- **Not the Windows HDR Calibration matrix** [V by arithmetic, 2026-11-18]: the profile's matrix maps D65 XYZ to
  0.3127/0.3290 exactly; it adjusts saturation, not white.
- **The monitor exposes RGB gain over DDC/CI** [V, read 2026-11-18]: VCP 16 / 18 / 1A (red / green / blue gain) all
  read 100 of 100; black level 6C / 6E / 70 read 50 of 255. Whether the gains act in the HDR presets is not known.
- **Absolute xy depends on the meter correction**: with the ccmx, 30 nits reads 0.310/0.321; without it (T-MED2),
  0.309/0.323. Both are short of D65 in y, so the lean is real; how exactly D65 is hit depends on the ccmx, which was
  made on another unit [I].
- The MHC2 tag has three separate LUTs (R, G, B), all identical so far; the pipeline truncates each to whole
  10-bit codes (T-NB7). One 10-bit code is about 1-3% of luminance in the 1-100 nit range.
- Grey readings cannot say how each channel behaves alone: building a per-channel correction needs new data [I].

## Design (proposed 2026-11-18; BevelTipDrip to confirm)

Two mechanisms, for the two parts:

1. **Whole-scale lean: the monitor's own RGB gain (DDC/CI), if it works in HDR.** Lowering red and blue a few
   steps would raise y at every level, with no 10-bit rounding and for SDR too. Test it first (T-NT1): read white
   and a 10-nit grey at gains 100/100/100, then with red and blue lowered, then restore. If HDR ignores the gains,
   the lean goes into the profile instead: either the MHC2 matrix (a per-channel scale, continuous) or the
   per-channel LUTs below.
2. **Level-dependent part: per-channel LUTs.**
   - The generator gets a command `C <r> <g> <b> <area>` (three 10-bit PQ codes); the existing commands stay.
   - Offset run (T-NT2): at about 15 grey levels from the lowest lit step to ~200 nits, read the grey, then green
     +1/+2 codes, red and blue -1. That gives how Y, x and y move per code of each channel at each level.
     About 150 patches, ~2 h at the current speed (Q-9 would shorten it).
   - Solver in `build_mhc2.py`: for each input code, per-channel output codes (each a whole code + 0.25) that
     bring xy closest to D65 at the PQ target luminance; each channel's LUT non-decreasing.
   - Errors weighed with the crushed-over-raised preference (Decisions): a too-bright error counts double.
3. **Verify** (T-NT3): standard run with luminance and xy, then BevelTipDrip checks greys on screen.

Alternatives considered:
- The MHC2 matrix alone: it applies equally at every level, so it cannot fix the part that grows toward black.
- Measuring each primary alone near black: single-channel light there is mostly under the meter's floor.
- Offsetting channels by eye: not repeatable; the project measures.

## Stages

| Stage | What | Switch | Test | State |
|---|---|---|---|---|
| NT1 | Probe: measure a few greys at given DDC/CI RGB gains, restoring them after; run it | n/a | T-NT1 | not started |
| NT2 | Generator `C` command + probe offset mode; offset run in True Black 400 with v2 active | n/a | T-NT2 | not started |
| NT3 | Per-channel solver (+ global gain or matrix, per NT1); True Black 400 v3 profile; verify | new option, default off | T-NT3 | not started |
| NT4 | Peak 1000, after Q-2 | n/a | | not started |

## Risks

- A channel may have no step between "off" and "too much" near black (panel steps are coarse there; T-NB3); then
  the tint can only be reduced at the lowest steps.
- Raising green adds light: luminance and colour are solved together; the lowest inputs may lose a little
  luminance accuracy (accepted, Decisions).
- Hitting D65 exactly depends on the ccmx (another unit's correction).
- DDC/CI gain changes the monitor for everything; restoring must be reliable (the probe restores in `finally:`).
- Measurement time; meter noise in xy under ~0.03 nit.
- Not tested: content in motion; other presets until NT4.

## Decisions

- Target **D65 (0.3127/0.3290) at every level** of the grey scale, not the panel's own grey (BevelTipDrip,
  2026-11-18: "we should probably fix that and target d65").
- A little luminance error near black is acceptable to get the colour right; prefer a step slightly too dark over
  one too bright, unless the brighter one is very close (BevelTipDrip, 2026-11-18: "A little brightness error near
  black is okay, though I would generally prefer slightly crushed black over raised ones. Obviously if the next
  brightness level up is 1% away, that's one thing"). Proposed weighting: a too-bright error counts double;
  strength to be confirmed.

## Open questions

- The strength of the crushed-over-raised weighting (BevelTipDrip).
- Whether DDC/CI RGB gain works in the HDR presets (T-NT1).
