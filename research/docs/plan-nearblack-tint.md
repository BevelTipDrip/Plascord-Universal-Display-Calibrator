# Plan: bring the AW3225QF's grey scale to D65 at every level, near black included

Status: target decided (D65); generator `C` command and probe `--search` built 2026-11-18 (checked in simulation),
not run. Parent: [START-HERE.md](START-HERE.md). Owner: BevelTipDrip. Branch: `feature/nearblack-tint`
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
  read 100 of 100; black level 6C / 6E / 70 read 50 of 255. Only the OSD preset "Custom Color HDR" offers colour
  controls; the other HDR presets lock them, so the gains most likely do nothing there [I] (BevelTipDrip,
  2026-11-18). Custom Color HDR peaks around 450 nits.
- **Per-channel black level (6C / 6E / 70) may act as a two-point white balance with the gains**: gain for the top
  of the scale, black level for the bottom. Untested [I].
- **Absolute xy depends on the meter correction**: with the ccmx, 30 nits reads 0.310/0.321; without it (T-MED2),
  0.309/0.323. Both are short of D65 in y, so the lean is real; how exactly D65 is hit depends on the ccmx, which was
  made on another unit [I].
- The MHC2 tag has three separate LUTs (R, G, B), all identical so far; the pipeline truncates each to whole
  10-bit codes (T-NB7). One 10-bit code is about 1-3% of luminance in the 1-100 nit range.
- Grey readings cannot say how each channel behaves alone: building a per-channel correction needs new data [I].

## Design (2026-11-18)

Everything goes into the HDR profile's three LUTs, solved by measurement level by level (BevelTipDrip chose this
over the monitor's controls, Decisions):

