# PR checklist: the bar for every pull request

Parent: [START-HERE.md](START-HERE.md). Branches and merging: [repo-boundaries.md](repo-boundaries.md). The PR
description follows `.github/pull_request_template.md`. Nothing is merged without a person's review and go.

## Scope

- [ ] One change per PR. Unrelated cleanups go in their own PR (or a new row in the work queue).
- [ ] Names its queue item (`Q-<n>`); the row is moved to `plan-work-queue-done.md` (or back with its state).
- [ ] A large feature change comes from a `feature/<topic>` branch ([repo-boundaries.md](repo-boundaries.md#branches)).
- [ ] The branch's reference file is current: `changemap.py branches` run today, every overlap in its "Conflicts with
      other branches" table with a plan, `main` merged in, status `merged` in the last commit.
- [ ] No secrets, build output, large data, or files of other projects without their licence.

## Code

- [ ] Reads like the surrounding code: naming, comment density (short, factual, says why), idiom of the file,
      existing helpers reused.
- [ ] Builds and passes tests on every platform the project supports.
- [ ] Behaviour changes sit behind the project's switch style with a safe default, where the project has switches.
- [ ] No warnings added. No dead code, no leftover debug output.
- [ ] Code taken from elsewhere: the commit message names the source (repo, commit, files) and its licence.

## Docs (same PR)

- [ ] Every code commit belongs to a card; cards written or updated; `changemap.py check` passes with 0 errors.
- [ ] New invariants, symptoms and dead ends in the area's reference doc.
- [ ] Work queue row, START-HERE state, roadmap Progress updated if they changed.

## Proof (in the PR description, with links)

- [ ] **What**: the problem or need, shown in the code (`file:line`) or a log.
- [ ] **How**: the mechanism, enough to review without running it.
- [ ] **How it fits**: every file touched and why; mechanisms used or changed; what callers see; defaults.
- [ ] Results: what was run, where, by whom, the numbers, with logs in `research/docs/data/`; "verified" only with a
      person's words.
- [ ] Risks and limits stated, including what was **not** tested.

## Commits

- [ ] Imperative subject, body says why; status words; test and card IDs. Each commit builds.
