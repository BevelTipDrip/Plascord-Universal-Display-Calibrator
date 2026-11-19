# Handoff 2026-11-19: DDC/CI package groundwork

Author: Claude (a sub-agent, for BevelTipDrip, who was away). Parent: [START-HERE.md](START-HERE.md). Previous
handoff on this topic: none. Branch: `feature/ddc-module`
([reference file](../branches/feature/ddc-module.md)), pushed with this commit. Queue items: Q-20 (built
`e40689f`).

## State

- BevelTipDrip asked (relayed by the lead agent, 2026-11-19): "launch a sub-agent to start the work to build a
  ddc/ci module". Nobody could answer questions, so every design decision was assumed and written down as an open
  question in [plan-ddc-module.md](plan-ddc-module.md#open-questions-for-beveltipdrip). None is decided.
- `tools/ddc/` is **built**: unit tests pass on the fake backend. It is **not run** on a monitor, and **nothing was
  written to any display**. Nothing imports it yet; `tools/nearblack_probe.py` is untouched.
- The read-only check on the AW3225QF could not run: Windows had no connected display (only `WinDisc`,
  error 0xC02625E5; PnP listed the AW3225QF as status Unknown). The display was not woken.

## What landed

| Change | Commit | Card | State |
|---|---|---|---|
| Branch reference file, Q-20 under Now | `511b365` | | |
| Plan doc with open questions | `808dd43` | | planned |
| Package: dxva2 and fake backends, `SafeDdc`, caps parser, CLI, tests; `ddc` area; `unit-tests` workflow; ddc-reference.md | `e40689f` | ddc-module | built: `python -m unittest discover -s tools/ddc/tests -t tools`, 62 run, 0 failed, 1 skipped (by design on Windows), Python 3.8.10 / 3.10 / 3.14. Not run on a monitor |
| Card commit, Q-20 state | `52f7503` | ddc-module | |

The `unit-tests` workflow has not run yet on GitHub when this was written: check its first result on the pushed
branch.

## Other branches

`feature/nearblack-tint` (BevelTipDrip): it owns `tools/nearblack_probe.py` and its DDC/CI code, which this branch
ported but did not edit. Both edit `START-HERE.md`, `plan-work-queue.md` and `building-and-tools.md`; a trial merge
shows conflicts in the first two (rows added side by side: keep both). Plan in the reference file; not yet
confirmed by BevelTipDrip.

## Traps

1. `ctypes.FormatError` raises OverflowError on dxva2's 0xC026xxxx error codes; pass them signed
   (`ddc/windows.py`, `error_text`). [ddc-reference.md](ddc-reference.md#5-things-not-to-retry).
2. `ctypes.wintypes.BYTE` is signed; the VCP code arguments use `c_ubyte`.
3. Run `python -m ddc` from `tools/` (it is a package there), and the tests from the repo root with `-t tools`.

## Start here next time

BevelTipDrip: read [plan-ddc-module.md](plan-ddc-module.md#open-questions-for-beveltipdrip) and answer the 11 open
questions (record each under Decisions with name and date). Then, with the display on, run the read-only check
T-DDC1 from `tools/`: `python -m ddc list`, `python -m ddc caps`, `python -m ddc get 10 12 14 16 18 1A 6C 6E 70 DC`,
and write it up in the plan.

## Next steps / pending

1. Answers to the open questions; rename or move the package if question 1 or 2 says so (BevelTipDrip).
2. T-DDC1, read-only (no go needed): stage D2.
3. T-DDC2, one write restored by `preserve()`: needs BevelTipDrip's go for that write (stage D3; fits Q-6).
4. After `feature/nearblack-tint` merges: the probe uses the package (stage D4), as its own queue row, agreed with
   the probe's owner.
5. Have a second agent check card ddc-module against the code (`checked:` is empty).

## Open questions

- The 11 questions in [plan-ddc-module.md](plan-ddc-module.md#open-questions-for-beveltipdrip), for BevelTipDrip.
- Is the overlap plan with `feature/nearblack-tint` (no probe edits here; adoption later) acceptable? For
  BevelTipDrip.
