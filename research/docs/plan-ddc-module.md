# Plan: a DDC/CI package that reads and writes a monitor's VCP codes safely, Windows first, Linux later

Status: planned 2026-11-19; D1 built `e40689f`; D1b, D2b, D2c built (`1a5b876`, `328832c`, `43fc609`) and D4's
parser (`b90f29d`), 2026-11-19; not run on a monitor; for BevelTipDrip to review (every assumed decision is under
[Open questions for BevelTipDrip](#open-questions-for-beveltipdrip)). Parent: [START-HERE.md](START-HERE.md).
Owner: BevelTipDrip (drafted by a Claude agent while BevelTipDrip was away). Work queue: Q-20 (related: Q-6, Q-12).
Branch: `feature/ddc-module`. Card: [ddc-module](../changes/ddc/ddc-module.md). Read
[ddc-reference.md](ddc-reference.md) first.

## Why

BevelTipDrip (2026-11-19, relayed by the lead agent): "launch a sub-agent to start the work to build a ddc/ci
module". The roadmap's S3 needs the monitor's DDC/CI black level (Q-6), and S4 plans display-specific controls as
modules on a shared core ([plan-roadmap.md](plan-roadmap.md#goal)). Today the only DDC/CI code lives inside the
measurement probe (`tools/nearblack_probe.py` on `feature/nearblack-tint`), where nothing else can use it and
nothing tests it without the monitor.

Goal: one small, standard-library package that any tool (the probe, a later MCP server, a UI) uses to list
monitors, read any VCP code, and write a short list of VCP codes with checks that make a wrong write unlikely and a
changed value always restorable. Writes are tested without hardware, on a fake backend.

## What is known today

The probe's DDC/CI code (`origin/feature/nearblack-tint` at `1703b92`, `tools/nearblack_probe.py`) [V, read
2026-11-19]:

| Piece | Lines | What it does |
|---|---|---|
| `BLACK_VCPS`, `DDC_VCPS` | 48-51 | The only codes the probe writes: 16 / 18 / 1A (R/G/B gain), 6C / 6E / 70 (R/G/B black level) |
| `open_monitor(name_hint)` | 84-96 | `EnumDisplayMonitors`, then dxva2 `GetPhysicalMonitorsFromHMONITOR`; returns the first handle whose description contains the hint (default `AW3225QF`). Handles of other monitors are never destroyed |
| `vcp_get(h, code)` | 99-103 | `GetVCPFeatureAndVCPFeatureReply` -> (current, max); raises on failure |
| `vcp_set(h, code, value)` | 106-112 | `SetVCPFeature`, 3 tries 0.3 s apart, 0.15 s settle after success |
| `parse_ddc_steps(text)` | 115-132 | `'16=96;16=100,1A=96'` -> list of {code: value}; refuses codes outside `DDC_VCPS` |
| `restore_vcps(h, saved)` | 135-142 | Writes every saved value back; a failure prints "reset it in the OSD" |
| Use in `run()` | 785-808, 821-824 | Reads each code's current and max, refuses a step value outside 0..max, saves the currents, writes each step, prints a read back (not compared), restores before the end reference, and again in `finally:` |

Gaps the package closes [I, from the code]: the read back is printed, not checked; a value is checked against max
only for the whole step list up front; no `argtypes` on the dxva2 calls (handles are passed as plain ints); no
capabilities string; nothing runs without the monitor.

What the AW3225QF reported over DDC/CI ([plan-nearblack-tint.md on its branch], 2026-11-18) [V there]: gains 16 /
18 / 1A read 100 of 100; black levels 6C / 6E / 70 read 50 of 255. Only the OSD preset "Custom Color HDR" offers
colour controls, so the gains most likely do nothing in other presets [I] (BevelTipDrip, 2026-11-18). The DDC route
for the grey-scale tint was dropped on that branch (BevelTipDrip, 2026-11-18); `--ddc-steps` stays for Q-6.

## Design

A package `tools/ddc/` (name: open question 1), standard library only, Python 3.8+, run as `python -m ddc` from
`tools/` like the other tools.

| File | What |
|---|---|
| `backend.py` | `Backend` interface, `MonitorInfo`, `VcpReply`, `DdcError`, `parse_vcp_code`, `VCP_NAMES`, `Backend.wait` (the pause between requests) |
| `mccs.py` | `MCCS_NAMES`: the MCCS 2.2a standard VCP names 00-DF (from ddcutil's feature table, which follows the VESA document), `WRITE_ONLY`, `mccs_name` (E0-FF: "manufacturer specific") |
| `windows.py` | `Dxva2Backend`: dxva2 through ctypes with `argtypes`; owns and destroys its physical-monitor handles; error messages carry the Windows error code |
| `fake.py` | `FakeBackend` / `FakeMonitor`: in-memory monitors with failure injection (reads that fail, writes that fail or are ignored, codes that answer 0 of 0), a VCP type per code, and logs of every write, read and wait |
| `safety.py` | `SafeDdc`: the only way the package writes. Never list, whitelist, range check, read back, `preserve()` save-and-restore, `restore()` |
| `scan.py` | `scan()`: read-only discovery of every code 00-FF against the capabilities string; table, CSV, JSON |
| `caps.py` | `parse_capabilities`: the MCCS capabilities string -> model, MCCS version, VCP codes and their allowed values |
| `cli.py`, `__main__.py` | `list`, `caps`, `get <vcp>...`, `scan [<vcp>...] [--csv F] [--json F]`, `set <vcp> <value> [--allow <vcp>,...]` (dry run unless `--yes`) |
| `tests/` | `unittest` tests on the fake backend |

Backend interface (every backend, Windows now, Linux later):

```
monitors() -> [MonitorInfo(index, description, device)]
get_vcp(index, code) -> VcpReply(current, maximum, vcp_type)
set_vcp(index, code, value)            # raw write, no checks: only SafeDdc calls it
capabilities(index) -> str             # the raw MCCS string
close()                                # also a context manager
```

Monitors are addressed by their index in `monitors()`; the CLI and `SafeDdc` callers pick one by a description
substring (like the probe's `--monitor`) or by index, and refuse when the choice is ambiguous.

Alternatives considered:

- **Wrap winddcutil or ddcutil as programs**: one more install per person (the project installs only ArgyllCMS),
  output parsing, and on Windows nothing that dxva2 does not already give. ddcutil stays the likely Linux route,
  either as a program or by reading its approach (below). Open question 3.
- **Keep it inside the probe**: no tests without hardware, and S4 / Q-13 would copy it again.
- **A framework now** (plugins, device database, async): Q-12 has not decided the architecture; a small package
  can move under whatever Q-12 decides.

### Safety rules (in `SafeDdc`; checked by the tests)

0. **Never list** (`NEVER_WRITE`, plus a display module's own `never` codes). Refused by every route: `SafeDdc`
   refuses to be built with one in its whitelist, `check_write`, `preserve()` and `restore()` check it again
   first, and the CLI's `--allow` cannot name one (exit 2, nothing written). Reading them is allowed. The codes:

   | Code | What | Why never | Source of the choice |
   |---|---|---|---|
   | 04, 05, 06, 08, 0A | MCCS factory restores (all, brightness/contrast, geometry, colour, TV) | Wipe user settings; not undoable over DDC/CI | Lead agent's brief, 2026-11-19 |
   | 60 | Input source | A wrong input leaves no picture to recover from | Lead agent's brief |
   | D6 | Power mode | Standby or off | Lead agent's brief |
   | B0 | Store / restore settings | Value 2 restores factory defaults (MCCS) | Drafting agent, 2026-11-19 [I, from MCCS] |
   | CA | OSD / button lock | A locked OSD removes the hand reset every restore message relies on ("reset it in the OSD") | Drafting agent, 2026-11-19 |
   | 76 | Remote procedure call | Runs a vendor-defined procedure; effect unknown | Drafting agent, 2026-11-19 |
   | 78 | Display identification data (EDID) operation | Identification data; nothing in this project needs to touch it | Drafting agent, 2026-11-19 |

   A display module can add its own never codes (the AW3225QF's: E1, C8, C9;
   [AW3225QF display module](#aw3225qf-display-module-skeleton)). No public source ties any VCP code to a
   firmware update or a service/factory mode. Every row the drafting agent added is for BevelTipDrip to review
   (open question 12).
1. **Write whitelist.** Only codes in the whitelist are written. Default (`DEFAULT_WRITE_WHITELIST`): brightness
   10, contrast 12, gains 16 / 18 / 1A, black levels 6C / 6E / 70 (BevelTipDrip, 2026-11-19, Decisions). Any
   other code that is not on the never list is writable for one call only when the caller names it: the CLI's
   `set <vcp> <value> --allow <vcp>[,<vcp>...] --yes`, or `SafeDdc(..., whitelist=...)` in code. `--allow`
   without `--yes` is a dry run like any other. Range check, read back and restore apply to allowed codes the
   same way.
2. **Range check against the monitor.** Before every write: an integer, read the code's current and max from the
   monitor, refuse unless 0 <= value <= max. A read failure refuses the write.
3. **Read back after every write.** After the write (and the backend's settle delay), read the code again; a value
   other than the one written raises `ReadbackMismatch` with what was read (open question 6: exact match or a
   tolerance).
4. **Save, then restore.** `with ddc.preserve([codes]):` reads and saves every code first (all must be
   whitelisted, or nothing starts), and on leaving the block, normally or by any exception (Ctrl+C included),
   writes each saved value back and reads it back. Restore failures are collected and raised together, chained to
   the exception that ended the block, with "reset it in the OSD".
5. **A person's go before any write to a real display** (START-HERE, Rules). The CLI's `set` is a dry run unless
   `--yes` is given: it prints current, max and the planned value, and writes nothing. `--yes` is how the person
   who gave the go confirms it; it is not the go. When a `set --yes` write fails or reads back another value, the
   CLI writes the value it read just before back (`SafeDdc.restore`, with a read back) and says so, or raises
   `RestoreFailed` with "reset it in the OSD".
6. **The raw `set_vcp` is never called outside `safety.py`** (a test greps for it).

### Read-only discovery: `scan` (D2b)

BevelTipDrip's goal is to control every setting the monitor exposes, hidden ones included (Decisions). The first
step only reads: `python -m ddc scan` asks for the capabilities string, then sends Get VCP Feature for every code
00 to FF, waiting at least 50 ms before each request (MCCS timing; `--interval` may be longer, never shorter). Per
code it records whether the monitor replied, the VCP type (momentary or set parameter), current and max, whether
the capabilities string lists the code (and the values it lists), and the MCCS 2.2a name. The table shows the codes
that replied or are listed (`--all`: every code) and ends with two lists: **hidden-setting candidates** (reply, not
in the capabilities string) and codes listed but silent. `--csv FILE` and `--json FILE` write the whole result;
neither ever overwrites a file.

- **It cannot write** [V by the tests; I for the hardware]: it calls only `capabilities` and `get_vcp`; a test runs
  it on a backend whose `set_vcp` fails the test. In MCCS, Get VCP Feature (opcode 01) and Set VCP Feature (03)
  are different requests, so reading 04 (restore factory defaults) asks for a value and cannot trigger the reset
  [I, from the protocol; ddcutil's `getvcp` and `scan` read every code the same way].
- **A reply is not proof a control exists**: some monitors answer 0 of 0 (flagged "may be unsupported"), or answer
  codes they ignore on write. What a hidden code does is found later, one code at a time, with a go for each
  write (T-DDC3 and after).
- Risks of reading [I]: on the AW3423DWF, constant DDC/CI polling made the OSD disappear (Twinkle Tray issue 536);
  one scan is 257 requests, not constant polling. Do not scan during a measurement run.
- Run time on the AW3225QF: unknown; at 50 ms plus each read's own time, a few seconds to a minute or two.

### AW3225QF display module (skeleton)

Working assumption for open question 2 (the lead agent's, 2026-11-19): the core knows MCCS; per-display knowledge
lives in `tools/ddc/displays/<model>.py`, Python data loaded by `displays.for_monitor(description, model)`. The
first is `aw3225qf.py`: per code a name, what it does, value meanings, which OSD presets lock it, whether a
capabilities string lists it, its source, whether it was confirmed on BevelTipDrip's monitor, and a safety class:

| Class | Meaning | AW3225QF codes |
|---|---|---|
| safe | The core's default whitelist; `set ... --yes` (with a go) | 10 12 16 18 1A 6C 6E 70 |
| ask first | Only with `--allow` and a go for that write | every other listed code, all unknown manufacturer codes |
| never | Added to `NEVER_WRITE` for this monitor; nothing overrides it | 04 05 08 60 CA D6 (core), E1 (Dell power), C8 C9 (identification, firmware level) |

A module can only add never codes; it cannot make a code writable (tests: `test_displays.py`). `get`, `caps` and
`scan` print the module's names and value meanings; `set` applies the never codes of the module the monitor's
description matches even with `--display none`. `python -m ddc display --display aw3225qf` prints the table
without a monitor.

**What is known about the AW3225QF's codes** (research 2026-11-19 by a sub-agent of the drafting agent, two
sources re-checked by the drafting agent; web pages only, no personal data in queries, nothing on firmware):

- **[V] BevelTipDrip's monitor, 2026-11-18** (probe reads, [plan-nearblack-tint.md](plan-nearblack-tint.md)):
  16 / 18 / 1A read 100 of 100, 6C / 6E / 70 read 50 of 255. Only Custom Color HDR offers colour controls (hue and
  saturation) in the OSD; the other HDR presets lock them (BevelTipDrip, 2026-11-18).
- **Another person's AW3225QF** (ddcutil capabilities, MCCS 2.1, 2024-03-31,
  [vdu_controls issue 84](https://github.com/digitaltrails/vdu_controls/issues/84); high confidence for that unit,
  re-read by the drafting agent): lists 02 04 05 08 10 12 14 (01 05 08 0B 0C) 16 18 1A 52 60 (0F 11 12) 87 AC AE
  B2 B6 C6 C8 C9 CA CC D6 DC DF and manufacturer codes E0 E1 E2 E3 E4 E5 E8 E9 EA EC F0 F1 F2 F4 F5 FE FD. **It
  does not list 6C / 6E / 70**, which BevelTipDrip's monitor answered: if T-DDC2 shows the same on this unit, the
  black levels are the first hidden settings found [I]. No 62 (volume), no E7 (Dell USB/KVM). Input 60 reads
  0x0F0F for DisplayPort: use the low byte.
- **AW3423DWF** (the closest Alienware QD-OLED; [aw3423dwf-tray VCP map](https://github.com/ykoval/aw3423dwf-tray/blob/main/VCP_MAP.md),
  firmware M3B107; medium confidence, re-read by the drafting agent; from that model, not confirmed on this
  monitor): **E2 reports the OSD preset** (writes ignored; HDR: Desktop 39, Movie HDR 35, Game HDR 36,
  DisplayHDR 58, Custom Color HDR 255) - a read could tell the probe which preset is active; **F0** with 14
  selects presets; **F2** reads 65 with HDR on, 0 off; **F4** is a command register (Dark Stabilizer: write 48+N
  to set, write 63 then read to get), so Dark Stabilizer cannot be read without a write; **10 / 12 are stored
  per preset**; the Peak 1000 toggle changed no polled code.
- **Dell U / P models** (low to medium confidence; not confirmed on this monitor):
  [ddccontrol-db U3421WE](https://raw.githubusercontent.com/ddccontrol/ddccontrol-db/master/db/monitor/DELA181.xml):
  **E1 = power, inverted** (0 on, 1 off), E7 USB/KVM, E9 PiP/PbP (some modes change the EDID: Windows may
  re-detect the display and drop its profile, Q-11); E8 PiP second input
  ([U2723QE notes](https://gist.github.com/lainosantos/06d233f6c586305cde67489c2e4a764d)). E0 E3 E4 EA EC F1 F5
  FD FE: meaning unknown anywhere found.
- **Hidden / service / firmware**: no public source ties any VCP code to a firmware update, a service menu or a
  factory mode on Dell or Alienware monitors; no VCP code is known to start the OLED panel refresh (Dell documents
  it only in the OSD). Dell does not publish its manufacturer codes
  ([Dell community](https://www.dell.com/community/Monitors/U3818DW-Please-publish-the-VCP-MCCS-codes/m-p/6188173)).
  ddcutil warns that manufacturer features "may have irreversible consequences"
  ([ddcutil-service man page](https://manpages.opensuse.org/Leap-16.0/ddcutil-service/ddcutil-service.1)): every
  unknown E0-FF code is "ask first".
- **Behaviour**: constant DDC/CI polling made an AW3423DWF's OSD disappear
  ([Twinkle Tray 536](https://github.com/xanderfrangos/twinkle-tray/issues/536)); an AW3926QW dropped a Set right
  after a probe ([ddcutil 626](https://github.com/rockowitz/ddcutil/issues/626)).
- Not found: MonitorControl, ClickMonitorDDC and forum reports on AW3225QF codes; a raw AW3225QF capabilities
  string (only ddcutil's parsed listing).

### How it is tested (project rule: every module brings its own tests)

- **Deterministic, no hardware** (`python -m unittest discover -s tools/ddc/tests -t tools`): every safety rule
  on the fake backend (refused code, out of range, failed read, ignored write -> mismatch, restore on exception,
  restore failure reported, nothing written when `preserve` refuses), the capabilities parser on sample strings,
  VCP code parsing, monitor selection, and the CLI end to end on the fake backend (dry run writes nothing). The
  Windows backend is not exercised by the tests: on Linux CI they check only that it fails cleanly.
- **On the real monitor, read only** (no go needed): `list`, `caps`, `get` of a few codes. Results go in this doc
  under a test ID `T-DDC<n>`.
- **On the real monitor, writes** (needs a go from BevelTipDrip each time): a later test, e.g. `set 6C 50 --yes`
  (writing the value it already has), then one step away and back inside `preserve`, confirming the OSD. Not
  planned here; it belongs with Q-6.

### Linux route (not built)

Linux talks DDC/CI over I2C: the `i2c-dev` kernel module exposes each display connector's DDC bus as
`/dev/i2c-<n>`; the monitor answers at address 0x37. A `LinuxI2cBackend` would open the device, `ioctl(I2C_SLAVE,
0x37)`, and send the MCCS "Get VCP Feature" / "Set VCP Feature" / "Capabilities Request" packets (with the
checksum and the 40-50 ms waits the spec requires), standard library only (`fcntl`, `os`). Finding which bus is
which monitor means reading each bus's EDID at 0x50. ddcutil does all of this and is the reference
(`ddcutil detect`, `getvcp`, `setvcp`, `capabilities`); the alternative is a `DdcutilBackend` that runs it as a
program. Permissions: the user needs access to `/dev/i2c-*` (the `i2c` group, or ddcutil's udev rule). NVIDIA's
proprietary driver has needed `NVreg_...` options for DDC on some versions [I, from ddcutil's docs; not checked
here]. Open question 4. Queue item: part of Q-14 or a new row when started.

### How the probe would adopt it (D4: may happen on this branch; not switched yet)

BevelTipDrip (2026-11-19, Decisions) allowed the switch on this branch. Built so far: `ddc/steps.py`,
`parse_ddc_steps(text, codes)`, the probe's function with the allowed codes as a parameter (`PROBE_VCPS`, the
probe's six); `tests/test_steps.py` checks it against 23 inputs whose results and exceptions were recorded from
the probe's own function (blob `221f64c`). **`tools/nearblack_probe.py` is not edited.** Why the drafting agent
(2026-11-19) stopped there:

1. **Read back on a mismatch: stop or carry on?** Today the probe writes, then tags the CSV with what the monitor
   reads back (`ddc_16=100_...`) and measures anyway. `SafeDdc.set` raises `ReadbackMismatch` instead (safety
   rule 3). In True Black 400 the gains are most likely locked [I], so a gain step would stop a run that runs
   today. Keeping the probe identical means catching `ReadbackMismatch` and carrying on, which works around rule 3;
   applying rule 3 changes the probe's behaviour. That is BevelTipDrip's choice (open question 13).
2. **Concurrent edits.** `feature/nearblack-tint` changed the probe three times on 2026-11-19 (`b9ccffb`,
   `e57d1b9`, `18b0034`, in `run()` among other places), and work on it continues in another checkout. The DDC
   code sits inside `run()` (lines 785-825); an edit here could conflict at the merge ("we just have to merge
   cleanly", BevelTipDrip, 2026-11-19).

Other differences a switch brings, none in the CSV or the flags [I, from the code]: one more read before each
write (`check_write`) and one after it (the read back), so each step takes about two DDC/CI reads longer; a
description matching two monitors raises (the probe takes the first); every physical-monitor handle is released
(the probe destroys only its own); error texts change (`DdcError` instead of `RuntimeError`, same `ERROR:` path in
`run()`). A failed read before a write stops the step, as the probe's tag read after the write already does.

The switch, once open question 13 is answered (only the probe's DDC code changes):

```
from ddc import open_backend, SafeDdc, ReadbackMismatch
from ddc.steps import PROBE_VCPS as DDC_VCPS, parse_ddc_steps
...
be = open_backend()                                  # in run(), where open_monitor() was; be.close() in finally:
ddc = SafeDdc(be, be.find(args.monitor), whitelist=DDC_VCPS)
# up-front range check and saved_vcp: as today, with ddc.get(c)
for c, v in step.items():
    ddc.set(c, v)                                    # (13: or catch ReadbackMismatch and carry on, as today)
# restore_vcps(): ddc.restore(saved_vcp), printing "Restored ..." / "! failed ... reset it in the OSD" as today
```

Test: `test_steps.py` (parse), a fake-backend check of the `run()` DDC block if it is moved into a function, and
one probe `--ddc-steps` run on the monitor with a go (Q-6).

## Stages

| Stage | What | Switch | Test | State |
|---|---|---|---|---|
| D1 | Package, fake backend, safety layer, CLI, unit tests | none (new code, nothing imports it) | unit tests | built `e40689f` (62 tests pass, 2026-11-19) |
| D1b | Brightness 10 and contrast 12 writable by default; `--allow`; the never list; old value put back after a failed `set` | none | unit tests | built (this branch, 2026-11-19; commit in the card) |
| D2 | Read-only check on the AW3225QF: `list`, `caps`, `get` | | T-DDC1 | not started (monitor not reachable 2026-11-19, twice, below) |
| D2b | Read-only discovery: `scan` of 00-FF, MCCS names | none | unit tests; T-DDC2 | built (unit tests, 2026-11-19); T-DDC2 planned, not run |
| D2c | AW3225QF display module (skeleton): codes, value meanings, preset locks, safety classes, sources | none | unit tests; T-DDC2 fills it in | built (unit tests, 2026-11-19); entries not confirmed on this monitor except 16 18 1A 6C 6E 70 |
| D3 | One write on the AW3225QF, restored, with a go | | T-DDC3 | not started (needs a go) |
| D4 | The probe uses the package (on this branch: BevelTipDrip, 2026-11-19, Decisions) | | `test_steps.py`; a probe `--ddc-steps` run | `parse_ddc_steps` built in the package (unit tests, 2026-11-19); the probe not switched (open question 13) |
| D5 | Linux backend | | unit tests on a fake I2C device; a Linux machine | not started |

## Risks

- A wrong write changes the monitor's picture until reset in the OSD; a write to an unlisted code (input, power,
  factory reset) could do worse. The whitelist and the dry-run default are the guard; they hold only while nothing
  calls `set_vcp` directly.
- Some monitors quantize or ignore writes in some presets (the AW3225QF's gains outside Custom Color HDR [I]).
  Exact read back would then raise; that is wanted until a person decides otherwise.
- DDC/CI is slow and flaky on some links (DisplayPort MST, some docks): the retries and settle delays are the
  probe's, not tuned.
- Not tested: the Windows backend against any monitor other than BevelTipDrip's; two processes talking DDC/CI to
  the same monitor at once; Linux.

## Decisions

BevelTipDrip's answers of 2026-11-19, relayed by the lead agent to a later drafting agent (quoted exactly):

- **Open question 5, the write whitelist: yes to both.** Asked "Should the write list also include brightness (10)
  and contrast (12)? And should the command line ever accept codes beyond the list?", BevelTipDrip answered:
  "Yes." Built: 10 and 12 in `DEFAULT_WRITE_WHITELIST`; `set ... --allow <codes> --yes` for other codes, with a
  never list no option overrides (Safety rules 0 and 1; how `--allow` works and what is on the never list were
  chosen by the drafting agent, open question 12).
- **Open question 11, who switches the probe:** asked "Who switches nearblack_probe.py over to the package, and
  when?", BevelTipDrip answered: "Each branch doesn't have to be a seperate change entirely, it can be a set of
  changes, we just have to merge cleanly." So the probe's switch (D4) may happen on this branch.
- **Branches:** "Should we merge the DDC branch into ours instead of into the main repo? Branching off of our
  working repo probably would have made more sense." Done by the lead agent: this branch was merged into
  `feature/nearblack-tint` (`4dd9353`) and fast-forwarded to it; it merges back there, not into `main`.
- **The goal** (from the answer to open question 2, which stays open): "I'd like to be able to control every
  setting over DDC, maybe even hidden ones." Read as: read every VCP code the monitor answers, including codes its
  capabilities string does not list, and make each writable only through the safety layer. The first sentence of
  that answer ("I didn't put it there, so we should investigate what it is and if it has any useful information
  the monitor.") most likely refers to something else (a stray folder the lead agent is handling); not acted on
  here.

Everything still under Open questions was assumed by a drafting agent (2026-11-19) and is open.

## Open questions for BevelTipDrip

1. **Package location and name.** Assumed `tools/ddc/`, imported as `ddc`, run as `python -m ddc` from `tools/`.
   Alternatives: `tools/plascord_ddc/`, or a top-level `plascord/` package once Q-12 decides the layout.
2. **Core library or display module (S4 sense)?** Still open: BevelTipDrip's answer (Decisions) set the goal,
   control of every setting over DDC/CI, hidden ones included, but not the layout. Working assumption (the lead
   agent's, 2026-11-19): a core library (it talks the MCCS protocol, the same on every monitor) plus a per-display
   module for the AW3225QF (which codes do what, which presets lock them, safety classes); built that way as a
   skeleton (`tools/ddc/displays/`). The change-map area is `ddc`; alternatives: under `measurement`, or a
   `modules` area later (Q-12).
3. **dxva2 directly or wrap winddcutil?** Assumed dxva2 through ctypes (what the probe already does; no install).
4. **Linux: own I2C code or ddcutil?** Assumed: design only, decide when Linux starts (Q-14).
5. ~~The write whitelist.~~ Answered: yes to 10 and 12, yes to codes beyond the list (Decisions).
6. **Read back: exact match, or a tolerance?** Assumed exact: any other value raises.
7. **CLI shape.** Assumed `list`, `caps`, `get <vcp>...`, `scan`, `set <vcp> <value> [--allow ...]` with a dry
   run unless `--yes`; codes in hex (`6C`, `0x6C`), values in decimal, like the probe's `--ddc-steps`. `scan` has
   `--csv` / `--json` files; `get` and `caps` print text only. Wanted: `--json` on every command (for Q-13), a
   `restore` command, a `sweep` command?
8. **Restore all saved codes, or only the ones that changed?** Assumed all (as the probe does).
9. **The CI job.** Assumed a second workflow, `unit-tests`, running the tests on every push and pull request,
   next to `docs-check`. Keep it, or run the tests only locally? Still open: BevelTipDrip asked what a CI job is
   (2026-11-19) and the lead agent is explaining; the workflow is left as it is.
10. **Retries and timing.** Kept the probe's: writes 3 tries 0.3 s apart, 0.15 s settle; reads added 2 tries.
    Tune when the AW3225QF's behaviour is measured?
11. ~~Who switches the probe, and when.~~ Answered: it may happen on this branch (Decisions).
12. **The never list and `--allow`** (Safety rules 0 and 1), chosen by a drafting agent on 2026-11-19: are B0,
    CA, 76 and 78 right on the never list (beyond the 04 / 05 / 06 / 08 / 0A / 60 / D6 the lead agent's brief
    named)? Should `--allow` also need a second confirmation for manufacturer codes (E0-FF), or a display
    module's "ask first" class to be named on the command line?
13. **The probe's switch (D4): on a read back mismatch, stop the run or carry on as today?** And may the switch
    edit `run()` now, or wait until the `feature/nearblack-tint` probe work settles? ([How the probe would adopt
    it](#how-the-probe-would-adopt-it-d4-may-happen-on-this-branch-not-switched-yet).)

## Planned: T-DDC1 and T-DDC2, read-only checks for BevelTipDrip (not run)

Written 2026-11-19 by the drafting agent for BevelTipDrip to run when back. **Read only: no command here writes
to the monitor**, so no go is needed (START-HERE, Rules); nothing is changed in the OSD, HDR, profiles or the
driver. T-DDC1 (list, caps, a few gets) and T-DDC2 (the full scan) run in one sitting, about five minutes. Test
IDs: T-DDC1 and T-DDC2 are these reads; T-DDC3 is the first write (D3, needs a go).

**Before:** the AW3225QF on and awake, in the preset it is normally used in (True Black 400, Windows HDR on); no
measurement running; Dell Display Manager, Alienware Command Center, Twinkle Tray or any other DDC/CI tool closed
(two programs talking DDC/CI at once are untested). Note the OSD preset and whether HDR is on. Open a terminal in
`tools/` on `feature/ddc-module` (or wherever it has merged). Replace `<date>` with the day's date (`2026-11-20`).

```
python -m ddc list
python -m ddc caps --monitor AW3225QF
python -m ddc caps --raw --monitor AW3225QF
python -m ddc get 10 12 14 16 18 1A 6C 6E 70 DC E2 F2 C9 --monitor AW3225QF
python -m ddc scan --monitor AW3225QF --csv ../research/docs/data/ddc-t-ddc2-scan-<date>.csv --json ../research/docs/data/ddc-t-ddc2-scan-<date>.json
python -m ddc get 10 12 14 16 18 1A 6C 6E 70 --monitor AW3225QF
```

The first `get` is T-DDC1, the `scan` is T-DDC2, the last `get` checks nothing moved. The scan's JSON keeps the
raw capabilities string, so nothing needs to be copied by hand. If `list` shows the display under another name
(e.g. "Generic PnP Monitor"), use `--index 0` instead of `--monitor AW3225QF`, and add `--display aw3225qf` to get
the module's names. `get` prints `ERROR` for a code that does not answer and then exits 1: for E2, F2 or C9 that
is a result, not a failure.

**What to look for, and what each outcome would mean:**

| Look at | Expected [I] | If not |
|---|---|---|
| `list` | One line naming the AW3225QF | Nothing: the display is off or asleep (the 2026-11-19 symptom, [ddc-reference.md](ddc-reference.md#4-symptom---first-place-to-look)). Two lines: pick with `--index` |
| `caps`: model, MCCS version, codes | Model AW3225QF, MCCS 2.1, the codes of the AW3225QF in vdu_controls issue 84 ([module section](#aw3225qf-display-module-skeleton)) | Different codes: this unit's firmware differs from that one; the module's `in_caps` gets corrected from this run |
| T-DDC1 `get`: 16 / 18 / 1A and 6C / 6E / 70 | 100 of 100 and 50 of 255, as on 2026-11-18 | Other values: something (a reset, a preset change) changed them since; note it, change nothing |
| `get E2` | A number naming the preset (on the AW3423DWF: Desktop 39, DisplayHDR 58, Custom Color HDR 255) | An error: E2 is not readable here; otherwise this run gives the AW3225QF's number for True Black 400 |
| `get F2` | 65 with HDR on (as on the AW3423DWF) | Another value: F2 means something else here |
| scan summary: **"Hidden-setting candidates (reply, not in caps)"** | 6C 6E 70 (they answered on 2026-11-18 and the other unit's caps omit them) | Any other code there is a hidden-setting candidate: the list to study next, one code at a time (T-DDC3 onward, each write with a go). An empty list: this unit lists everything it answers |
| scan: "In caps but no reply" | 04 05 08 (write-only in MCCS) and maybe 02 / 52 | Many more: reads are failing (timing, link); rerun with `--interval 0.1` before reading anything into it |
| scan: notes "0 of 0: may be unsupported" | A few | Many E0-FF codes at 0 of 0: the monitor answers unsupported codes that way; they are not hidden settings |
| C9 (display firmware level) | Any value | Recorded only: a firmware update between runs could explain a changed near-black curve (Q-19) |
| The last `get` | The same numbers as T-DDC1 | Different: a read changed something, which MCCS does not allow; stop and report it |
| The screen during the scan | Nothing visible | The OSD flickers or vanishes (seen on an AW3423DWF under constant polling): note it; the scan's interval can grow |

**Optional, for the preset map (T-DDC2b):** change the OSD preset by hand to Custom Color HDR (a person changing
their own OSD; no agent does it), then run the scan again into `ddc-t-ddc2b-scan-customcolorhdr-<date>.csv` /
`.json`, and set the preset back. Comparing the two scans shows which codes follow the preset (E2, F0, 14, 10, 12
on the AW3423DWF) and gives the AW3225QF's E2 numbers.

**Writing it up:** a heading `## T-DDC2: ...` below (date, who ran it, commit, the two data files), the summary
lines quoted, the hidden candidates listed. Then (an agent can do this from the JSON): set `in_caps` and
`confirmed` in `tools/ddc/displays/aw3225qf.py` for every code read, and correct anything the run contradicts.

## Read-only check 2026-11-19: monitor not reachable

Run by the drafting agent (Claude), branch `feature/ddc-module` before its first code commit, from `tools/`:
`python -m ddc list`, then `python -m ddc get 10 12 14 16 18 1A 6C 6E 70 DC`. No test ID: nothing depends on it.

- `list`: "No monitors found for DDC/CI"; skipped `WinDisc`: "Windows error 0xC02625E5: The function failed
  because the specified GDI device did not have any monitors associated with it." `get`: the same error, exit 1.
- Windows' only display was `WinDisc`, its stand-in when no display is connected; `Get-PnpDevice -Class Monitor`
  listed both AW3225QF entries with status Unknown (not present). The display was off, asleep or disconnected
  [I]; it was not woken (no go to wake it, and none needed for groundwork).
- Found on the way: `ctypes.FormatError(0xC02625E5)` raises OverflowError; the backend now passes the signed code
  (`windows.error_text`) and `list` prints each skipped display with the reason
  ([ddc-reference.md](ddc-reference.md#5-things-not-to-retry)).

Second session, same day (Claude, for BevelTipDrip): `python -m ddc list` at the start of the session and again at
12:42 gave the same result (only `WinDisc`, 0xC02625E5); no other command ran against the real backend.

T-DDC1 (D2) and T-DDC2 (D2b) are still to run: [the plan for them](#planned-t-ddc1-and-t-ddc2-read-only-checks-for-beveltipdrip-not-run).

## T-DDC1 and T-DDC2 run with the monitor asleep (2026-11-19)

Run by Claude for BevelTipDrip, who said: "The monitor is actually on but asleep right now, so you should be able to
run the scan." Read only: nothing was written. Data: `data/ddc-t-ddc1-asleep-2026-11-19.txt`,
`data/ddc-t-ddc2-scan-asleep-2026-11-19.csv` / `.json` / `.txt`.

**DDC/CI answers while the monitor sleeps.** `list` found the monitor as "Alienware AW3225QF(DisplayPort HDR)"
on `\\.\DISPLAY17`. D6 power mode read 4 (standby). Earlier the same day, `list` found no monitor at all
(WinDisc only), so asleep is not the same state as that one.

**Some values follow the power state** (corrected by the awake run below). The T-DDC1 `get` read brightness 0 and
E2 0; the scan a minute later read brightness 35 and E2 4. Nothing was written in between. The awake run shows why:
in standby (D6 = 4) the monitor reports standby values for brightness, E2 and F2, and these can change while it
sleeps. Read D6 first, and trust state codes only when D6 = 1.

**Capabilities:** model AW3225QF, MCCS 2.1. The 42 codes listed are exactly those in vdu_controls issue 84 (another
person's AW3225QF). The `cmds` list includes `E3 F3` (table read and write).

**Scan:** 256 codes read, 61 replied. 19 replied without being listed in the capabilities (the hidden-setting
candidates): 03 06 0B 0C 0E 1E 20 30 3E 62 6C 6E 70 A8 B4 C0 DE E6 FA.
- **Real settings, confirmed hidden:** the black levels 6C / 6E / 70 (50 of 255, as on 2026-11-18).
- **Worth a closer look:**
  - 0B / 0C colour temperature (increment 0 of 24028; request 2 of 255);
  - C0 display usage time, 2359 (hours: panel use, relevant to OLED wear);
  - A8 (not in MCCS, 0 of 3);
  - B4 source timing mode (1 of 2);
  - E6 (manufacturer, 1 of 1);
  - FA (manufacturer, 0 of 65535).
- **Probably scaler defaults, not real settings on an OLED:**
  - 0E clock, 3E clock phase, 20 / 30 position, 1E auto setup (these are analogue-video controls);
  - 62 speaker volume (the monitor has no speakers);
  - 03 soft controls, 06 restore geometry, DE scratch pad (0 of 0).

**Values while asleep:** brightness 35, contrast 75, 14 colour preset 5 (6500 K), gains 100 / 100 / 100, black
levels 50 / 50 / 50, E2 4, F0 13, F2 0, F4 48 (max 1), F5 48 (max 1), C9 firmware level 16656 (0x4110), DF VCP
version 513 (0x0201). F2 reading 0 is the standby state (see the awake run).

## T-DDC2 run with the monitor awake (2026-11-19)

BevelTipDrip: "You're free to wake it up yourswlf and take the reading. It should already be in hdr400". The display
was woken with `display_power.py wake` (a mouse nudge). Read only: nothing was written.

- **First attempt** (`data/ddc-t-ddc2-scan-awake-fell-asleep-2026-11-19.*`): the monitor went back to standby
  partway through the scan. D6 read 1 when the scan reached it; E2 read 30, a value in transition; and the closing
  `get` showed D6 4, brightness 0, E2 4, F2 0. Windows turned the display off again because nothing held it on.
- **Held run** (`data/ddc-t-ddc2-scan-awake-held-2026-11-19.*`): `SetThreadExecutionState(ES_CONTINUOUS |
  ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED)` held the display on for the whole run; D6 stayed 1. The same 61 codes
  replied, and the same 19 hidden ones. Compared with the asleep scan, only these differ:

| VCP | Awake (True Black 400, Windows HDR on) | Asleep | Reading |
|---|---|---|---|
| D6 power mode | 1 (on) | 4 (off, soft) | MCCS standard |
| E2 preset report | 58 | 4 (0 at the first read) | 58 is also the AW3423DWF's "DisplayHDR" number: True Black 400 likely reports 58 [I] |
| F2 | 585 (0x0249) | 0 | Follows HDR or power; the AW3423DWF's "65" does not hold here [I] |
| F4 / F5 | 48, then 16 | 48 | See below |
| 60 input source | 3855 (0x0F0F) | 3858 (0x0F12) | Low byte 0F = DisplayPort 1; the asleep value differs |

**F4 and F5 changed with no write.** Both read 48 (0x30) at the first `get`, then 16 (0x10) in the scan and in the
closing `get`. Both values appear in F4's capability list: 10-17, 30-33, 40-47 and A0-A3. F4 looks like a
register selector, and something during the scan moved it. Two candidates:
- a read of another code (the scan reads every code in order);
- the monitor itself.

MCCS says reads must not change state, so this needs a closer look before anything reads or writes the
F4 family; the module (`displays/aw3225qf.py`) does not record this yet [I]. Brightness, contrast, gains and black
levels read the same awake and asleep.

Next steps 1 and 2 were run the same evening: see the next section.

## T-DDC2c: what moves F4, and `--keep-awake` (2026-11-19)

BevelTipDrip: "Yes, do one and two. Make sure the monitor goes back to sleep when you're done." Read only: nothing
was written to the monitor.

**T-DDC2c, F4 hunt** (`data/ddc-t-ddc2c-f4-hunt-2026-11-19.csv`; every read is logged with its time). The display was
woken and held on. D6 read 1 after 1.4 s. Then:
- A: F4 and F5 read five times each, back to back. Values: 48/48, 16/16, 16/16, 48/(read failed), (failed)/48.
- B: a capabilities request, then F4/F5. Both read 16.
- C: every other code, 00-FF, read in turn, with F4 and F5 read after each one. Both read 16 throughout, more than
  500 reads over 2 minutes, with no failed F4/F5 read.

**Conclusion:**
- Found: reading other codes does not move F4/F5, and neither does the capabilities request.
- Found: F4/F5 read 48 in standby, and on the first read or reads after a pause. Once read repeatedly, they hold 16.
- Found: settle time alone does not explain it. In the `--keep-awake` check below, F4 read 48 at 5.5 s after D6
  read 1, on its only read.
- Not known: whether reading F4 is what changes it.

Until this is understood, treat a single F4/F5 read as unreliable: read it several times, and use the value it
settles on.

**`--keep-awake` and `--sleep-after`, built.** `ddc/power.py`; options on every command; 13 new tests in
`tests/test_power.py`; 143 tests run, all OK (1 skipped).
- `--keep-awake` does four things, in order:
  1. wakes the display;
  2. holds it on (`SetThreadExecutionState` with `ES_CONTINUOUS`);
  3. polls D6 until it reads 1, for up to 20 s;
  4. waits a further 5 s.

  It releases the hold however the command ends. If D6 never reads 1, it warns and runs the command anyway.
- `--sleep-after` turns the display off at the end with SC_MONITORPOWER, as Windows' idle timer does.
- `scan` warns when D6 is not 1.
- None of this is a DDC/CI write.

**Two wake bugs found while building it:**
1. A continuous `SetThreadExecutionState` on its own does not wake a display that is already off. The first real
   try left the AW3225QF in standby for 20 s. A one-shot `ES_DISPLAY_REQUIRED` call does wake it; that is what
   `display_power.py wake` relies on.
2. Both `display_power.py` and the first `power.py` passed `SendInput` a 48-byte `INPUT` structure. Windows expects
   40 bytes on 64-bit, so the call fails (it returns 0) and the mouse nudge never happened. `power.py` now uses the
   correct size (`SendInput` returns 1). `display_power.py` belongs to feature/nearblack-tint and is not changed
   here.

**Run on the AW3225QF.** The display was put to sleep, and its standby (D6 4) confirmed. Then:
`python -m ddc get D6 10 E2 F2 F4 F5 --monitor AW3225QF --keep-awake --sleep-after`
- D6 read 1 after 0.5 s.
- Values read: 10 = 35, E2 = 58, F2 = 585, F4/F5 = 48.
- About 25 s later the monitor reported standby again (D6 4), the same delay as Windows' own display-off. It was
  left asleep.

**Next:** the preset comparison (T-DDC2b). It needs BevelTipDrip at the OSD. Run each scan with `--keep-awake`.
