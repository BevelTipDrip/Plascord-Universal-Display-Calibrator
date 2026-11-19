---
name: branch-work
description: Start, work on, and merge a git branch alongside other people's active branches - decide whether a change is a large feature (feature/<topic> branch), write the branch's reference file in research/branches/, check every other active branch's reference file for overlaps and conflicts with changemap.py branches, record a plan for each, and prepare the merge. Use before creating a branch, at the start of every session on a branch, before changing a shared interface, and before opening or merging a pull request.
---

# Working on a branch

Rules: `research/docs/repo-boundaries.md` ("Branches", "Working on a branch alongside others"). File format:
`research/branches/README.md`. Tool: `research/tools/changemap.py`.

## Starting a branch

1. **Size it.** Large (any of: more than one area; an interface, data format, schema, config key or switch others
   use; needs a plan doc; more than a session or about a day; more than one PR's worth) -> `feature/<topic>`, and a
   plan doc (skill `new-doc`). Small -> `fix/<topic>`. Docs only -> `docs/<topic>` (no reference file). Unsure ->
   large. Tell the person which and why.
2. **Look first:** `python research/tools/changemap.py queue` and `branches`. The work needs a queue item
   (`Q-<n>`); if it has none, add the row first (`changemap.py queue next` for the ID). If the item is already under
   Now, or a branch claims it or the same files, stop and tell the person (name the branch and its owner).
3. `git switch main && git pull`, then `git switch -c <branch>`.
4. `python research/tools/changemap.py new-branch <branch>`; fill every `<...>`: goal, `areas`, `files` (globs),
   `interfaces` others use that it will change, `work_queue` (the `Q-<n>`), `docs`. Fill "Conflicts with other branches" from step
   2 (write "none" with the date if there are none).
5. Move the queue row to **Now**: Owner, Branch, `in progress`.
6. `changemap.py check` (0 errors). Commit the file and the queue row as the branch's first commit; push the branch
   (`git push -u origin <branch>`; pushing your own branch needs no go). Now others' `branches` see it.

## Every session on the branch

1. `python research/tools/changemap.py branches`, then read the reference file of every branch it shows an
   overlap, shared area, changed interface or conflict for.
2. A new overlap -> a row in your file's "Conflicts with other branches": branch, overlap, plan, agreed with, date.
   A plan needs the other owner's agreement when it asks something of them (wait, split out a shared piece, change
   their side): ask the person you work with to arrange it, or note it as open.
3. Before changing an interface another branch lists or uses: stop and say so; agree it with that owner first.
4. If your plan grows (new files, areas, interfaces): update the front matter and "Planned changes", and push.
5. The queue row's State follows the work (found / confirmed / built `<commit>` / run / verified (Name)), in the
   same commit. New problems found on the way: new rows, not silent fixes.
6. Merge `main` in (`git merge main` after `git fetch`) at least daily; resolve conflicts here, not at the PR. Never
   rebase or force-push a pushed branch.

## Before the pull request and the merge

1. `branches` once more; every overlap has a plan that was carried out or still holds.
2. Merge `main` in; build and tests pass; `changemap.py check` 0 errors.
3. Reference file: State current, status `in review`; the PR description's Branch section filled.
4. The last commit before merging sets status `merged` (or `abandoned`, with why) and moves the queue row to
   `plan-work-queue-done.md` (done with the PR and who verified it; or dropped with why), or back to Next with its
   state if the item is not finished by this branch. Lasting knowledge goes in cards
   and reference docs; the branch file stays on `main` as the record.
5. Merging needs a person's review and go; deleting the branch afterwards needs its owner's go.
