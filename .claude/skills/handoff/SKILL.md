---
name: handoff
description: End a work session so the next person or agent can pick it up from the repo alone - update the work queue, cards, reference docs and START-HERE, then write a dated handoff. Use when a session ends, before a context is likely to run out, when switching topics, or when the person says "wrap up", "hand off" or "we're done for today".
---

# Handoff: close a session

Nothing learned in a session may live only in the conversation. Work through these in order; skip a step only when
nothing changed for it, and say which you skipped.

1. **Work queue** (`research/docs/plan-work-queue.md`): each item touched gets its state (status words only:
   found / confirmed / built `<commit>` / run / verified (Name)) and Owner; detail goes in the linked doc, not the
   row. Every problem found this session has a row (`changemap.py queue next`). Items you stop on go back to Next or
   Later; finished ones move to `plan-work-queue-done.md`. `changemap.py queue` to review.
2. **Cards**: every code commit of the session belongs to a card (`research/changes/`); evidence and pitfalls
   added. Run `python research/tools/changemap.py check`: 0 errors. Run `index` if it says so.
3. **Reference docs**: each new invariant, symptom or dead end from the session is one line in the area's
   `<area>-reference.md`, with a pointer to the findings. Rejected attempts go under "Things not to retry".
4. **Plan / study docs**: test write-ups under `## T-<ID>: ...` headings with date, who ran it, build, log path;
   decisions in the Decisions section as "(Name, YYYY-MM-DD)".
5. **START-HERE**: the Current state row of each area that changed, with the date and your name in its heading;
   a Document index row for each new doc. `plan-roadmap.md` Progress if a stage moved.
6. **Traps not yet acted on**: `research/changes/LANDMINES.md`.
7. **Your branch's reference file** (`research/branches/<branch>.md`, unless on `main` or a `docs/` branch):
   State (status words, date, name), a Log line, new overlaps from `changemap.py branches` in "Conflicts with other
   branches", `files` / `areas` / `interfaces` if the plan grew. Status `paused` if nobody will continue soon.
8. **The handoff**: copy `research/templates/handoff.md` to
   `research/docs/handoff-<YYYY-MM-DD>-<topic>.md` (today's date, absolute). Keep it short; link instead of
   repeating. "Start here next time" must name one concrete first action.
9. **Commit** the docs (one commit, "Handoff <date>: <topic>" with the attribution lines the session requires) and
   **push the branch**, so the reference file others' `changemap.py branches` reads is current. Pushing your own
   branch is free; never push to `main`.

Then tell the person, in a few lines: what landed (with status words), what is next, and anything waiting on them.

## Rules

- Never write "verified" unless a person said so in this session; quote them and name them.
- Never write "fixed" or "done" alone.
- Dates absolute, never "today" or "yesterday".
