# Conventions: how this project writes things down

Parent: [START-HERE.md](START-HERE.md). Read once in full; after that, when writing a doc, card or commit message.
The point of all of it: any person or agent can pick up any piece of work from the repo alone, reading little,
without losing what was learned or repeating what failed.

## Where things live

| What | Where |
|---|---|
| Entry point, rules, current state, doc index | `research/docs/START-HERE.md` (agents reach it from `AGENTS.md` / `CLAUDE.md` / `GEMINI.md`) |
| One card per change: what, invariants, interactions, evidence, pitfalls | `research/changes/<area>/<id>.md`; generated `INDEX.md`, `TESTS.md`; `LANDMINES.md` |
| One reference file per in-progress branch: owner, plan, conflicts, merge plan | `research/branches/<branch>.md`, on that branch ([README](../branches/README.md)) |
| Plans, studies, implementation notes, references, handoffs | `research/docs/*.md` (flat, no subfolders) |
| Measured logs and captures that docs quote | `research/docs/data/` (small, text); large data outside git ([data/README.md](data/README.md)) |
| Research and analysis tools | `research/tools/` (`changemap.py` among them) |
| Blank forms for every doc type | `research/templates/` |
| Procedures for agents | `.claude/skills/<name>/SKILL.md` |

## Doc types

The prefix says what a doc is; the rest of the name is the topic in lower-case-with-hyphens.

| Name | What it holds | Written when | Template |
|---|---|---|---|
| `START-HERE.md` | Reading order, rules, current state, switches, doc index | Kept current | |
| `plan-work-queue.md` | **The work queue**: every planned feature, fix, active issue, research question and chore, as `Q-<n>` rows under Now / Next / Later | An item appears or moves, in the same commit | |
| `plan-work-queue-done.md` | Finished and dropped queue rows, newest first | An item finishes | |
| `plan-roadmap.md` | Goals, stages, Progress table | A stage lands | |
| `plan-<topic>.md` | What to do and in what order: why, what is known, stages, tests, risks; test write-ups appended | Before work starts on a topic | [plan](../templates/plan.md) |
| `study-<topic>.md` | A question answered from code, data or outside sources: answer first, then evidence, sources, open questions | Research, often by a subagent | [study](../templates/study.md) |
| `design-<topic>.md` | A design draft for review before anything is built | A change too big to just propose | [plan](../templates/plan.md) |
| `impl-<topic>.md` | What was built: mechanism, switches, what stays as it was, builds and tests | Something is built | [impl](../templates/impl.md) |
| `notes-<topic>.md` | Read-only analysis or a map of something (a file, a protocol, a data format) | Reading something big | |
| `<area>-reference.md` | Directory, **invariants**, before-every-test checklist, symptom -> first place to look, **things not to retry** | The area's first code lands; updated the same day a rule, symptom or dead end is found | [reference](../templates/reference.md) |
| `handoff-YYYY-MM-DD-<topic>.md` | State, what landed, traps, **start here next time**, next steps | End of every session | [handoff](../templates/handoff.md) |
| `research/branches/<branch>.md` | A branch's owner, goal, planned files / areas / interfaces, state, **conflicts with other branches**, merge plan, log | The branch's first commit; kept current and pushed | [branch](../templates/branch.md) |
| `building-and-tools.md`, `repo-boundaries.md`, `pr-checklist.md` | Setup and build; branches and remotes; the PR bar | Kept current | |

Every doc starts with its title, then a status line and its parent:

```
# Plan: <what>

Status: planned 2026-11-18, nothing built. Parent: [START-HERE.md](START-HERE.md). Owner: Alex.
Cards: [core/fast-path](../changes/core/fast-path.md). Work queue: Q-4.
```

Size: a doc that passes ~400 lines gets split or summarized; new findings go at the end under a dated heading,
and the doc's opening lines (or its card) carry the current conclusion. One fact lives in one place: link to it
instead of copying it.

## Status words

