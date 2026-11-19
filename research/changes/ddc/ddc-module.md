---
id: ddc-module
title: DDC/CI package tools/ddc: backends (dxva2, fake), SafeDdc the only writer (never list, whitelist, 0..max, read back, restore), read-only scan, MCCS names, display modules (AW3225QF skeleton), CLI and unit tests
area: ddc
status: active
default: n/a
origin: ours (Windows backend and --ddc-steps parser ported from tools/nearblack_probe.py, feature/nearblack-tint @ 1703b92)
owner: BevelTipDrip
commits: e40689f, 1a5b876, 328832c, 43fc609, b90f29d
prs:
queue: Q-20
files: tools/ddc/__init__.py, tools/ddc/backend.py, tools/ddc/mccs.py, tools/ddc/scan.py, tools/ddc/tests/test_scan.py, tools/ddc/displays/__init__.py, tools/ddc/displays/aw3225qf.py, tools/ddc/tests/test_displays.py, tools/ddc/steps.py, tools/ddc/tests/test_steps.py, tools/ddc/windows.py, tools/ddc/fake.py, tools/ddc/safety.py, tools/ddc/caps.py, tools/ddc/cli.py, tools/ddc/__main__.py, tools/ddc/tests/test_safety.py, tools/ddc/tests/test_cli.py, tools/ddc/tests/test_caps.py, tools/ddc/tests/test_backend.py, tools/ddc/power.py, tools/ddc/tests/test_power.py, .github/workflows/unit-tests.yml
symbols: Backend, MonitorInfo, VcpReply, DdcError, parse_vcp_code, open_backend, Dxva2Backend, error_text, FakeBackend, FakeMonitor, SafeDdc, Preserve, DEFAULT_WRITE_WHITELIST, NEVER_WRITE, WriteRefused, ReadbackMismatch, RestoreFailed, parse_capabilities, main, MCCS_NAMES, WRITE_ONLY, mccs_name, scan, ScanRow, ScanResult, MIN_INTERVAL, write_csv, write_json, DisplayModule, Control, for_monitor, by_key, parse_ddc_steps, PROBE_VCPS, Power, WindowsPower, FakePower, platform_power, wait_awake, SETTLE_S
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

`tools/ddc/` lists monitors, reads any VCP code and writes some, standard library only. `Backend` (`monitors`,
`get_vcp`, `set_vcp`, `capabilities`, `wait`, `close`): `Dxva2Backend` (Windows dxva2 through ctypes) and
`FakeBackend` (in memory; failure injection; logs of writes, reads, waits). `SafeDdc` is the only caller of
`set_vcp`: never list (`NEVER_WRITE` plus a display module's), whitelist (default 10 12 16 18 1A 6C 6E 70), 0..max
read just before, read back; `preserve()` / `restore()` put values back. `scan` reads every code 00-FF (Get only,
>= 50 ms apart) against the capabilities string; replies not listed are hidden-setting candidates. `mccs.py`: MCCS
2.2a names. `displays/`: per-model knowledge (AW3225QF skeleton: names, values, preset locks, safety classes).
`steps.py`: the probe's `--ddc-steps` parser. CLI `python -m ddc list | caps | get | scan | display | set` (from
`tools/`); `set` is a dry run unless `--yes`; `--allow` widens the whitelist for one call.

## Invariants

- Only `safety.py` calls `.set_vcp(` (test `OnlySafetyWrites` greps the package, `displays/` included).
- `SafeDdc.set`: code not in `never` (checked first, every call), in `whitelist`, `int` (not `bool`) in 0..max
  from a read just before; a failed read refuses; a read back other than the value raises `ReadbackMismatch`.
- `NEVER_WRITE` holds at least 04 05 06 08 0A 60 D6 and does not overlap `DEFAULT_WRITE_WHITELIST`; `SafeDdc(...)`
  raises `WriteRefused` when its whitelist names a never code; `preserve()` / `restore()` refuse never and
  unlisted codes before reading or writing anything.
- `Preserve.__exit__` restores every saved code (no range check), keeps going after a failure, and raises
  `RestoreFailed` chained to the exception that ended the block.
- `cli._set` writes only with `--yes` (exit 2 = refused, nothing written); after a failed or mismatched write it
  calls `restore` with the value read just before; it applies the never codes of the description-matched display
  module whatever `--display` says.
- `scan` calls only `capabilities` and `get_vcp`, `wait(>= MIN_INTERVAL)` before every read, and opens its CSV /
  JSON with mode `"x"` (never overwrites).
- A display module only adds never codes: its `safe` set equals `DEFAULT_WRITE_WHITELIST`; every entry without
  `confirmed` says "not confirmed on this monitor" in its source.
- `steps.parse_ddc_steps` returns and raises exactly what the probe's does (`test_steps.py` golden table).
- `--keep-awake` / `--sleep-after` (`power.py`) never write a VCP code: waking is a one-shot `ES_DISPLAY_REQUIRED`
  plus a `SendInput` mouse nudge (`INPUT` exactly `sizeof(INPUT)`, no padding), holding is `SetThreadExecutionState`,
  sleeping is SC_MONITORPOWER; `main` releases the hold on every exit; `wait_awake` only reads D6.
- `windows.py` touches no Windows API at import; `error_text` passes 0xC026xxxx codes to `FormatError` signed.

## Interactions

- [nearblack-probe](../measurement/nearblack-probe.md) still has its own DDC/CI code (`DDC_VCPS`, the same six
  codes as `steps.PROBE_VCPS`); switching it is plan D4, open question 13 (read back mismatch: stop or carry on).

## Evidence

- Unit tests built (fake backends only): 62 run (`e40689f`); 129 run, 0 failures, 1 skipped (off-Windows check),
  Python 3.8.10 and 3.14, Windows, 2026-11-19 (`cd tools && python -m unittest discover -s ddc/tests -t .`).
- Run on the AW3225QF, read only, 2026-11-19: T-DDC1, T-DDC2 (asleep, awake, held), T-DDC2c (F4 hunt), and a
  `--keep-awake --sleep-after` check (woke in 0.5 s, back in standby ~25 s after). No write has been sent to any
  real display. Earlier the same day it was unreachable (`list` found only `WinDisc`, error 0xC02625E5).
- 143 unit tests run, 0 failures, 1 skipped, with `power.py` (Python 3.8, Windows, 2026-11-19).
- AW3225QF module entries: 16 18 1A 6C 6E 70 confirmed by the 2026-11-18 reads; the rest from public sources
  (plan, "AW3225QF display module"), not confirmed on this monitor.

## History and pitfalls

- 2026-11-19: `ctypes.FormatError` raises OverflowError on 0xC02625E5; built `error_text` (signed code) and
  `skipped` (each display without a physical monitor, and why).
- 2026-11-19: `--display none` would have lifted a module's never codes for `set`; `_never` now always adds the
  description-matched module's.
- 2026-11-19: `--keep-awake` first left the display in standby: a continuous `SetThreadExecutionState` does not
  wake a display that is off, and the copied 48-byte `INPUT` made `SendInput` fail (also in `display_power.py`).
- Options go after the command (`python -m ddc scan --backend fake`), not before it.
