# Profiles reference: corrections built from measurements, and how they are installed

Read it **before changing profile building or installing, and before every test of a profile.** **Keep it current:**
a new rule, symptom or dead end goes in here the same day, in one line with a pointer to the findings. Parent:
[START-HERE.md](START-HERE.md).

## 1. Directory

| What | Where |
|---|---|
| MHC2 profile builder | `tools/build_mhc2.py` ([mhc2-lut](../changes/profiles/mhc2-lut.md), [lut-snap](../changes/profiles/lut-snap.md)) |
| Install / switch / show HDR profiles, toggle HDR | `tools/set_hdr_profile.py` ([set-hdr-profile](../changes/profiles/set-hdr-profile.md)) |
| Example profiles (one AW3225QF unit) | `profiles/` |
| Installed profiles | `C:\Windows\System32\spool\drivers\color\` |
| Design and test write-ups | [plan-hdr-nearblack-lut.md](plan-hdr-nearblack-lut.md) |

## 2. Invariants: must hold after every change

| # | Rule | What broke when it didn't | How to verify |
|---|---|---|---|
| 1 | LUT outputs in the corrected range are whole panel codes + 0.25 (snapped), not fractional codes | v1 undershot by one panel step: 0.05 nit -> 0.027 (T-NB7) | `snap_lut`; the table `build_mhc2.py` prints ("predicted" uses the truncated code) |
| 2 | The LUT never decreases | A non-monotone LUT inverts tones | `build_lut`, `snap_lut` |
| 3 | No jump at the meter's floor: inputs under the lowest reliable reading ramp linearly from 0 | v1 draft had identity below the floor, then a jump | `build_lut` |
| 4 | Identity from `--blend-end` (30 nits) up | The panel tracks there; a correction would fight the meter's own error (Q-17) | `build_lut` |
| 5 | The profile ID (MD5) is recomputed after any change to the file | Windows may reject or cache a profile with a stale ID | `write_icc` |
| 6 | Profiles are per unit and per HDR preset; the name says which | A True Black 400 profile in Peak 1000 corrects the wrong curve | file names in `profiles/` |

## 3. Before every test

1. A person has said go (changing the display's profile is a go action).
2. `set_hdr_profile.py --show`: the HDR profile under test is the default.
3. NVIDIA "Override to reference mode" unticked.
4. The OSD preset matches the profile.

## 4. Symptom -> first place to look

| Symptom | Most likely cause | Look at |
|---|---|---|
| Profile set, nothing changes on screen or meter | NVIDIA Control Panel "Override to reference mode" ticked: it bypasses OS colour transforms | T-NB4 to T-NB7; [building-and-tools.md](building-and-tools.md#traps) trap 3 |
| Settings lists no profiles; `mscms` calls return E_INVALIDARG | Windows lost the monitor from colour management after a restart | Device Manager > Monitors > Scan for hardware changes; Q-11 |
| Correction gone after sleep | Windows did not re-apply the profile after standby | Q-3 |
| `--set` reports the old profile as default | Already-associated profile is not made default again | Q-10 |
| Near-black steps one step too dark | Fractional LUT outputs (built with `--no-snap`) | Invariant 1 |

## 5. Things not to retry

| What | Why it failed | Where written up |
|---|---|---|
| Changing the monitor's firmware tables | The update package is encrypted and signed; not pursued, out of scope (BevelTipDrip, 2026-11-18) | [plan-roadmap.md](plan-roadmap.md#goal) |
| Fractional LUT outputs (v1, `--no-snap`) | Truncated to the code below: one panel step too dark | T-NB7, [lut-snap](../changes/profiles/lut-snap.md) |
| Testing a profile with NVIDIA reference mode on | The profile is ignored; every run measures the uncorrected panel | T-NB4, T-NB5, T-NB6 |
| dwm_lut for games | Does not reach fullscreen (independent flip) games | [plan-hdr-nearblack-lut.md](plan-hdr-nearblack-lut.md#design) |

## 6. How Windows applies an MHC2 profile (HDR mode)

- The `MHC2` tag holds min and peak luminance, a 3x4 matrix and three 1D LUTs (`sf32`, one entry per 10-bit code
  here). In HDR the GPU's display pipeline applies the matrix, then the LUTs to the PQ signal, for everything sent
  to the display: desktop, composed windows and independently flipped full-screen swapchains (T-NB7).
- The pipeline **truncates** the LUT output to a whole 10-bit code: 40.87 is sent as 40 (T-NB7).
- The Windows HDR Calibration app writes an MHC2 profile with an identity 2-entry LUT, a colour matrix and the
  peak set in the app; `build_mhc2.py` copies that profile and replaces only the LUTs, the description and
  optionally the peak.
