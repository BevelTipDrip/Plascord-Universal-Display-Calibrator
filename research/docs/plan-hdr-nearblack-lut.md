# Plan: correct the AW3225QF's raised near-black in Windows HDR with an MHC2 1D LUT, one profile per HDR preset

Status: True Black 400 v2 profile run (T-NB9: within 7% of target from 0.075 to 20 nits); Peak 1000 profile is v1
(Q-2); not verified by a person in games yet (Q-4). Parent: [START-HERE.md](START-HERE.md). Owner: BevelTipDrip.
Cards: [nearblack-probe](../changes/measurement/nearblack-probe.md), [hdr10-patchgen](../changes/patchgen/hdr10-patchgen.md),
[mhc2-lut](../changes/profiles/mhc2-lut.md), [lut-snap](../changes/profiles/lut-snap.md),
[set-hdr-profile](../changes/profiles/set-hdr-profile.md). Work queue: Q-1 to Q-5. Read
[profiles-reference.md](profiles-reference.md) and [measurement-reference.md](measurement-reference.md) first.

## Why

The AW3225QF (QD-OLED, firmware M2B110) shows the first steps above black far too bright: code 0 is true black,
but from about 0.025 nit the panel jumps to roughly 2-3x the PQ target and only converges by 10-20 nits. It is
worse in HDR, where games give little control over the curve. BevelTipDrip (2026-11-18): "the gamma curve is very
off. This is also a known issue on the monitor, the first few steps in the curve are all bumped up." ICC profiles in
SDR do not reach most games, and dwm_lut does not work in fullscreen games. An MHC2 profile is applied by the GPU's
display pipeline to everything Windows sends to the display in HDR mode.

## What is known today

- **The lift** [V] (T-NB3): ratio measured/target 2.2x at code 35 (0.026 nit), 2.8x at code 47 (0.05 nit), 2.3x
  at 0.1 nit, 1.5x at 0.5 nit, 1.07x at 5 nits, 1.01x at 10 nits. Below code 33 the panel is at or under target.
- **The panel moves in discrete steps near black** [V] (T-NB3): codes 33-34 = 0.026 nit, 35-37 = 0.058, 38-39 =
  0.073, 41-42 = 0.105. A correction can only pick among these.
- **Every HDR preset has the lift**; they differ only at the very bottom [V] (T-NB1, T-NB2, T-NB3): Peak 1000 starts
  later (0.33x at 0.03 nit) and is 5-15% brighter from 0.2 to 2 nits.
- **Near black is tinted blue/purple** [V]: xy about 0.27/0.21 at 0.02-0.03 nit and 0.27/0.24 at 0.05 nit,
  against about 0.31/0.32 from 1 nit up (T-NB3, T-NB9). The luminance correction moves more of the range onto
  these lowest steps, so it makes the tint easier to see (Q-1).
- **30-100 nits read 4-8% low** in every run, corrected or not [V] (T-NB3, T-NB9). The profile leaves that range
  alone (Q-17).
