---
name: change-card
description: Write or update the change-map card for a code change (research/changes/<area>/<id>.md) and keep the map true with changemap.py - before editing a file (read its cards' invariants), after committing code, when a change is rejected or reverted, or when checking a card against the code.
---

# Change cards

Format and statuses: `research/changes/README.md` ("Card format"). Tool: `research/tools/changemap.py`.

## Before editing a file

```
python research/tools/changemap.py file <path>
```

Read the invariants of every card it lists. If your change would break one, stop and tell the person before
writing code. If it lists commits without a card, mention it.

## After a code change

1. Find the card: `changemap.py commit <hash>` / `find <text>` / `file <path>`. A fix to an existing change updates
   that card. A new behaviour gets a new card: `changemap.py new <area> <id>` (copies `research/templates/card.md`).
2. Fill or update it: front matter (`commits` oldest first, `files`, `symbols`, `switches`, `tests`, `docs`,
   `queue`: the `Q-<n>` it came from), then the
   five sections. Mechanism first; invariants each checkable in the code; evidence with status words, test IDs and
   quotes; under 60 lines (detail goes in the linked docs).
3. Same commit as the code when possible; otherwise the next commit.
4. `changemap.py check` until 0 errors; `changemap.py index` if INDEX/TESTS are out of date.

## Rejected or reverted

Keep the card. Set `status: rejected` (code may stay behind an off switch, or was never built: say so) or
`reverted`, and write why under History and pitfalls. Add a line to the area reference doc's "Things not to retry".

## Checking a card (for a second agent or reviewer)

Compare each front-matter item and each invariant with the code (read the files, `git show` the commits) and the
docs it links. Fix what is wrong, mark guesses `[inferred from code, not tested]`, set `checked: <YYYY-MM-DD>`.
Traps you find but do not fix go to `research/changes/LANDMINES.md`. Never set or write "verified": that is a
person's confirmation.
