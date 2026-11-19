---
id: display-power
title: Wake the display with a 1-pixel mouse nudge, or turn it off with SC_MONITORPOWER, for unattended runs
area: measurement
status: active
default: n/a
origin: ours
owner: BevelTipDrip
commits: c491027
prs:
queue:
files: tools/display_power.py
symbols: nudge, MOUSEINPUT, INPUT
switches:
tests:
docs: measurement-reference.md
depends_on:
conflicts_with:
supersedes:
related: nearblack-probe
checked:
---
## What it does

`python tools/display_power.py wake` sends a relative mouse move of +1 then -1 pixel (`SendInput`) and resets the
display idle timer (`ES_DISPLAY_REQUIRED`). `off` broadcasts `WM_SYSCOMMAND` / `SC_MONITORPOWER` (2), so the
display sleeps after an unattended run.

## Invariants

- The nudge returns the cursor to where it was (+1 then -1).
- It only requests power states; it never changes display settings.

## Interactions

- Used around [nearblack-probe](nearblack-probe.md) runs when nobody is at the machine; the probe keeps the display
  awake once it runs.

## Evidence

- Run 2026-11-18 around T-NB9 (unattended): the display woke for the run and was turned off after it.

## History and pitfalls

- None yet.