1. **Patches with separate channel codes**: generator command `C <r> <g> <b> <area>` (built).
2. **Search per input level** (`nearblack_probe.py --search`, built): for each of 24 input codes from 31 (0.02 nit)
   to 520 (100 nits), with an identity HDR profile active:
   - start from the grey code that gives the input's PQ luminance (`--response` = a dense grey run of the preset);
   - measure each channel raised by a few codes (the step doubles until the change is above the meter's noise),
     which gives how X, Y, Z move per code;
   - take Newton steps to the target XYZ (the input's luminance at D65), rounded to whole codes, at most 12 codes
     per channel per step; re-measure the slopes only after a step that made things worse;
   - keep the reading with the lowest cost: colour in u'v' (tolerance 0.002), luminance in log (tolerance 3%), a
     too-bright error counted `--raised-weight` times (default 2).
   On a simulated panel with coarse near-black steps: all 24 codes within 0.0045 Delta u'v', luminance 0.90-1.03x
   near black and 1.00x from 0.1 nit up, 184 readings (about 30 min on the real meter) [V in simulation only].
3. **Build** (next, after T-NT1): per-channel LUTs from the best codes (interpolated between solved inputs, each a
   whole code + 0.25, non-decreasing per channel; below the lowest solved input a ramp; above the highest, the
   offsets kept and eased off before the top so nothing clips).
4. **Verify** (T-NT2): standard run with luminance and xy, then BevelTipDrip checks greys on screen.

Alternatives considered:
- The monitor's OSD / DDC/CI colour controls: not pursued. The only HDR preset with colour controls (Custom Color
  HDR) has hue and saturation, not a grey-scale white balance (Decisions).
- The MHC2 matrix alone: it applies equally at every level, so it cannot fix the part that grows toward black.
- Measuring each primary alone near black: single-channel light there is mostly under the meter's floor.
- Offsetting channels by eye: not repeatable; the project measures.

## Stages

| Stage | What | Switch | Test | State |
|---|---|---|---|---|
| NT1 | Generator `C` command; probe `--search`; search run in the chosen preset with an identity profile | n/a | T-NT1 | built (checked in simulation), not run |
| NT2 | Per-channel LUTs from the search in `build_mhc2.py`; profile v3; verify run; on-screen check | new option, default off | T-NT2 | not started |
| NT3 | The other preset(s), if wanted | n/a | | not started |

## Risks

- A channel may have no step between "off" and "too much" near black (panel steps are coarse there; T-NB3); then
  the tint can only be reduced at the lowest steps.
- Raising green adds light: luminance and colour are solved together; the lowest inputs may lose a little
  luminance accuracy (accepted, Decisions).
- Hitting D65 exactly depends on the ccmx (another unit's correction).
- The search must run with an identity HDR profile; with the v2 LUT active the codes would be corrected twice.
- Measurement time; meter noise in xy under ~0.03 nit.
- Not tested: content in motion; other presets until NT4.

## Decisions

- Not through the monitor's colour controls: Custom Color HDR (about 450 nits peak) is the only HDR preset with
  them, and they are hue and saturation only (BevelTipDrip, 2026-11-18: "this monitor only has "hue" and
  "saturation" so I don't believe we're going to get the results we need without effecting other areas, because
  it's not linear"). Earlier the same day: "I am fine with 450 nits, this monitor can't do well with 1000 anyway".
  The probe's `--ddc-steps` stays for later tests (Q-6).
- Calibrate **True Black 400**; Peak 1000 dropped for now (BevelTipDrip, 2026-11-18: "true black 400 is the one to
  use" and "we will drop it for now at least, the correct mode for the monitor is a well calibrated HDR400").
- **Two final profiles**: one keeping the Windows HDR Calibration matrix (its saturation boost), one neutral
  (identity matrix) (BevelTipDrip, 2026-11-18: "we'll make two profiles, one with saturation, one neutral").
  Measurements use a neutral profile with identity LUT: `profiles/AW3225QF neutral (identity, for measuring).icc`
  (`build_mhc2.py --identity-lut --neutral`). BevelTipDrip stopped the first identity check because the active
  profile was an HDR Calibration one: "which is not necessarilly neutral (I believe saturation is turned up on all
  of those)". Grey patches are unaffected by that matrix (it maps D65 to D65), the search's off-grey patches are not.
- Target **D65 (0.3127/0.3290) at every level** of the grey scale, not the panel's own grey (BevelTipDrip,
  2026-11-18: "we should probably fix that and target d65").
- A little luminance error near black is acceptable to get the colour right; prefer a step slightly too dark over
  one too bright, unless the brighter one is very close (BevelTipDrip, 2026-11-18: "A little brightness error near
  black is okay, though I would generally prefer slightly crushed black over raised ones. Obviously if the next
  brightness level up is 1% away, that's one thing"). Proposed weighting: a too-bright error counts double;
  strength to be confirmed.

## Open questions

- The strength of the crushed-over-raised weighting (BevelTipDrip).
- None on scope (see Decisions).

## T-NT0: which HDR profile is active? (2026-11-18 22:45-23:05, run by Claude for BevelTipDrip, logs `data/nearblack-t-nt0-profile-check-2026-11-18.csv`, `data/nearblack-t-nt0-profile-check-tb400-2026-11-18.csv`, `data/nearblack-t-nt0-lut-plateau-check-2026-11-18.csv`)

Before the search run (it needs an identity profile), with Windows colour management broken (Q-11): the per-user
association list was reordered so `HDR Calibrated Profile 11-18-2026 11563.icc` (identity LUT) is last, backed up
first (`C:\Users\Ty\icm-assoc-0000-backup-2026-11-18.reg`), and Windows HDR toggled off and on. The OSD preset had
reset to Desktop after the monitor was unplugged; BevelTipDrip set True Black 400 again before the second check.

- Three greys, twice: 0.05 nit -> 0.072, 0.1 -> 0.127-0.129, 1 -> 1.077-1.084 (reference 94-95). Neither
  uncorrected True Black 400 (0.138 / 0.229 / 1.28, T-NB3) nor v2 (0.060 / 0.108 / 0.98, T-NB9).
- Plateau test: v2 sends inputs 36 and 42 to code 34, 43 and 50 to code 35; with no LUT they are four different
  panel steps. Measured: 36, 42, 43 all 0.0317 nit, 50 0.069. **A LUT is active**, but neither v1 nor v2 matches,
  with truncation (v2 would group 43 with 50; v1 all four) or with rounding.
- If the active LUT is v1- or v2-like, the panel reads ~15-20% brighter at the same output codes than in T-NB3.

Verdict: which profile Windows applies can be neither controlled nor read while Q-11 lasts; no search run until it
can (BevelTipDrip, 2026-11-18: "I think it's clear we need to fix profile selection"). Q-18 opened.

**T-NT0, follow-up (2026-11-18 ~23:40, log `data/nearblack-t-nt0-neutral-check-2026-11-18.csv`).** After
BevelTipDrip ran CRU's `restart64.exe` (Windows lists the monitor again, Q-11) and the neutral profile was installed
and selected: inputs 36 / 42 / 43 / 50 / 64 / 153 read 0.0705 / 0.127 / 0.127 / 0.177 / 0.261 / 1.397 nits. 36 and
42 differ, so **no LUT is active** (identity confirmed). Against T-NB3 (same preset, uncorrected, afternoon) the same
codes read **15-21% brighter below 0.2 nit**, +9% at 1 nit, while the 100-nit reference is only +1.3% (93.6-93.9 vs
92.5): the near-black curve itself moved (Q-19). The meter failed once at the start ("Communication protocol
breakdown") and read normally on the retry.

BevelTipDrip (2026-11-19): "It's likely brighter because the HDR profile I had set was done with windows HDR
calibration, and I imagine the "neutral" settings is much brighter." Against it [I]: that profile's matrix maps D65 to
D65 at the same luminance, both profiles have the same min / peak luminance and identity LUT, and a matrix scales
all levels alike, while the change grows toward black; the 11:17 MediEvil run (T-MED1, one profile all day) also
read ~15% above T-NB3 near black. To settle it: after T-NT1, the same six codes with
`HDR Calibrated Profile 11-18-2026 11563.icc` active (Q-19).
