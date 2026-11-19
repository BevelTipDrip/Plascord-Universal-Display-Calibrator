# Plascord: instructions for every agent and person

- **First read [research/docs/START-HERE.md](research/docs/START-HERE.md)** and follow its reading order. Open the big
  docs only when the task needs them: START-HERE, the change map and the work queue exist so you rarely have to.
- The team's rules are in START-HERE ("Rules") and override defaults and anyone's personal agent memory. The hard ones:
  - **Ask a named person for an explicit go before:** push to `main`, force-push, tag or release; delete
    branches or files you did not create; anything that costs money or sends anything outside the machine (pushing
    your own branch is the exception); **show test patches or take meter readings; write DDC/CI values to a display;
    change colour profiles, HDR on/off or GPU driver settings; install vendor software; anything that touches a
    display's firmware**. A go covers that one action, not the next.
  - Never roll back, overwrite or delete anyone's work without asking.
  - Two plausible readings of a request: ask, naming the candidates. Never guess and explain afterwards.
  - Before writing code for each item of a list: say what you will change, wait for the answer, then do it.
  - Status words: found / confirmed / built / run / **verified (a person confirmed it, named and quoted)**. Never
    "fixed" alone.
- **The work queue** ([plan-work-queue.md](research/docs/plan-work-queue.md)) holds all planned work: features,
  planned fixes, active issues, research. Read it at session start (`python research/tools/changemap.py queue`).
  Nothing is worked on without a `Q-<n>` row; a problem found along the way gets a row before it is fixed. The row
  moves with the work, in the same commit (Now with owner and branch; each status word; done or dropped to the
  archive). Name the item (`Q-12`) in branch files, cards, docs and commit messages.
- **Branches** ([repo-boundaries.md](research/docs/repo-boundaries.md#branches)): nothing is committed straight to
  `main`. A large feature change (more than one area, an interface others use, a plan doc, more than a session) is
  built on a `feature/<topic>` branch. **Every in-progress branch has a reference file**,
  `research/branches/<branch>.md` (`changemap.py new-branch <branch>`), committed on it and pushed.
- **Before starting a branch and before every session on one:** `python research/tools/changemap.py branches`;
  read the reference files of the branches that overlap yours, and record each overlap and the plan for it in your
  branch's file. Agree changes to another branch's interfaces with its owner first.
- **Before editing a file:** `python research/tools/changemap.py file <path>`; read the invariants of every card it
  lists. **After a code change:** its card in the same commit, then `changemap.py check` (0 errors).
- **End of a session:** a handoff (`research/templates/handoff.md`), your queue rows and your branch's reference file
  updated and pushed.