- Earlier readings in True Black 400 from BevelTipDrip's earlier meter project, 2026 (HCFR, same meter):
  0.035 nit -> 0.117, 0.1 -> 0.27, 1 -> 1.49, 10 -> 11.0 [V in that project's data]. Same shape as T-NB3.
- The meter reads 0 below about 0.005 nit, and readings under about 0.015 nit are unreliable
  ([measurement-reference.md](measurement-reference.md)).

## Design

1. Measure the uncorrected response in the preset, code by code through the jump (`--dense`, T-NB3).
2. `build_mhc2.py`: monotone fit of measured luminance per 10-bit code; for every input code, the output code
   whose measured light equals the input's exact PQ luminance; below the meter's floor a linear ramp from 0; a
   smoothstep blend back to identity between 20 and 30 nits. Card [mhc2-lut](../changes/profiles/mhc2-lut.md).
3. Snap each corrected output to the panel step closest (in log) to the target, stored as code + 0.25, because
   the pipeline truncates the LUT output to whole codes. Card [lut-snap](../changes/profiles/lut-snap.md).
4. Copy the Windows HDR Calibration profile (its matrix, luminance and other tags) and replace only the LUTs, the
   description and optionally the peak; install and set it as the display's HDR profile (`set_hdr_profile.py`).
5. Verify with the standard 26-level run (T-NB9).

Alternatives: firmware tables (not pursued: encrypted and signed, out of scope); dwm_lut (no fullscreen games);
SDR ICC profiles (not applied to most games); DDC/CI black level (not measured yet, Q-6).

## Stages

| Stage | What | Switch | Test | State |
|---|---|---|---|---|
| NB1 | Baselines in Desktop, Peak 1000, True Black 400 (dense) | n/a | T-NB1, T-NB2, T-NB3 | run |
| NB2 | True Black 400 profile v1 (unsnapped) | `--no-snap` | T-NB7 | superseded by NB3 |
| NB3 | True Black 400 profile v2 (snapped) | default | T-NB8, T-NB9 | run |
| NB4 | Peak 1000 dense sweep and v2 profile | default | T-NB10 (to run) | not started (Q-2) |
| NB5 | Re-apply after standby; confirm in fullscreen games | n/a | | not started (Q-3, Q-4) |

## Risks

- The correction is per unit and per preset: another AW3225QF may differ; a firmware update can change the curve.
- Inputs under ~0.015 nit are ramped blind (meter floor); a visual check is pending (Q-5).
- Windows may drop the profile after standby (Q-3) or lose the monitor from colour management after a restart
  (Q-11); then the panel is uncorrected without any message.
- Not tested: real games; other GPUs (only NVIDIA); the Peak 1000 v1 profile was never measured.

## Decisions

- Patches must be true HDR10 signal values, not Windows' SDR-to-HDR mapping (BevelTipDrip, 2026-11-18: "you'll have
  to make sure the test patches are actually HDR").
- Keep the Windows HDR Calibration profile's matrix and Auto color management active during runs: that is what
  games see (BevelTipDrip, 2026-11-18).
- One profile per HDR preset, True Black 400 and Peak 1000 (BevelTipDrip, 2026-11-18: "I want to be able to use both
  1000 and 400").
- Firmware route not pursued (BevelTipDrip, 2026-11-18).

## Open questions

- Is the 4-8% low reading at 30-100 nits the panel or the meter correction (Q-17)? Needs a second meter or a
  spectro-based correction.

## T-NB1: Desktop preset baseline, 26 levels (2026-11-18, run by Claude for BevelTipDrip, log `data/nearblack-t-nb1-desktop-2026-11-18.csv`)

Uncorrected (Windows HDR Calibration profile, identity LUT). OSD HDR Desktop. 0.05 nit -> 0.160 (3.2x), 0.1 ->
0.261 (2.6x), 1 -> 1.43 (1.44x), 10 -> 10.65 (1.06x), 100 -> 94.3. Starts lifting earlier than the other presets
(0.92x already at 0.02 nit).

## T-NB2: Peak 1000 baseline, 26 levels (2026-11-18, run by Claude for BevelTipDrip, log `data/nearblack-t-nb2-peak1000-2026-11-18.csv`)

Uncorrected, OSD HDR Peak 1000. 0.03 nit -> 0.0096 (0.33x), 0.05 -> 0.079 (1.6x), 0.1 -> 0.253 (2.5x), 1 -> 1.52
(1.53x), 10 -> 10.61, 100 -> 94.3. Only two points inside the jump: the v1 Peak 1000 profile built from it is
coarse (Q-2).

## T-NB3: True Black 400 dense baseline, 105 codes (2026-11-18, run by Claude for BevelTipDrip, log `data/nearblack-t-nb3-tb400-dense-2026-11-18.csv`)

Uncorrected, OSD HDR True Black 400. Every code from 20 to 59, then coarser to code 520. Codes 20-25 read 0;
code 27 0.0047 (0.31x); 33-34 0.026; 35 0.058 (2.2x); 41 0.105 (2.9x); 47 0.138 (2.8x); 64 0.229 (2.3x);
120 0.750 (1.5x); 310 10.51 (1.01x); 400 28.3 (0.96x); 520 92.5 (0.92x). The source for both True Black 400
profiles.

## T-NB4: True Black 400 v1 profile, 26 levels: INVALID, LUT not applied (2026-11-18 17:11, run by Claude, log `data/nearblack-t-nb4-tb400-v1-verify-2026-11-18.csv`)

Same shape as T-NB3 (0.05 nit -> 0.125, 2.5x): the v1 profile was set but not applied, because NVIDIA "Override
to reference mode" was ticked (found 18:18, see T-NB7). Kept as a record; not evidence about any profile.

## T-NB5: diagnostic half-PQ profile (2026-11-18 17:26-18:08, run by Claude, logs `data/nearblack-t-nb5-diag-half-*-2026-11-18.csv`)

A test profile whose LUT halves the PQ signal, so its effect is unmistakable. Five short runs: without and with an
HDR off/on reload, with a composed (not independently flipped) window, and after Windows' colour management was
restored (Q-11). Every run read unchanged (10 nits -> 10.0-10.4, 1 nit -> 1.25-1.32): the LUT never reached the
display. Cause found later: NVIDIA reference mode (T-NB7).

## T-NB6: True Black 400 v1 spot check, still in reference mode (2026-11-18 18:03, run by Claude, logs `data/nearblack-t-nb6-tb400-v1-spot-2026-11-18.csv`, `data/nearblack-t-nb6-tb400-v1-spot-composed-2026-11-18.csv`)

0.05 nit -> 0.144 (2.9x), 0.1 -> 0.235, flip and composed alike: uncorrected, same cause as T-NB4.

## T-NB7: True Black 400 v1 spot check, NVIDIA Accurate mode (2026-11-18 18:18, run by Claude, log `data/nearblack-t-nb7-tb400-v1-spot-accurate-2026-11-18.csv`)

One change since T-NB6: BevelTipDrip unticked NVIDIA "Override to reference mode" ("I see a visible difference
after unchecking this, previously this check box made no difference"). The LUT applied at once: 1 nit -> 0.964,
0.5 -> 0.485, 10 -> 10.12. But 0.05 nit -> 0.027 (0.55x) and 0.1 -> 0.079 (0.79x): undershoot. The v1 LUT asked
for fractional codes (e.g. 40.87) and the pipeline sent the whole code below (40), one panel step too dark. This
led to snapping (v2, [lut-snap](../changes/profiles/lut-snap.md)). This run also shows a LUT applies to an
independently flipped full-screen swapchain (relevant to Q-4).

## T-NB8: True Black 400 v2 spot check (2026-11-18 18:23, run by Claude, log `data/nearblack-t-nb8-tb400-v2-spot-2026-11-18.csv`)

One change since T-NB7: v2 profile (snapped). 0.05 nit -> 0.060 (1.20x, the nearest panel step), 0.075 -> 0.075
(1.02x), 0.1 -> 0.109 (1.08x), 0.2 -> 0.197, 0.5 -> 0.502, 1 -> 0.993.

## T-NB9: True Black 400 v2 profile, 26 levels (2026-11-18 18:27, run by Claude for BevelTipDrip, log `data/nearblack-t-nb9-tb400-v2-verify-2026-11-18.csv`)

Same profile as T-NB8, standard levels. Reference drift +0.4%. Ratio measured/target:

| Asked (nits) | 0.015 | 0.02 | 0.03 | 0.05 | 0.075 | 0.1 | 0.2 | 0.5 | 1 | 2 | 5 | 10 | 20 | 30 | 100 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Before (T-NB3) | 0.31 | 0.82 | 1.97 | 2.78 | 2.49 | 2.27 | 1.97 | 1.50 | 1.28 | 1.16 | 1.06 | 1.01 | 0.98 | 0.96 | 0.92 |
| v2 | 0.98 | 0.85 | 0.93 | 1.20 | 1.02 | 1.07 | 0.98 | 1.00 | 0.99 | 0.98 | 0.99 | 1.00 | 0.99 | 0.96 | 0.92 |

0.02 and 0.05 nit miss because the panel has no step closer (0.017, 0.058). 30-100 nits is identity (Q-17).
Chromaticity unchanged by the LUT: xy 0.273/0.241 at 0.05 nit, 0.281/0.266 at 0.1 (`data/nearblack-t-nb9-tb400-v2-verify-2026-11-18.csv:8`,
`:10`). Verdict: run, the luminance correction holds from 0.075 to 20 nits; not yet verified by a person in use.
