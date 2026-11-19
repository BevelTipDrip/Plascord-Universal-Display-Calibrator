# Plan: a DDC/CI package that reads and writes a monitor's VCP codes safely, Windows first, Linux later

Status: planned 2026-11-19; D1 built `e40689f`, not run on a monitor; groundwork for BevelTipDrip to review (every assumed decision is under
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

   A display module can add its own never codes (the AW3225QF's: below, once written). Every row the drafting
   agent added is for BevelTipDrip to review (open question 12).
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

### How the probe would adopt it (later, agreed with feature/nearblack-tint's owner)

After `feature/nearblack-tint` merges, a separate change (its own queue row) replaces the probe's `open_monitor`,
`vcp_get`, `vcp_set`, `restore_vcps` and `DDC_VCPS` with:

```
from ddc import open_backend, SafeDdc
with open_backend() as be:
    ddc = SafeDdc(be, be.find(args.monitor))
    with ddc.preserve(vcps):          # restore on any exit, as the probe's finally: does today
        for step in steps:
            for c, v in step.items():
                ddc.set(c, v)          # range check and read back on every write
            sweep(...)
```

The probe's restore before the end reference (so the drift check compares like with like) becomes the end of the
`with` block. `parse_ddc_steps` can move to the package unchanged. The probe's CSV tag (`ddc_6C=50_...`) keeps
coming from read backs. Not done on this branch: the probe belongs to `feature/nearblack-tint`.

## Stages

| Stage | What | Switch | Test | State |
|---|---|---|---|---|
| D1 | Package, fake backend, safety layer, CLI, unit tests | none (new code, nothing imports it) | unit tests | built `e40689f` (62 tests pass, 2026-11-19) |
| D1b | Brightness 10 and contrast 12 writable by default; `--allow`; the never list; old value put back after a failed `set` | none | unit tests | built (this branch, 2026-11-19; commit in the card) |
| D2 | Read-only check on the AW3225QF: `list`, `caps`, `get` | | T-DDC1 | not started (monitor not reachable 2026-11-19, twice, below) |
| D2b | Read-only discovery: `scan` of 00-FF, MCCS names | none | unit tests; T-DDC2 | built (unit tests, 2026-11-19); T-DDC2 not run |
| D3 | One write on the AW3225QF, restored, with a go | | T-DDC3 | not started (needs a go) |
| D4 | The probe uses the package (on this branch: BevelTipDrip, 2026-11-19, Decisions) | | a probe `--ddc-steps` run | not started |
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
   module for the AW3225QF (which codes do what, which presets lock them, safety classes). The change-map area is
   `ddc`; alternatives: under `measurement`, or a `modules` area later (Q-12).
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

T-DDC1 (D2) is still to run: with the display on, `list`, `caps`, `get` of the same codes; compare 16 / 18 / 1A
and 6C / 6E / 70 with the 2026-11-18 reads (100 of 100, 50 of 255).
