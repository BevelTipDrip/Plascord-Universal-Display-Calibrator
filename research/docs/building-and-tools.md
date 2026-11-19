# Building and tools

Parent: [START-HERE.md](START-HERE.md). **Do not re-install the toolchain or re-derive the build: it is here.** When
a step changes or a new trap is found, update this page the same day.

## Paths

| What | Where |
|---|---|
| Repo | `git clone https://github.com/BevelTipDrip/Plascord-Universal-Display-Calibrator.git` |
| Meter software (not in git) | `tools/argyll/`: `spotread.exe`, `dispwin.exe` and the meter correction (`.ccmx`), per person (below) |
| Measurement CSVs | `research/docs/data/` (in git; the probe writes there) |
| Built profiles | `profiles/` (examples in git; others local) |
| Installed Windows profiles | `C:\Windows\System32\spool\drivers\color\` |

## Toolchain

Windows 11 (all of it today; Linux is planned, Q-14). Versions as installed on 2026-11-18 by BevelTipDrip:

| What | Version | Notes |
|---|---|---|
| Python | 3.8.10 (`python`; `py -0` also lists 3.10 and 3.14) | Standard library only (`ctypes`, `tkinter` for SDR mode). Any 3.8+ works |
| Visual Studio Build Tools | 2026 (18), C++ workload | `cl` for the patch generator. `build.ps1` expects `C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools`; edit `$vs` there for another install |
| ArgyllCMS | 3.5.0 | https://www.argyllcms.com/ (AGPL-3.0, so not shipped here). Copy `bin\spotread.exe` and `bin\dispwin.exe` into `tools/argyll/`. Use 3.0 or newer: 3.0 fixed the i1d3's low-level red readings on OLED. The ColorMunki Display needs no driver |
| Meter correction | `tools/argyll/AW3225QF_i1d3.ccmx` | Descriptor "i1 DisplayPro, ColorMunki Display & Dell, AW3225QF (i1 Pro 2)". Not in git (the database's own file). Source: DisplayCAL's colorimeter corrections database, https://colorimetercorrections.displaycal.net/ (BevelTipDrip, 2026-11-18); search for AW3225QF, save it as `tools/argyll/AW3225QF_i1d3.ccmx`. Another meter or display: pass your own with `--ccmx`, or `--ccmx ""` for none |
| Meter | X-Rite ColorMunki Display (i1d3 family) | |

Display and driver settings for HDR work (why: [measurement-reference.md](measurement-reference.md)):

- Windows: Use HDR on for the display; Auto color management on.
- NVIDIA Control Panel > Change resolution > Color: full range, default colour; **"Override to reference mode"
  unticked** (Accurate). Reference mode bypasses Windows' HDR colour profiles.
- AW3225QF OSD: the HDR preset under test (True Black 400, Peak 1000, Desktop); Dark Stabilizer 0.

## Build

```
powershell -ExecutionPolicy Bypass -File tools/hdrgen/build.ps1
```

Writes `tools/hdrgen/hdr10_patchgen.exe` (a few seconds; `cl` prints nothing on success). Build output is not
committed (`.gitignore`). The Python tools need no build.

## Run

Every command that shows patches, reads the meter, changes a profile or writes DDC/CI values needs a person's go
first (START-HERE, Rules).

```
cd tools
# Measure (meter on the screen centre, room dark, display warmed up). --label = the run's test ID.
python nearblack_probe.py --mode hdr --label t-nb10-peak1000-dense --dense     # ~105 patches, ~80 min
python nearblack_probe.py --mode hdr --label t-nb11-tb400-check               # standard 26 levels
python nearblack_probe.py --mode hdr --label t-nb12-spot --levels 0.05,0.1,1,10,100
python nearblack_probe.py --mode sdr --label t-sdr1-creator-g22

# Build a profile from a dense run, then install it as the display's HDR profile.
python build_mhc2.py --csv ../research/docs/data/nearblack-t-nb3-tb400-dense-2026-11-18.csv --name "AW3225QF TB400 near-black fix v2"
python set_hdr_profile.py --install "../profiles/AW3225QF TB400 near-black fix v2.icc"
python set_hdr_profile.py --show

# DDC/CI (tools/ddc/, research/docs/ddc-reference.md). Reads need no go; `set --yes` writes and needs one.
python -m ddc list                     # monitors DDC/CI can reach (--backend fake: an in-memory demo monitor)
python -m ddc caps                     # the capabilities string, parsed (--raw as sent)
python -m ddc get 10 12 16 18 1A 6C 6E 70
python -m ddc set 6C 48                # dry run: checks and prints, writes nothing
python -m ddc set 6C 48 --yes          # writes a whitelisted code, reads back; only with a person's go

# Unattended runs: wake the display before, turn it off after.
python display_power.py wake
python display_power.py off
```

`build_mhc2.py --base` defaults to this machine's Windows HDR Calibration profile (`DEFAULT_BASE`): on another
machine, pass your own (Windows HDR Calibration app output, in the colour folder above).

## Test

Measurement results come from meter runs, each with a test ID written up in its plan doc (`T-NB<n>` in
[plan-hdr-nearblack-lut.md](plan-hdr-nearblack-lut.md)); every module brings its own tests (Q-12).

Unit tests (no hardware; standard library `unittest`; the `unit-tests` workflow runs them on every push and pull
request, Python 3.12 on Linux). From the repo root:

```
python -m unittest discover -s tools/ddc/tests -t tools          # DDC/CI package: fake backend only
```

The Windows-only check that `Dxva2Backend` refuses to start off Windows is skipped on Windows (it would enumerate
the real monitors). The tools support Python 3.8: run the tests with `py -3.8` too after a change.

The docs are checked with:

```
python research/tools/changemap.py check
```

## Debug and profile

- The generator prints `READY hdr=1 composed=0 w=... h=... display_min=... display_max=...` (from DXGI) at start,
  or `ERROR ...` (e.g. Windows HDR off) and exits.
- The probe reads a 100-nit (HDR) or white (SDR) reference first and stops if it is out of range (meter off the
  patch, screen asleep); `--diagnostic` only warns, for test profiles that change the reference.
- `set_hdr_profile.py --show` prints the display's current HDR and SDR profiles as Windows reports them.

## Research tools

| Tool | Where | Use |
|---|---|---|
| `changemap.py` | `research/tools/` | Change map lookups and checks ([README](../changes/README.md)) |
| `python -m ddc` | `tools/ddc/` (run from `tools/`) | Read monitor VCP codes over DDC/CI; dry-run writes ([ddc-reference.md](ddc-reference.md)) |

## Traps

Things that cost someone time. Number them; never delete one, strike it through if it stops applying.

1. Windows turns the display off after 60 s idle here: a run that crossed it read nothing (2026-11-18). The probe
   and the generator hold the display awake (`SetThreadExecutionState`); the start and end reference checks catch
   it if that fails.
2. A `.bat` build script failed with "\Windows was unexpected": `(x86)` in the VS path breaks cmd's `if (...)`
   blocks. Use `build.ps1`.
3. NVIDIA "Override to reference mode" ticked = Windows' HDR profile is silently ignored: every LUT test before
   18:18 on 2026-11-18 measured the uncorrected panel ([profiles-reference.md](profiles-reference.md)).
4. After a restart Windows can lose the monitor from colour management (Settings lists no profiles, `mscms` calls
   return E_INVALIDARG): Device Manager > Monitors > Scan for hardware changes (Q-11).
