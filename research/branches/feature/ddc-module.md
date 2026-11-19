---
branch: feature/ddc-module
owner: BevelTipDrip
status: active
started: 2026-11-19
base: main @ 1b1783f
goal: A standalone DDC/CI package (tools/ddc/) that reads and writes a monitor's VCP codes safely (whitelist, range check, read back, save and restore), Windows dxva2 first, with a fake backend and tests; Linux later
areas: ddc, tooling
files: tools/ddc/*, tools/ddc/displays/*, research/docs/plan-ddc-module.md, research/docs/ddc-reference.md, research/changes/ddc/*, research/tools/changemap.config.json, research/docs/building-and-tools.md, research/docs/plan-work-queue.md, research/docs/START-HERE.md, .github/workflows/*, research/docs/handoff-2026-11-19-ddc-module.md, research/docs/handoff-2026-11-19-ddc-module-2.md
interfaces: new Python API and CLI in tools/ddc/ (nothing existing changes); a new change-map area "ddc" in changemap.config.json; a new CI workflow for unit tests
work_queue: Q-20
docs: plan-ddc-module.md
cards: ddc-module
---
## Goal and scope

Started 2026-11-19 by a Claude agent for BevelTipDrip, who asked (relayed by the lead agent): "launch a sub-agent to
start the work to build a ddc/ci module". BevelTipDrip was away, so this branch is groundwork for review: a plan doc
with every assumed decision listed as an open question, a small standard-library package, tests that need no
hardware. Plan: [plan-ddc-module.md](../../docs/plan-ddc-module.md).

In scope: backend interface, Windows dxva2 backend (ported from the probe's DDC/CI code), a fake in-memory backend,
a safety layer (write whitelist, range check against the reported max, read back after every write, save and
restore), a small CLI (`list`, `caps`, `get`, `set`), unit tests. Out of scope: the Linux backend (designed in the
plan, not built); changing `tools/nearblack_probe.py` (owned by feature/nearblack-tint; it adopts the package
later, agreed with its owner); any write to a real display.

## Planned changes

| What | Where | Changes something others use? |
|---|---|---|
| DDC/CI package: backends, safety layer, capabilities parser, CLI | `tools/ddc/` | no: new code; nothing imports it yet |
| Unit tests on the fake backend | `tools/ddc/tests/` | no |
| Plan doc, area reference doc | `research/docs/plan-ddc-module.md`, `research/docs/ddc-reference.md` | no |
| Change-map area `ddc` and its first card | `research/tools/changemap.config.json`, `research/changes/ddc/` | yes: a new area name others can file cards under |
| How to run and test it | `research/docs/building-and-tools.md` | no |
| CI job running the unit tests | `.github/workflows/` | yes: a new check on every push and pull request |
| Queue row Q-20, START-HERE index row | `research/docs/plan-work-queue.md`, `research/docs/START-HERE.md` | no |

## State

Built (unit tests on fake backends, 129 run): D1 `e40689f`; second session 2026-11-19: D1b write list (10 / 12,
`--allow`, never list) `1a5b876`, D2b `scan` and MCCS names `328832c`, D2c AW3225QF display module skeleton
`43fc609`, D4's parser `b90f29d` (probe not switched: plan open question 13), T-DDC1 / T-DDC2 plan `73a4c52`. Not
run on a monitor (unreachable at both tries on 2026-11-19); nothing written to any display. Waiting on
BevelTipDrip: T-DDC1 / T-DDC2 (read only) and open questions 2, 9, 12, 13. Last updated 2026-11-19 by Claude (for
BevelTipDrip). Handoff: [handoff-2026-11-19-ddc-module-2.md](../../docs/handoff-2026-11-19-ddc-module-2.md).

## Conflicts with other branches

Checked 2026-11-19 with `changemap.py branches` (twice: at the start and at the handoff; the trial merge at the
handoff showed conflicts in `START-HERE.md` and `plan-work-queue.md`, both rows added side by side). Checked again
2026-11-19 in the second session, at its start and its end: nearblack-tint at `c4ed60e`, merges cleanly (git
merge-tree); `tools/nearblack_probe.py` not edited here.

| Branch | Owner | Overlap (files, areas, interfaces) | Plan | Agreed with |
|---|---|---|---|---|
| feature/nearblack-tint | BevelTipDrip (with Claude) | Owns `tools/nearblack_probe.py`, which has its own DDC/CI code (`open_monitor`, `vcp_get`, `vcp_set`, `parse_ddc_steps`, `restore_vcps`, `DDC_VCPS`). Both branches edit `plan-work-queue.md`, `START-HERE.md`, `building-and-tools.md` and the change-map index files | This branch was merged into nearblack-tint (`4dd9353`) and fast-forwarded to it (`c4ed60e`); it merges back into nearblack-tint, not `main`. The probe may switch to `tools/ddc/` on this branch (D4); not done on 2026-11-19 (plan open question 13), so the probe is still not edited here. Doc conflicts: keep both sides' rows | BevelTipDrip, 2026-11-19 (relayed by the lead agent): "Should we merge the DDC branch into ours instead of into the main repo? Branching off of our working repo probably would have made more sense."; "Each branch doesn't have to be a seperate change entirely, it can be a set of changes, we just have to merge cleanly." |

## Merge plan

Into `feature/nearblack-tint` (BevelTipDrip, 2026-11-19, above), not `main`. Before merging: `changemap.py
branches`, merge nearblack-tint in here if it moved, tests and `check` pass, keep both sides' doc rows. Merging
needs BevelTipDrip's review and go.

## Log

- 2026-11-19 Claude (for BevelTipDrip): started from main @ 1b1783f.
- 2026-11-19 Claude: plan doc `808dd43`; package, tests, card, ddc area, CI workflow `e40689f`; read-only check
  on the real monitor not possible (only `WinDisc`). Handoff: handoff-2026-11-19-ddc-module.md.
- 2026-11-19 Claude (second session, for BevelTipDrip): answers recorded; D1b built (write list, `--allow`, never list) `1a5b876`; D2b built (`scan`, MCCS names) `328832c`; D2c built (AW3225QF display module) `43fc609`; D4 part built (`steps.parse_ddc_steps`), probe not switched (open question 13).
- 2026-11-19 Claude: T-DDC1 / T-DDC2 plan `73a4c52`; monitor still unreachable at the end; handoff-2026-11-19-ddc-module-2.md.
