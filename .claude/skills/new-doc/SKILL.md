---
name: new-doc
description: Create a research doc in this project's standard - a plan, design, study, implementation note, notes map or area reference - from research/templates/, named, headed and linked so it can be found. Use whenever work needs a written plan, a research question is answered, something is built, or an area gets its first code.
---

# New doc

Doc types, names and when each is written: `research/docs/conventions.md` ("Doc types").

1. **Check it does not exist**: look at START-HERE's Document index and `ls research/docs/`. An existing doc on the
   topic gets a new dated section at its end instead.
2. **Copy the template** from `research/templates/` to `research/docs/<prefix>-<topic>.md`:
   `plan.md` (for `plan-` and `design-`), `study.md`, `impl.md`, `reference.md` (`<area>-reference.md`).
   `notes-` docs have no template: title, status line ("Read-only analysis, <date>. Sources: ..."), then the map.
3. **Fix the links**: templates link `../docs/X`; in `research/docs/` that is just `X`. Remove the `<!-- -->`
   comments. Fill every `<...>`.
4. **Header**: title, `Status:` line with an absolute date and status words, `Parent:` link, owner, related
   cards and queue item (`Work queue: Q-<n>`).
5. **Link it**: a row in START-HERE's Document index; a link from the queue row's Details or parent plan; `docs:` in the
   related cards.
6. `python research/tools/changemap.py check`: 0 errors (it checks the links and anchors).

## Writing it

- Answer or conclusion first; then evidence. Tag claims **[V]** (verified, say where) or **[I]** (inference).
- Numbers with their source (`data/<file>:<line>`, test ID, commit). People named and quoted, with dates.
- A study can be delegated to a subagent: give it the question, the files to read and the template; then have a
  second agent check the answer against the code before anyone acts on it.
- Over ~400 lines: split it, or summarize at the top and in the card.
