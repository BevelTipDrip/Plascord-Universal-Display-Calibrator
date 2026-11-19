---
id: ddc-module
title: DDC/CI package tools/ddc: backends (dxva2, fake) behind one interface, and SafeDdc, the only writer (whitelist, 0..max check, read back, save and restore), with a CLI and unit tests
area: ddc
status: active
default: n/a
origin: ours (Windows backend ported from tools/nearblack_probe.py, feature/nearblack-tint @ 1703b92)
owner: BevelTipDrip
commits:
prs:
queue: Q-20
files: tools/ddc/__init__.py, tools/ddc/backend.py, tools/ddc/windows.py, tools/ddc/fake.py, tools/ddc/safety.py, tools/ddc/caps.py, tools/ddc/cli.py, tools/ddc/__main__.py, tools/ddc/tests/test_safety.py, tools/ddc/tests/test_cli.py, tools/ddc/tests/test_caps.py, tools/ddc/tests/test_backend.py, .github/workflows/unit-tests.yml
symbols: Backend, MonitorInfo, VcpReply, DdcError, parse_vcp_code, open_backend, Dxva2Backend, error_text, FakeBackend, FakeMonitor, SafeDdc, Preserve, DEFAULT_WRITE_WHITELIST, WriteRefused, ReadbackMismatch, RestoreFailed, parse_capabilities, main
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
failure injection and a write log). `SafeDdc` is the only caller of `set_vcp`: whitelist (default 16 / 18 / 1A,
6C / 6E / 70), 0..max read from the monitor, read back; `preserve(codes)` saves then restores on any exit.
`python -m ddc list | caps | get | set` (from `tools/`); `set` is a dry run unless `--yes`. Nothing imports it yet.

## Invariants

- Only `safety.py` calls `.set_vcp(` (test `OnlySafetyWrites` greps the package).
- `SafeDdc.set`: code in `whitelist`, `int` (not `bool`) in 0..`maximum` from a read just before; a failed read
  refuses; after the write, a read back other than the value raises `ReadbackMismatch`.
- `Preserve.__enter__` refuses unlisted codes and reads all codes before anything is written; `__exit__` restores
  every saved code (no range check: the values came from the monitor), keeps going after a failure, and raises
  `RestoreFailed` chained to the exception that ended the block.
- `cli._set` writes only with `--yes`; exit 2 = refused, nothing written.
- `windows.py` touches no Windows API at import; `Dxva2Backend()` raises `DdcError` off Windows.
- `error_text` passes dxva2's 0xC026xxxx codes to `FormatError` signed (unsigned raises OverflowError).

## Interactions

- [nearblack-probe](../measurement/nearblack-probe.md) has its own copy of this DDC/CI code on
  `feature/nearblack-tint`; it is meant to switch to this package after that branch merges (plan, D4). Until then
  the two copies can drift: the probe's `DDC_VCPS` and `DEFAULT_WRITE_WHITELIST` must list the same codes.

## Evidence

- Unit tests built: 62 run, 0 failures, 1 skipped (the off-Windows check, skipped on Windows), Python 3.8.10 and
  3.14, Windows, 2026-11-19 (`python -m unittest discover -s tools/ddc/tests -t tools`).
- Not run against a monitor: on 2026-11-19 the AW3225QF was not reachable (`list` found only `WinDisc`,
  error 0xC02625E5). No write has been sent to any real display.

## History and pitfalls

- 2026-11-19: the first `list` with the display off said only "No monitors found". Decoding the error by hand
  showed `ctypes.FormatError` raises OverflowError on 0xC02625E5, which `_err` would have hit. Built: `error_text`
  (signed code) and `skipped` (each display without a physical monitor, and why), run on that same display-off
  case.
