---
id: ddc-module
title: DDC/CI package tools/ddc: backends (dxva2, fake) behind one interface, and SafeDdc, the only writer (whitelist, 0..max check, read back, save and restore), with a CLI and unit tests
area: ddc
status: active
default: n/a
origin: ours (Windows backend ported from tools/nearblack_probe.py, feature/nearblack-tint @ 1703b92)
owner: BevelTipDrip
commits: e40689f
prs:
queue: Q-20
files: tools/ddc/__init__.py, tools/ddc/backend.py, tools/ddc/mccs.py, tools/ddc/scan.py, tools/ddc/tests/test_scan.py, tools/ddc/displays/__init__.py, tools/ddc/displays/aw3225qf.py, tools/ddc/tests/test_displays.py, tools/ddc/windows.py, tools/ddc/fake.py, tools/ddc/safety.py, tools/ddc/caps.py, tools/ddc/cli.py, tools/ddc/__main__.py, tools/ddc/tests/test_safety.py, tools/ddc/tests/test_cli.py, tools/ddc/tests/test_caps.py, tools/ddc/tests/test_backend.py, .github/workflows/unit-tests.yml
symbols: Backend, MonitorInfo, VcpReply, DdcError, parse_vcp_code, open_backend, Dxva2Backend, error_text, FakeBackend, FakeMonitor, SafeDdc, Preserve, DEFAULT_WRITE_WHITELIST, NEVER_WRITE, WriteRefused, ReadbackMismatch, RestoreFailed, parse_capabilities, main, MCCS_NAMES, WRITE_ONLY, mccs_name, scan, ScanRow, ScanResult, MIN_INTERVAL, write_csv, write_json, DisplayModule, Control, for_monitor, by_key
switches:
tests:
docs: plan-ddc-module.md#design, ddc-reference.md
depends_on:
conflicts_with:
supersedes:
related: nearblack-probe
checked:
---
## What it does

`tools/ddc/` lists monitors, reads any VCP code and writes a few, standard library only. A `Backend`
(`monitors`, `get_vcp`, `set_vcp`, `capabilities`, `close`) has two implementations: `Dxva2Backend` (Windows
dxva2 through ctypes, with argtypes, owned handles and Windows error text) and `FakeBackend` (in memory, with
failure injection and a write log). `SafeDdc` is the only caller of `set_vcp`: never list (`NEVER_WRITE` plus a
display module's), whitelist (default 10 / 12, 16 / 18 / 1A, 6C / 6E / 70), 0..max read from the monitor, read
back; `preserve(codes)` saves then restores on any exit; `restore(saved)` puts back values a caller saved.
`python -m ddc list | caps | get | scan | set` (from `tools/`); `set` is a dry run unless `--yes`, `--allow` widens
the whitelist for one call, and a failed or mismatched write is put back. `scan` reads every code 00-FF, at least
50 ms apart, against the capabilities string; codes that reply but are not listed are hidden-setting candidates.
Names: MCCS 2.2a (`mccs.py`). Per-model knowledge: `displays/` (AW3225QF skeleton: names, values, safety
classes; its never codes join the core's).

## Invariants

- Only `safety.py` calls `.set_vcp(` (test `OnlySafetyWrites` greps the package).
- `SafeDdc.set`: code not in `never` (checked first, on every call), in `whitelist`, `int` (not `bool`) in
  0..`maximum` from a read just before; a failed read refuses; after the write, a read back other than the value
  raises `ReadbackMismatch`.
- `NEVER_WRITE` holds at least 04 05 06 08 0A 60 D6; `SafeDdc(...)` raises `WriteRefused` when its whitelist names
  a never code; `preserve()` and `restore()` refuse never codes before reading or writing anything.
- `NEVER_WRITE` and `DEFAULT_WRITE_WHITELIST` do not overlap (test `NeverList`).
- `Preserve.__enter__` refuses unlisted codes and reads all codes before anything is written; `__exit__` restores
  every saved code (no range check: the values came from the monitor), keeps going after a failure, and raises
  `RestoreFailed` chained to the exception that ended the block.
- `cli._set` writes only with `--yes`; exit 2 = refused, nothing written. `--allow` codes go through the same
  `SafeDdc` (never list, range, read back); after a failed or mismatched write it calls `restore` with the value
  read just before.
- `scan` calls only `capabilities` and `get_vcp`, calls `wait(>= MIN_INTERVAL)` before every read, and opens its
  CSV / JSON with mode `"x"` (never overwrites).
- A display module only adds never codes (its `safe` set equals `DEFAULT_WRITE_WHITELIST`); `cli._set` applies
  the never codes of the description-matched module whatever `--display` says.
- `windows.py` touches no Windows API at import; `Dxva2Backend()` raises `DdcError` off Windows.
- `error_text` passes dxva2's 0xC026xxxx codes to `FormatError` signed (unsigned raises OverflowError).

## Interactions

- [nearblack-probe](../measurement/nearblack-probe.md) has its own copy of this DDC/CI code on
  `feature/nearblack-tint`; it is meant to switch to this package after that branch merges (plan, D4). Until then
  the two copies can drift. Since 2026-11-19 the default whitelist is wider (10, 12) than the probe's `DDC_VCPS`;
  the probe keeps its own six-code list and passes it as the whitelist when it switches.

## Evidence

- Unit tests built: 62 run, 0 failures, 1 skipped (the off-Windows check, skipped on Windows), Python 3.8.10 and
  3.14, Windows, 2026-11-19 (`python -m unittest discover -s tools/ddc/tests -t tools`).
- 2026-11-19 (second session): 10 / 12 writable, `--allow`, the never list, put-back after a failed `set`:
  built, 82 run, 0 failures, 1 skipped (Python 3.8.10, Windows). Fake backend only.
- 2026-11-19: `scan`, MCCS names: built, 105 run, 0 failures, 1 skipped (Python 3.8.10 and 3.14, Windows), fake
  backend only.
- 2026-11-19: display modules: built, 124 run, 0 failures, 1 skipped (3.8.10, 3.14), fake backend only.
- Not run against a monitor: on 2026-11-19 the AW3225QF was not reachable (`list` found only `WinDisc`,
  error 0xC02625E5). No write has been sent to any real display.

## History and pitfalls

- 2026-11-19: the first `list` with the display off said only "No monitors found". Decoding the error by hand
  showed `ctypes.FormatError` raises OverflowError on 0xC02625E5, which `_err` would have hit. Built: `error_text`
  (signed code) and `skipped` (each display without a physical monitor, and why), run on that same display-off
  case.
