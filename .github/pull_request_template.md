<!-- The bar: research/docs/pr-checklist.md. One change per PR. Status words: found / confirmed / built / run / verified. -->

## What

The problem or need, with evidence (`file:line`, log lines). Work-queue item / issue.

## How

The mechanism, enough to review without running it.

## How it fits in

| File | Change | Why |
|---|---|---|
| | | |

Switches and defaults. What callers see. What happens on unsupported setups.

## Proof

| Check | Result | Evidence |
|---|---|---|
| Build and tests | | |
| `changemap.py check` | 0 errors | |
| <scenario> (where, build) | | Name: "quote" / `research/docs/data/<file>` |

## Risks and limits

What could break, and what was **not** tested.

## Queue

Q-<n>: row moved to `plan-work-queue-done.md` (or back to Next with its state, if not finished here).

## Branch

Reference file: `research/branches/<branch>.md`. `changemap.py branches` run on <date>: overlaps with <branches, or
none>, handled as its "Conflicts with other branches" table says. `main` merged in.

## Cards and docs

Cards: `research/changes/<area>/<id>.md`. Docs updated: work queue, reference doc, START-HERE (if state changed).
