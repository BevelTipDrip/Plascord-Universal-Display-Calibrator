---
branch: <feature/topic>
owner: <name>
status: active
started: <YYYY-MM-DD>
base: <main @ commit>
goal: <one line: what this branch delivers>
areas: <change-map areas it touches>
files: <files or folders it will change; globs work: src/sync/*, src/api/client.py>
interfaces: <functions, APIs, schemas, data formats, config keys, switches that other code or people use and this branch changes>
work_queue: <Q-n: the queue item(s) this branch works on; required>
docs: <plan-topic.md>
cards: <card IDs, once written>
---
## Goal and scope

<What the branch delivers and why. In scope; out of scope. Created with `changemap.py new-branch`; lives at
research/branches/<branch>.md on this branch, pushed, so `changemap.py branches` shows it to everyone.>

## Planned changes

| What | Where | Changes something others use? |
|---|---|---|
| <change> | `<file or folder>` | <no / yes: what, and who uses it> |

## State

<Status words (found / confirmed / built `<commit>` / run / verified by Name). Last updated YYYY-MM-DD by Name.>

## Conflicts with other branches

Checked <YYYY-MM-DD> with `changemap.py branches`.

| Branch | Owner | Overlap (files, areas, interfaces) | Plan | Agreed with |
|---|---|---|---|---|
| <none> | | | | |

## Merge plan

<What must merge first and why; who resolves conflicts (default: the branch that merges second); migrations or
switch defaults at merge; how main is brought in (merge main into this branch; no rebase once pushed).>

## Log

- <YYYY-MM-DD> <Name>: started from <main @ commit>.
