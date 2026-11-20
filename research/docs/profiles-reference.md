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
| Settings lists no profiles; `mscms` calls return E_INVALIDARG; Settings crashes on "Add profile" (Windows.UI.Xaml.dll, 0xc000027b) | `EnumDisplayDevices` lists no monitor under the GPU output, while PnP (status OK), WMI, the monitor device interface and DisplayConfig (`monitorDevicePath`) all still have it; per-user associations (HKCU ...\ICM\ProfileAssociations\Display\{4d36e96e-...}\0000, `ICMProfileAC`) intact, and the last-loaded profile stays applied | Device Manager scan fixed it once (2026-11-18 ~18:05), not the second time (22:30); unplugging DP or power did not either. Q-11 |
| Correction gone after sleep | Windows did not re-apply the profile after standby | Q-3 |
| Correction gone after a reset, re-plug, input or PBP/PIP change; a different default in Settings | The monitor came up as its other device instance (or a new hardware ID) whose association slot is empty, so Dell's identity "HDR True Black 400" profile applies | Section 7; Q-22 |
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

## 7. Dell's monitor driver and the profile Windows falls back to (found 2026-11-19)

Read-only look at what Dell's software left on this PC (BevelTipDrip, 2026-11-19: "I think it's worth unpacking it,
read only obviously, without integrating any code"; only the INF and ICC files Windows already uses were read, no
installer was unpacked or run). Found, not yet confirmed by a test:

- **Dell's monitor driver** (`aw3225qf.inf` 1.1.0.0, 2026-06-18, installed as `oem129.inf`; 1.0.0.0 of 2023 is
  outranked) gives the monitor a different hardware ID per input and mode: DisplayPort `DELA245`, DisplayPort HDR
  `DELA246`, PBP `DELA247`, PIP `DELA248`, HDMI1/2 `DELA249`-`DELA250`. Ours runs as `DELA246`. On install it
  **deletes** the device's `ICMProfile` and `ICMProfileAC` and, for the HDR IDs, sets `ICMProfileAC` to
  `Alienware_AW3225QF_HDR True Black 400.icm`. (Its DisplayPort HDR and PIP sections copy each other's file lists;
  harmless here, the file is in the colour folder.)
- **Dell's "HDR True Black 400" profile corrects nothing:** MHC2 with an identity matrix and an identity 256-entry
  LUT, min 0.0002 / max 460.42 nits; primaries rXYZ 0.5646/0.2506/0.0040, gXYZ 0.2623/0.7013/0.0431, bXYZ
  0.1455/0.0614/0.7715. With it applied the panel is uncorrected: near black raised and tinted as in T-NB3/T-NT0.
- **Two device instances of the monitor**, each with its own association slot:
  `DISPLAY\DELA246\5&14b0e70&0&UID4353` (Started; driver key `0000`) and
  `DISPLAY\DELA246\1&8713bca&0&UID0` (Disconnected; driver key `0001`). The per-user list
  (HKCU `...\ProfileAssociations\Display\{4d36e96e-...}\0000`, `UsePerUserProfiles=1`) holds our
  profiles; slot `0001` is empty, so when Windows brings the monitor up as the other instance it falls back to
  the device default, Dell's identity profile, and the correction is gone. A likely cause of profiles "changing"
  after resets (Q-10, Q-11), and of switching to PBP/PIP or the other HDR input (new hardware ID, new instance).
 
  Q-22, on hold until we know what the second instance is (BevelTipDrip, 2026-11-19).
- **Command Center can reinstall itself:** an extension driver bound to the monitor (`awfxdisp_aw3225qf_ext_monitor.inf`,
  `oem27.inf` 1.0.0.0 bound, 2.0.0.0 `oem115.inf` staged) adds a software component whose driver
  (`AWCC_IM_Driver_Component.inf`, 2.7.2.0) runs `AWCCInstallationManager.exe /silent /IS_DRIVER_FLOW:YES
  /ISFeatureInstall:ALL` (Command Center 6.14.4.0). The component device is Started; its logs show attempts on
  2026-10-09, 2026-10-11 and 2026-11-15, the last two aborted (0x643). Leftovers: `C:\ProgramData\Alienware`
  (575 MB of cached installers, among them `AWDisplayInstaller.exe`), `C:\ProgramData\Dell` (logs),
  `DellInstrumentation.sys` staged in the driver store. Q-21. No action: BevelTipDrip disabled the installation on purpose (2026-11-19).

**Q-11 again, 2026-11-19 evening** (reported by BevelTipDrip: "it looks like the HDR profile bug returned"). The
active monitor is the same instance as before, `DISPLAY\DELA246\5&14b0e70&0&UID4353` (slot `0000`, our profiles);
UID0 is Disconnected. So this is not Q-22. `EnumDisplayDevices` lists `\\.\DISPLAY17` (RTX 4090, attached) with
no monitor under it, and `set_hdr_profile.py --show` gets 0x80070057: the Q-11 symptom. DDC/CI (dxva2) still reaches
the monitor on `\\.\DISPLAY17`. The System log has no PnP add or remove for the monitor. It has only display power
transitions (Kernel-Power 566) at 15:08-15:09 and 18:38-18:51; the latter match the DDC wake/sleep tests on
feature/ddc-module. Not known which transition, if any, dropped it. Candidate: display power cycles, which tie
in with Q-3.

**Restored by CRU `restart64.exe` again** (run by BevelTipDrip, 2026-11-19: "running restart64.exe worked again, so
something about the deep reset of the graphics driver CRU does seems to fix it"). Afterwards:
- The output is renamed `\\.\DISPLAY33` (it was 17; each restart adds 16), and the monitor is listed under it again,
  the same instance UID4353.
- `set_hdr_profile.py --show` works again: the HDR default is the neutral measuring profile, and the SDR entry is
  Dell's `Alienware_AW3225QF_HDR True Black 400.icm`.
- DDC/CI lists the monitor on `\\.\DISPLAY33`.

Two out of two recoveries came from the full GPU restart, not from Windows' own driver reset or a re-plug.
