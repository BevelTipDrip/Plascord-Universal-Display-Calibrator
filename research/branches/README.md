# Branch reference files

Every in-progress branch has a reference file here, at `research/branches/<branch name>.md`
(`feature/sync-retry` -> `research/branches/feature/sync-retry.md`): who owns it, what it delivers, which files,
areas and interfaces it changes, its state, how it will avoid or resolve conflicts with other branches, and its merge
plan. Exempt: `main` and the patterns in `branch_docs_exempt`
([changemap.config.json](../tools/changemap.config.json); default `docs/*`).
Rules for branches: [repo-boundaries.md](../docs/repo-boundaries.md#branches).

## Where the file lives, and how others see it

The file is committed **on its own branch** (its first commit) and the branch is pushed. Other people never need
it on `main` to read it: `changemap.py branches` fetches the remote and reads each active branch's file from
that branch.

```
python research/tools/changemap.py new-branch feature/sync-retry   # write the file from research/templates/branch.md
python research/tools/changemap.py branches                         # every other active branch, against yours
python research/tools/changemap.py branches --no-fetch              # the same, offline
```

For each other branch, `branches` prints its owner, status, goal, queue items and the interfaces it changes;
then, against your branch: files you both change, files it changes that you plan to change (and the reverse),
shared areas, and the files that would **conflict if merged now** (`git merge-tree`, git 2.38+), including
conflicts between your branch and `main` (another branch merged first). It also lists branches with no reference
file and branches with no commits beyond `main` (merged, or not started).

## When to update it

| When | What |
|---|---|
| The branch is created | Whole file from the template; first commit; push |
| Before each session on the branch | `changemap.py branches`; new overlaps into "Conflicts with other branches" with the date |
| The plan changes (new files, areas, interfaces) | Front matter `files` / `areas` / `interfaces`, "Planned changes"; push, so others' checks see it |
| End of a session | "State", "Log"; push (skill `handoff`) |
| Before opening the pull request | `branches` again; merge `main` in; status `in review` |
| The last commit before merging | Status `merged` (or `abandoned`, with why). The file then stays on `main` as the branch's record |

`changemap.py check` validates every file here (keys, status, areas, cards, docs, sections) and fails when the
current branch needs a file and has none. Lasting knowledge (invariants, evidence, pitfalls) belongs in cards and
reference docs, not only here.
