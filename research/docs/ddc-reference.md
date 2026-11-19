# DDC reference: monitor control over DDC/CI

Read it **before changing `tools/ddc/` and before any DDC/CI write to a display.** **Keep it current:** a new rule,
symptom or dead end goes in here the same day, in one line with a pointer to the findings. Parent:
[START-HERE.md](START-HERE.md). Design and open questions: [plan-ddc-module.md](plan-ddc-module.md) (Q-20).

## 1. Directory

| What | Where |
|---|---|
| Backend interface, shared types, `open_backend` | `tools/ddc/backend.py` |
| MCCS 2.2a VCP names | `tools/ddc/mccs.py` |
| Read-only discovery (`scan`): every code against the capabilities string | `tools/ddc/scan.py` |
| Display modules: per-model names, values, preset locks, safety classes (AW3225QF skeleton) | `tools/ddc/displays/` ([plan](plan-ddc-module.md#aw3225qf-display-module-skeleton)) |
| Windows backend (dxva2 through ctypes) | `tools/ddc/windows.py` |
| In-memory backend for tests and `--backend fake` | `tools/ddc/fake.py` |
| The only writer: never list, whitelist, range check, read back, `preserve()`, `restore()` | `tools/ddc/safety.py` |
| Capabilities-string parser | `tools/ddc/caps.py` |
| CLI (`python -m ddc`, from `tools/`) | `tools/ddc/cli.py` |
| Unit tests | `tools/ddc/tests/` ([building-and-tools.md](building-and-tools.md#test)) |
| Card | [ddc-module](../changes/ddc/ddc-module.md) |
| The probe's own DDC/CI code (until it adopts this package) | `tools/nearblack_probe.py` on `feature/nearblack-tint` |

## 2. Invariants: must hold after every change

| # | Rule | What broke when it didn't | How to verify |
|---|---|---|---|
| 1 | Only `safety.py` calls a backend's `set_vcp` | (designed in; nothing broke yet) | `OnlySafetyWrites` test |
| 2 | Every write: code not on the never list, in the whitelist, an int in 0..max read from the monitor just before, read back equal | (designed in) | `tests/test_safety.py` |
| 2a | Never-list codes (`NEVER_WRITE`, a display module's `never`) are refused by every route: whitelist, `--allow`, `preserve`, `restore`. Reads stay allowed | (designed in, 2026-11-19) | `tests/test_safety.py`, class `NeverList`; `tests/test_cli.py` |
| 3 | `preserve()` reads everything before any write, and restores every saved code on any exit, reporting all failures | The probe's rule ([measurement-reference.md](measurement-reference.md), invariant 4) | `tests/test_safety.py`, class `Preserve` |
| 4 | `python -m ddc set` writes nothing without `--yes`; `--allow` only widens the whitelist for that call; a failed or mismatched write is put back | (designed in) | `tests/test_cli.py` |
| 4a | `scan` only reads (`capabilities`, `get_vcp`), waits at least 50 ms (`MIN_INTERVAL`) before every request after the first, and never overwrites a file | (designed in, 2026-11-19) | `tests/test_scan.py` (a backend whose `set_vcp` fails the test) |
| 4b | A display module only adds never codes: its `safe` codes are exactly the default whitelist, core never codes stay `never`, every unconfirmed entry says "not confirmed on this monitor"; `set` applies the never codes of the module the description matches even with `--display none` | (designed in, 2026-11-19) | `tests/test_displays.py` |
| 5 | Standard library only, Python 3.8+; importing any module (`windows.py` included) works on every platform | CI runs on Linux | `unit-tests` workflow; `py -3.8` locally |
| 6 | A backend owns the handles it opens and releases them in `close()` | The probe never destroys the other monitors' handles | `Dxva2Backend.close` |

## 3. Before every test

1. **A write to a real display needs a named person's go for that write** (START-HERE, Rules). Reads need none.
2. Read and note the current values of every code the test changes (`python -m ddc get ...`), so the OSD can put
   them back if a restore fails.
3. Writes go through `preserve()` (code) or a dry run of `set` first (CLI).
4. One change per test; say in advance what each outcome would mean.
5. Not while a measurement run on the same monitor is in progress (two DDC/CI talkers at once are untested).

## 4. Symptom -> first place to look

| Symptom | Most likely cause | Look at |
|---|---|---|
| `list`: "No monitors found", skipped `WinDisc` with error 0xC02625E5 | Windows has no connected display: the monitor is off, asleep or disconnected (seen 2026-11-19; PnP listed the AW3225QF as status Unknown) | Turn the display on; do not wake it for a test without a go |
| A read fails once, works on retry | DDC/CI is a slow I2C link; some monitors drop requests | `READ_TRIES` in `windows.py` |
| `ReadbackMismatch` after a write | The control is locked in this OSD preset, or the monitor quantizes values | The preset (AW3225QF: colour controls only in Custom Color HDR [I]); plan open question 6 |
| `RestoreFailed` | A write failed during restore | The values printed; set them in the OSD |
| `scan`: a code replies 0 of 0 | Some monitors answer unsupported codes that way | Treat it as unsupported until a write test says otherwise |
| `scan`: every code fails | Display off (first row), or another program is talking DDC/CI | `list` first; close other DDC/CI tools (Dell Display Manager, Twinkle Tray) |

## 5. Things not to retry

| What | Why it failed | Where written up |
|---|---|---|
| `ctypes.FormatError(code)` with dxva2's unsigned error codes (0xC026xxxx) | Raises OverflowError on Windows; pass the signed value (`windows.error_text`) | [plan-ddc-module.md](plan-ddc-module.md#read-only-check-2026-11-19-monitor-not-reachable) |
