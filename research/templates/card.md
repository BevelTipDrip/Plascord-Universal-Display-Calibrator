---
id: <short-unique-id>
title: <one line: what it does, mechanism first>
area: <area folder>
status: active
default: <on | off | n/a | mixed>
origin: ours
owner: <name>
commits: <short hashes, oldest first>
prs:
queue: <Q-n it came from>
files: <repo-relative paths it changes>
symbols: <functions / types / variables it adds or changes>
switches: <env vars / config keys / flags>
tests: <T-...>
docs: <file.md#anchor>
depends_on:
conflicts_with:
supersedes:
related:
checked:
---
## What it does

<Two to five lines, mechanism first: where it hooks in, what it changes, which switch turns it on or off.>

## Invariants

- <What must stay true for it to be correct, and what breaks if it does not. Each one checkable in the code.>

## Interactions

- <Other cards it needs, conflicts with, masks or is masked by, and why. "None known" is an answer.>

## Evidence

- <T-ID (date, where, build): the numbers, log `data/<file>`. Name: "quote". Or: "built, not run".>

## History and pitfalls

- <What went wrong, what was tried and dropped, which bug it caused or fixed. "None yet" is an answer.>
