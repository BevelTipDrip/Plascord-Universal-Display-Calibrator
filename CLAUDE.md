@AGENTS.md

## Claude Code

- Procedures are skills in `.claude/skills/`, used by name: `branch-work` (starting, working on and merging a
  branch, alongside other people's branches), `handoff` (end of a session), `change-card` (after a code change),
  `new-doc` (a plan, study, implementation or reference doc). Update a skill in the same commit as the tool or rule
  it describes.
- Your memory is per person and per machine; the team's rules and state live in the repo. Save to memory only this
  person's own preferences. When a memory and the repo disagree, the repo wins: tell the person.
- After a context compaction: give a short status (task, next step) and ask what is missing before searching the
  code or logs to rebuild it.
