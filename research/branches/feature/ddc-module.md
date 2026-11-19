---
branch: feature/ddc-module
owner: BevelTipDrip
status: active
started: 2026-11-19
base: main @ 1b1783f
goal: A standalone DDC/CI package (tools/ddc/) that reads and writes a monitor's VCP codes safely (whitelist, range check, read back, save and restore), Windows dxva2 first, with a fake backend and tests; Linux later
areas: ddc, tooling
files: tools/ddc/*, research/docs/plan-ddc-module.md, research/docs/ddc-reference.md, research/changes/ddc/*, research/tools/changemap.config.json, research/docs/building-and-tools.md, research/docs/plan-work-queue.md, research/docs/START-HERE.md, .github/workflows/*, research/docs/handoff-2026-11-19-ddc-module.md
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

Branch and queue row created. Last updated 2026-11-19 by Claude (for BevelTipDrip).

## Conflicts with other branches

Checked 2026-11-19 with `changemap.py branches`.

| Branch | Owner | Overlap (files, areas, interfaces) | Plan | Agreed with |
|---|---|---|---|---|
| feature/nearblack-tint | BevelTipDrip (with Claude) | Owns `tools/nearblack_probe.py`, which has its own DDC/CI code (`open_monitor`, `vcp_get`, `vcp_set`, `parse_ddc_steps`, `restore_vcps`, `DDC_VCPS`). This branch ports that code into `tools/ddc/` and does not edit the probe. Both branches also edit `plan-work-queue.md`, `START-HERE.md` and `building-and-tools.md` | The probe is not touched here. After nearblack-tint merges, a later step (its own queue row) switches the probe to `tools/ddc/`, agreed with the probe's owner. Doc conflicts: whoever merges second resolves; in the queue, keep both sides' rows | Open: the lead agent set this plan on 2026-11-19; BevelTipDrip (owner of both) to confirm |

## Merge plan

No order is required: this branch adds new files and touches no code of nearblack-tint. Merge `main` in before
the pull request (no rebase once pushed); whoever merges second resolves the shared doc conflicts (queue rows: keep
both sides). Merging needs BevelTipDrip's review and go.

## Log

- 2026-11-19 Claude (for BevelTipDrip): started from main @ 1b1783f.