Use exactly these for how far a change has got, in cards, docs, the work queue and commit messages. Loose wording
makes a regression hard to trace.

- **found**: a problem seen in the code or a log; nothing changed yet.
- **confirmed in code / in a log**: the problem is real (the file and line, or the log and line, named).
- **built `<commit>`** (or **fix built `<commit>`**): the change compiles and its tests pass; not run for real.
- **run**: it ran in the real setting; say where, which build, and what the log showed.
- **verified**: a person confirmed it works, **named and quoted**, with the log line or number that goes with it.

Never write "fixed" or "done" alone. Agents never write "verified" on their own word; a separate agent's review of a
card against the code is `checked: <date>`.

Work-queue states: `open` / `in progress` / `blocked` (on what) / the status words above; `done` (commit, who
verified) and `dropped` (why) only in the archive. Card statuses:
[research/changes/README.md](../changes/README.md#card-format).

## Work queue

[plan-work-queue.md](plan-work-queue.md) is the one place planned work lives: features, planned fixes, active
issues (bugs), research questions, chores. Not a plan doc, not an issue tracker, not a handoff; it points to them.

- **Every piece of work has a row before it starts**, with an ID `Q-<n>` (`changemap.py queue next`) that is never
  reused. A problem found while working on something else gets its row first, then work carries on.
- **The ID is how everything refers to the work:** branch files (`work_queue: Q-12`, required), cards
  (`queue: Q-12`), doc headers ("Work queue: Q-12"), commit messages ("(Q-12)"), PRs, handoffs, issues.
  `changemap.py queue Q-12` lists every reference.
- **The row moves with the work, in the same commit:** Now with owner and branch when started; the state cell at
  each status word; back to Next or Later when stopped; to
  [plan-work-queue-done.md](plan-work-queue-done.md) when done or dropped.
- **Rows stay short** (one line, at most 400 characters): what is known goes in the linked doc. This keeps the queue
  cheap enough to read at the start of every session.
- **`check` enforces it:** IDs unique and well formed, kinds and states from the lists, an owner on every Now row,
  done rows with a commit or PR, dropped rows with why, every `work_queue:` / `queue:` naming a real item, and on a
  branch, its item under Now with that branch named. `changemap.py queue` flags Now rows whose branch is missing or
  has no commits for a week.

## Evidence

- Numbers come with their source: a log in `data/` (`data/<file>:<line>`), a test ID, a commit.
- What a person said is quoted and attributed by name and date: `Alex (2026-11-18): "menus work at 4K"`.
- Decisions are attributed the same way, in the doc's Decisions section and in the work queue.
- Claims are tagged when it matters: **[V]** verified in code or data (say where), **[I]** inference. "Inferred from
  code, not tested" is a valid and useful thing to write.
- Say what was **not** tested and what could break. Rejected and reverted attempts are written down (a card with
  status `rejected` / `reverted`, and a line in the area's reference doc under "Things not to retry").
- Report the numbers that matter for the question (worst cases and percentiles next to averages for performance).

## Test IDs

Every run whose result anything depends on gets an ID: `T-<topic code><n>` (`T-AUTH3`, `T-SYNC12`). The plan or study
that owns the topic owns its numbering; before using a new ID, `changemap.py test <id>` must find nothing.
Write it up as a heading in that doc, so `changemap.py` can find it:

```
## T-SYNC3: retry on 409 (2026-11-18, run by Alex, build `abc1234`, log `data/sync-t-sync3-2026-11-18.log`)

What changed since the last run (one change), settings, what was seen, the numbers, what the person said, verdict.
```

## Writing style

- Plain words, short sentences, mechanism first. Tables for state, lists for steps.
- Absolute dates (`2026-11-18`), never "yesterday" or "last week". Times when order within a day matters.
- Paths as `path/file.ext:line`; commits as short hashes in backticks; switches in backticks.
- Write for someone who has read only START-HERE: name the file, the switch, the test, the card.

## Keep it true

| When | Update, the same day |
|---|---|
| Code changes | Its card (same commit), `changemap.py check` |
| A rule, symptom or dead end is found | The area's `<area>-reference.md`: one line and a pointer to the findings |
| Work is planned, or a bug or problem turns up | A queue row (`Q-<n>`) before work on it starts |
| A work item moves (started, state, stopped, finished) | Its queue row, in the same commit as the work |
| A stage lands or the state of an area changes | START-HERE's Current state, `plan-roadmap.md` Progress |
| A decision is made | The doc's Decisions section and the work queue, "(Name, date)" |
| A doc is created | START-HERE's Document index |
| A tool or procedure changes | Its skill, same commit |
| A trap is found that is not yet acted on | `research/changes/LANDMINES.md` |
| A branch is created | Its reference file, first commit, pushed |
| A branch's plan changes, or a new overlap with another branch appears | Its reference file (`files` / `areas` / `interfaces`, Conflicts table), pushed |
| A session ends | A handoff; the branch's reference file (State, Log), pushed |

## Commits

- One change per commit. Subject in the imperative, saying what changed; body says why, with the queue item
  (`Q-12`), test IDs, card IDs and status words (`built, not run`; `T-SYNC3 run: 0 conflicts in 2 h`).
- Code and its card in the same commit. Docs-only commits are fine and frequent.
- End with any attribution lines the agent's session requires.

## Line endings

The repository stores LF (`.gitattributes`: `* text=auto eol=lf`). Git converts on `git add`, so a tracked file
cannot flip to CRLF in a commit, whatever the editor wrote. Without this, CRLF and LF mix freely: a one-line
edit shows as a whole-file diff, and a real change can hide inside it.

- `*.cmd` / `*.bat` check out CRLF (cmd.exe needs it); `research/docs/data/**` is byte for byte; binary types
  are listed. A new file type that must keep its bytes gets a line in `.gitattributes` in the same commit.
- Once per clone: `git config blame.ignoreRevsFile .git-blame-ignore-revs`. A commit that changes only line
  endings or formatting goes in `.git-blame-ignore-revs` (full hash, with a comment).
- Normalizing a repo that had no attributes: commit `.gitattributes` together with `git add --renormalize .`
  and nothing else ("Normalize line endings"); check that `git diff --cached --ignore-cr-at-eol --stat` shows
  only `.gitattributes`; add the commit to `.git-blame-ignore-revs`. Branches made before it merge with
  `git merge -X renormalize <branch>`.
- **Untracked files are not covered** (local config, `.env`, settings files a program writes). Keep their line
  endings as found: edit with the agent's edit tool or byte-safe code (`open(p, 'rb')` / `'wb'`), never Git
  Bash `sed -i`, which strips CRs. Back the file up first and diff against the backup.
- After any scripted edit, `git diff --stat` must be proportional to the change; review with
  `git diff --ignore-cr-at-eol` so nothing hides in a whole-file flip. Count line endings with Python, not
  Git Bash `grep $'\r'`, which miscounts.

## Working together

- Claim a queue item before starting: check `changemap.py queue` and `branches` that nobody has it; create the
  branch, its reference file naming the item (`work_queue: Q-12`), and the row under Now with your name and the
  branch, in the branch's first commit; push. `branches` shows the claim to everyone at once; the row reaches
  `main` with the merge (or sooner through a `docs/` pull request).
- The queue is one file that many branches edit: on a merge conflict in it, keep both sides' rows.
- Large feature changes on `feature/<topic>` branches; every in-progress branch has a reference file; check the
  other active branches before every session on yours: [repo-boundaries.md](repo-boundaries.md#branches).
- One handoff per person per session; the topic in the name keeps same-day handoffs apart.
- `INDEX.md` and `TESTS.md` are generated: on a merge conflict, take either side and run `changemap.py index`.
- Merge pull requests with merge commits, so the commit hashes in cards stay valid
  ([repo-boundaries.md](repo-boundaries.md)).
- Each person's agent memory is private to them. Anything the team must share goes in the repo.
