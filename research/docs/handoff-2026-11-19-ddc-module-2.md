# Handoff 2026-11-19: DDC/CI package, second session (write list, scan, AW3225QF module)

Author: Claude (a sub-agent, for BevelTipDrip, who was at work). Parent: [START-HERE.md](START-HERE.md). Previous
handoff on this topic: [handoff-2026-11-19-ddc-module.md](handoff-2026-11-19-ddc-module.md). Branch:
`feature/ddc-module` ([reference file](../branches/feature/ddc-module.md)), pushed with this commit; it merges
back into `feature/nearblack-tint`, not `main`. Queue items: Q-20 (built; in progress).

## State

- BevelTipDrip's answers of 2026-11-19 (relayed by the lead agent) are recorded, quoted, in
  [plan-ddc-module.md, Decisions](plan-ddc-module.md#decisions): yes to 10 / 12 and to codes beyond the list; the
  probe may switch on this branch; the goal is control of every setting over DDC/CI, hidden ones included. Open
  question 2 (layout) and 9 (CI job) stay open.
- **Built** (unit tests on fake backends, 129 run, 0 failures, 1 skipped, Python 3.8.10 and 3.14): brightness and
  contrast writable by default, `--allow`, a never list nothing overrides; `scan` (read-only discovery of 00-FF)
  and MCCS 2.2a names; the AW3225QF display module (skeleton); the probe's `--ddc-steps` parser in the package.
- **Not run** on a monitor: the AW3225QF was unreachable at the start and the end of the session (`list` found only
  `WinDisc`, 0xC02625E5). **Nothing was written to any display**; no `set` ran against the real backend.
- **Not done:** the probe's switch to the package (open question 13: on a read back mismatch the probe carries on
  today, `SafeDdc` would stop; and nearblack-tint is editing `run()`). `tools/nearblack_probe.py` is untouched.
- Nothing is verified: no person has seen any of it yet.

## What landed

| Change | Commit | Card | State |
|---|---|---|---|
| Write list: 10 / 12 by default, `set --allow`, `NEVER_WRITE`, put back after a failed `set`; decisions recorded | `1a5b876` | ddc-module | built, not run |
| `scan` (Get only, >= 50 ms apart, table / CSV / JSON, hidden-setting candidates); `mccs.py` names | `328832c` | ddc-module | built, not run |
| `displays/aw3225qf.py` skeleton (names, values, preset locks, safety classes, sources); `--display`, `display` command | `43fc609` | ddc-module | built; 6 entries confirmed by the 2026-11-18 reads, the rest from public sources |
| `steps.parse_ddc_steps` with a golden table recorded from the probe | `b90f29d` | ddc-module | built; probe not switched |
| T-DDC1 / T-DDC2 plan (read only) | `73a4c52` | | planned, not run |
| Card, START-HERE, queue, branch file, this handoff | this commit | ddc-module | |

## Research findings (detail and sources: [plan, AW3225QF display module](plan-ddc-module.md#aw3225qf-display-module-skeleton))

- Another person's AW3225QF lists 6C / 6E / 70 **nowhere** in its capabilities (vdu_controls issue 84, checked),
  yet BevelTipDrip's answered them on 2026-11-18: likely the first hidden settings [I]; T-DDC2 will tell.
- On the AW3423DWF (closest model, medium confidence): E2 reports the OSD preset, F0 + 14 select presets, F2 shows
  HDR on/off, F4 is a command register (Dark Stabilizer), 10 / 12 are stored per preset.
- No public source ties any VCP code to firmware update, a service menu or a factory mode on Dell / Alienware; no
  VCP code is known to start the OLED panel refresh. Dell does not publish its manufacturer codes.

## Other branches

`feature/nearblack-tint` (BevelTipDrip): at `c4ed60e`, no new commits this session; merges cleanly with this
branch (`changemap.py branches`, 2026-11-19). It owns `tools/nearblack_probe.py`, which this session did not edit.
Both branches edit START-HERE, the queue and the change-map index files: keep both sides' rows when merging.

## Traps

1. Git Bash heredocs mangle backslashes in Python (`\r` became a newline in `cli.py` once): put Python edits in a
   file in the scratchpad, or use the Edit tool.
2. `python -m ddc --backend fake scan` fails: options go after the command (`python -m ddc scan --backend fake`).
3. The probe calls `windll` and `SetProcessDPIAware` at import: unit tests must not import it (the golden table in
   `test_steps.py` was recorded from it once instead).
4. A new test-ID heading needs `changemap.py index` before `check` passes.

## Start here next time

BevelTipDrip, with the AW3225QF on and awake: run the six read-only commands in
[plan-ddc-module.md, "Planned: T-DDC1 and T-DDC2"](plan-ddc-module.md#planned-t-ddc1-and-t-ddc2-read-only-checks-for-beveltipdrip-not-run)
from `tools/` (about five minutes, no go needed: nothing is written). Then an agent writes it up and fills
`in_caps` / `confirmed` in `tools/ddc/displays/aw3225qf.py` from the JSON.

## Next steps / pending

1. T-DDC1 / T-DDC2 (BevelTipDrip): read only.
2. Answers to open questions 2, 9, 12, 13 ([plan](plan-ddc-module.md#open-questions-for-beveltipdrip)).
3. After 13: switch the probe (D4) on this branch, behind the answer.
4. From the scan's hidden candidates: one code at a time, a dry run, then a write with a go (T-DDC3, fits Q-6).
5. A second agent checks card ddc-module against the code (`checked:` is empty).

## Open questions

- For BevelTipDrip: open questions 2 (layout; working assumption core + display module), 9 (CI job), 12 (the
  never list beyond the brief: B0, CA, 76, 78, and C8 / C9 / E1 in the module; extra confirmation for E0-FF?),
  13 (probe switch: stop or carry on after a read back mismatch; when to edit `run()`).
