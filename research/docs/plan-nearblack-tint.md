# Plan: correct the AW3225QF's blue/purple tint near black with per-channel MHC2 LUTs

Status: planned 2026-11-18, nothing built; approach proposed, waiting for BevelTipDrip's answer. Parent:
[START-HERE.md](START-HERE.md). Owner: BevelTipDrip. Branch: `feature/nearblack-tint`
([reference file](../branches/feature/nearblack-tint.md)). Work queue: Q-1. Read
[profiles-reference.md](profiles-reference.md), [measurement-reference.md](measurement-reference.md) and
[plan-hdr-nearblack-lut.md](plan-hdr-nearblack-lut.md) first.

## Why

With the luminance fix (True Black 400 v2), near black has the right brightness but a blue/purple cast: grey
patches below about 0.1 nit come out bluish-magenta. Every run shows it, corrected or not (T-NB1 to T-NB9).
BevelTipDrip (2026-11-18): "The next thing I want to tackle is fixing the near black color shift."

## What is known today

**The tint follows the panel's light output, not the input code** [V]: chromaticity binned by measured luminance,
across all HDR rows of T-NB1 to T-NB9 (`data/nearblack-t-nb*.csv`, 146 readings from 0.01 to 3 nits):

| Measured (nits) | Readings | x (range) | y (range) |
|---|---|---|---|
| 0.010-0.020 | 7 | 0.263 (0.257-0.268) | 0.207 (0.201-0.211) |
| 0.020-0.030 | 6 | 0.278 (0.276-0.280) | 0.210 (0.209-0.211) |
| 0.045-0.065 | 6 | 0.273 (0.271-0.275) | 0.240 (0.236-0.243) |
| 0.065-0.090 | 8 | 0.272 (0.269-0.276) | 0.250 (0.237-0.258) |
| 0.090-0.130 | 9 | 0.287 (0.280-0.298) | 0.272 (0.264-0.291) |
| 0.130-0.200 | 21 | 0.302 (0.296-0.305) | 0.295 (0.288-0.301) |
| 0.200-0.300 | 16 | 0.305 (0.299-0.307) | 0.303 (0.297-0.307) |
| 0.300-0.500 | 18 | 0.308 (0.301-0.313) | 0.311 (0.306-0.315) |
| 0.500-3.000 | 55 | 0.309-0.312 | 0.314-0.316 |

- Below about 0.13 nit, y falls from 0.314 to 0.21 while x falls less: green drops out first, which reads as
  blue/magenta [V for the shift; I for which subpixel]. The ranges are narrow and repeat across runs and presets,
  so it is the panel, not meter noise [I].
- The luminance fix moved more inputs onto these lowest output steps, so it makes the tint more visible
  (plan-hdr-nearblack-lut.md, "What is known today").
- The MHC2 tag has three separate LUTs (R, G, B); all three are identical in every profile so far
  ([mhc2-lut](../changes/profiles/mhc2-lut.md)). The pipeline truncates each to whole 10-bit codes (T-NB7).
- Grey readings cannot say how each channel behaves on its own: the existing data cannot build a per-channel
  correction [I].
- Chromaticity readings under ~0.02 nit are near the meter's floor; the 0.010-0.020 row is the least certain [I].

## Design (proposed 2026-11-18; BevelTipDrip to decide)

1. **Patches with separate channel values.** The generator gets a command `C <r> <g> <b> <area>` (three 10-bit
   PQ codes); the existing `N`, `P`, `B`, `Q` stay as they are.
2. **Measure grey plus small per-channel offsets near black** (probe mode, one run per preset): at about ten grey
   codes the v2 LUT actually sends (27 to ~150), read the grey, then green +1/+2 codes, and red and blue +/-1,
   giving how Y, x and y move per code step of each channel. About 100 patches, ~1.5 h at the current speed
   (Q-9 would shorten it).
3. **Solve per input code.** For each corrected input, keep the v2 output as the starting grey and pick small
   per-channel code offsets that bring xy closest to the target grey while keeping Y within the v2 tolerance;
   each channel's LUT stays non-decreasing and is stored as code + 0.25 ([lut-snap](../changes/profiles/lut-snap.md)).
4. **Verify** with the standard 26-level run (luminance and xy), then BevelTipDrip checks near black on screen.

Target grey: the panel's own grey between 0.5 and 10 nits (xy about 0.310/0.315), not D65, so near black matches
the rest of the scale; the overall white point stays the Windows HDR Calibration matrix's job.

Alternatives considered:
- Change the MHC2 matrix: it applies at every level, so it cannot fix a shift that exists only near black.
- Measure each primary alone near black: single-channel light near black is mostly under the meter's floor.
- Offset channels by a guess and iterate on screen: not repeatable, and the project's rule is to measure.

## Stages

| Stage | What | Switch | Test | State |
|---|---|---|---|---|
| NT1 | Generator `C` command + probe offset mode; offset run in True Black 400 with v2 active | n/a | T-NT1 | not started |
| NT2 | Per-channel solver in `build_mhc2.py`; True Black 400 v3 profile | new option, default off | T-NT2 | not started |
| NT3 | Standard run with v3; on-screen check by BevelTipDrip | n/a | T-NT3 | not started |
| NT4 | Peak 1000, after Q-2 | n/a | | not started |

## Risks

- A channel may have no step between "off" and "too much" near black (panel steps are coarse there; T-NB3); then
  the tint can only be reduced, not removed, at the lowest steps.
- Raising green adds light: luminance and tint have to be solved together, and the lowest inputs may trade a
  little luminance accuracy for colour.
- Measurement time; meter noise in xy under ~0.03 nit.
- Not tested: whether per-channel offsets look right in motion or on content (only patches are measured).

## Decisions

- (Pending) Target grey: the panel's own grey, as proposed, or D65.
- (Pending) Approach as above, starting with stage NT1.

## Open questions

- Is a small luminance error near black acceptable to get the colour right, and how much (BevelTipDrip)?
