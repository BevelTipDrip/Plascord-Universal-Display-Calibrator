# <Area> reference: <what the area covers>

Read it **before changing <area> and before every test of it.** **Keep it current:** a new rule, symptom or dead
end goes in here the same day, in one line with a pointer to the findings. Parent:
[START-HERE.md](../docs/START-HERE.md).

<!-- Copy to research/docs/<area>-reference.md when the area's first code lands; add it to START-HERE's
     Document index and reading order item 6. -->

## 1. Directory

| What | Where |
|---|---|
| <piece> | `<path>` |

## 2. Invariants: must hold after every change

| # | Rule | What broke when it didn't | How to verify |
|---|---|---|---|
| 1 | <rule> | <the bug, card, date> | <check, test, review> |

## 3. Before every test

1. A person has said go for this run (if the run needs one).
2. One change since the last run, behind a switch; say which.
3. Settings backed up and diffed against the backup.
4. The build is new (timestamp, a new log line).
5. Same input, settings and machine as the baseline.
6. Say in advance what each outcome would mean, and what the person should look at.

## 4. Symptom -> first place to look

| Symptom | Most likely cause | Look at |
|---|---|---|
| <what is seen> | <cause> | `<file:line>`, card <id> |

## 5. Things not to retry

| What | Why it failed | Where written up |
|---|---|---|
| (none yet) | | |
