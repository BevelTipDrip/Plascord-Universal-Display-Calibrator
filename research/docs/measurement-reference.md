# Measurement reference: meter readings and measurement runs

Read it **before changing the measurement code and before every measurement run.** **Keep it current:** a new rule,
symptom or dead end goes in here the same day, in one line with a pointer to the findings. Parent:
[START-HERE.md](START-HERE.md).

## 1. Directory

| What | Where |
|---|---|
| Probe: patches, meter, sweeps, reference checks, DDC/CI sweep, CSV | `tools/nearblack_probe.py` ([nearblack-probe](../changes/measurement/nearblack-probe.md)) |
| Wake / turn off the display for unattended runs | `tools/display_power.py` ([display-power](../changes/measurement/display-power.md)) |
| Meter software and correction (not in git) | `tools/argyll/` ([building-and-tools.md](building-and-tools.md#toolchain)) |
| Results | `research/docs/data/nearblack-<test id>-<date>.csv`; write-ups in the owning plan doc |

## 2. Invariants: must hold after every change

| # | Rule | What broke when it didn't | How to verify |
|---|---|---|---|
| 1 | A run starts with a reference reading in range and ends with one within 5%; otherwise it is marked INVALID | 2026-11-18: the display slept mid-run and the run read nothing | `run()` in the probe; the file name says `-INVALID` |
| 2 | The display is held awake for the whole run (`SetThreadExecutionState`) | Same | `main()` in the probe and in the generator |
| 3 | HDR patches are exact 10-bit PQ codes from the native generator; targets are the exact luminance of the code sent (`pq10`) | Targets computed from the requested nits would be off by up to half a code | [hdr10-patchgen](../changes/patchgen/hdr10-patchgen.md) |
| 4 | Every setting a run changes (SDR gamma ramp, DDC/CI values) is restored on exit, also on Esc, Ctrl+C or errors | A crashed DDC sweep would leave the monitor's black level changed | `finally:` block in `run()` |
| 5 | A CSV is never overwritten; its name carries the test ID | Results lost or mixed up between runs | `data_path()` |

## 3. Before every test

1. A person has said go for this run (patches on screen, meter on the screen centre, room dark).
2. One change since the last run; say which. Give the run its test ID (`changemap.py test <id>` finds nothing).
3. Colour pipeline as intended: `python tools/set_hdr_profile.py --show` (HDR profile is the one meant for this
   run); NVIDIA "Override to reference mode" unticked; Windows HDR on (HDR runs) or off (SDR runs).
4. Display warmed up; OSD preset named in the label; Dark Stabilizer 0. After the monitor lost power, near black runs
   up to ~20% high for about three hours (T-DRIFT1/2, Q-19): first read the six T-DRIFT codes (36, 42, 43, 50, 64,
   153) and compare with T-NB3 (within ~3%) before any run that a profile will be built from.
5. Same patch size (`--area 0.1`), meter and correction as the baseline.
6. Say in advance what each outcome would mean.

## 4. Symptom -> first place to look

| Symptom | Most likely cause | Look at |
|---|---|---|
| Reference reads ~0 or out of range at the start | Display asleep, meter off the patch, meter not on the screen | Pre-flight in `run()`; `display_power.py wake` |
| A profile changes nothing measurable | NVIDIA reference mode, or Windows lost the monitor (Q-11) | [profiles-reference.md](profiles-reference.md) |
| Readings of 0 below ~0.005 nit, noisy below ~0.015 | The ColorMunki Display's floor | Section 5; Q-5 for a visual check |
| 30-100 nits read 4-8% low | Panel tracking or the meter correction (open) | Q-17 |
| Same preset and codes read 15-20% brighter near black than an earlier session | The panel's near-black curve moved (power cut, resets, warm-up?); compare with the baseline's reference and near-black codes before building on old data | Q-19, T-NT0 |
| Another tool's readings ~4-5% higher than the probe's | Read without the AW3225QF ccmx (the probe always uses it) | T-MED2 in [plan-hdr-nearblack-lut.md](plan-hdr-nearblack-lut.md) |

## 5. Things not to retry

| What | Why it failed | Where written up |
|---|---|---|
| `spotread -Y A` (fixed integration) to speed up near black | Reads 0 at 0.05 nit: too short to count any light | Section 7, T-INT1 |
| Trusting readings under ~0.015 nit as zero light | Meter floor: the ColorMunki reads 0 there whether or not the panel emits | BevelTipDrip (2026-11-18): "most meters are inaccurate below a certain level"; Q-5 |
| A `.bat` build script | `(x86)` in the VS path breaks cmd blocks | [building-and-tools.md](building-and-tools.md#traps) |

## 6. Settings that are known good

- ArgyllCMS 3.5.0 `spotread -e -y o -x -O -X <ccmx>`: emissive, OLED type, one reading per call.
- Readings per patch follow HCFR's "Adapt" rule: 5 under 1 cd/m2, 4 under 2, 3 under 5, 2 under 10, then 1.
  Speed-ups are queued (Q-9).

## 7. Meter timing (2026-11-19)

**T-INT1: adaptive vs fixed integration (2026-11-19 02:20, run by Claude for BevelTipDrip, log `data/meter-t-int1-adaptive-vs-fixed-2026-11-19.csv`).**
Grey code 36 (neutral profile), five readings each. Adaptive (Argyll's default): 9.5 s per reading, Y 0.0498, spread
1.5%, xy spread 0.0008. Fixed (`spotread -Y A`): 2.4 s per reading, **Y = 0 every time**: its integration is too
short to count any light at 0.05 nit. Code 64 was not reached (the test script divided by the zero readings).

- The ColorMunki Display (i1d3) has no dark calibration; start-up is ~1.3 s. Near black the time is the adaptive
  integration on every reading (~7-10 s; 14.6 s on black). HCFR feels faster because it uses a fixed 0.4 s
  integration and fewer, brighter patches.
- One `spotread` session per run is not possible through a pipe (it reads the console) and would save ~1.3 s.
- The lever is fewer readings per patch (`--agree`, Q-9).
