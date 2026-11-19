# Work queue: what is next, in order

Parent: [START-HERE.md](START-HERE.md). **The single list of planned work: features, planned fixes, active
issues, research, chores.** Everything someone intends to do is a row here before work on it starts, and its row
changes in the same commit as the work that moves it. Details live in the linked plan, study, card or issue, never
in the row. Finished rows move to [plan-work-queue-done.md](plan-work-queue-done.md).

Order decided by BevelTipDrip; last reordered 2026-11-18 by BevelTipDrip.
Compact view: `python research/tools/changemap.py queue`; one item and everything that references it:
`changemap.py queue Q-<n>`.

## How to use it

- **IDs:** `Q-<n>`, from `changemap.py queue next`. Never reused, never renumbered. Branch files
  (`work_queue:`), cards (`queue:`), docs ("Work queue: Q-12"), commit messages ("(Q-12)") and handoffs name it.
- **Kind:** `bug` (an active issue: something is broken now), `fix` (a planned fix, or a found problem to fix),
  `feature`, `research` (a question to answer, usually a study), `chore`.
- **State:** `open` / `in progress` / `blocked (on Q-n or what)` / `found` / `confirmed` / `fix built <commit>` /
  `built <commit>` / `run` / `verified (Name)`. Status words: [conventions.md](conventions.md#status-words).
- **Sections:** `Now` is what someone is working on (Owner required; Branch once there is one). `Next` is in order:
  the top row is what gets picked up next. `Later` is everything else, unordered.
- **One row is one line of at most 400 characters** (`check` enforces it): the item, one line of what is known, and
  a link. Measurements, test runs and discussion go in the linked doc.

**When to update it (in the same commit as the work):**

| When | Change |
|---|---|
| A bug, problem or idea turns up while working on something else | A new row (Later, or Next if urgent) **before** fixing it, then carry on |
| Starting an item | Move it to Now: Owner, Branch, `in progress`. The branch's reference file names it (`work_queue:`); `check` fails on the branch until the row is under Now with that branch |
| The state changes (found, confirmed, built, run, verified, blocked) | Its State cell |
| Stopping without finishing | Back to Next or Later, Owner empty, state as far as it got; branch file status `paused` |
| Finished or dropped | Move the row to plan-work-queue-done.md: done with commit / PR and who verified, or dropped with why |
| The order changes | Reorder Next; update "last reordered" above with the name and date |
| Every session start and end | Read Now and Next (`changemap.py queue`); at the end, check your rows (skill `handoff`) |

## Now

| ID | Kind | Item | Owner | Branch | State | Details |
|---|---|---|---|---|---|---|
| Q-1 | feature | Grey scale to D65 at every level: whole-scale magenta lean plus the blue/purple shift near black | BevelTipDrip | feature/nearblack-tint | built (search, not run) | Per-channel LUTs solved by a measured search; run needs the preset choice and a go. [plan-nearblack-tint.md](plan-nearblack-tint.md) |

## Next

| ID | Kind | Item | Owner | Branch | State | Details |
|---|---|---|---|---|---|---|
| Q-2 | feature | Peak 1000: dense sweep, then a v2 (snapped) profile | | | open | v1 is unsnapped and built from the 26-level run, 2 points in the 0.01-0.08 nit jump (T-NB2). [plan-hdr-nearblack-lut.md](plan-hdr-nearblack-lut.md) |
| Q-3 | feature | Re-apply the HDR profile after waking from standby | | | open | ledoge's fix: a scheduled task on System log, Power-Troubleshooter, Event ID 1. [profiles-reference.md](profiles-reference.md) |
| Q-4 | research | Check the profile reaches fullscreen games (independent flip) | | | run | Reaches the MediEvil port's swapchain (T-MED2); flip mode there unknown; confirm in a known fullscreen game. [plan-hdr-nearblack-lut.md](plan-hdr-nearblack-lut.md) |
| Q-5 | research | Visual check of codes 15, 22, 27, 31, 37 (below the meter's floor) against black | | | open | Decides how the LUT treats inputs under ~0.015 nit. [measurement-reference.md](measurement-reference.md) |
| Q-6 | research | DDC/CI black level (VCP 6C/6E/70) sweep | | | open | Probe `--ddc-sweep`; run with the uncorrected HDR profile so the LUT does not mask it. [measurement-reference.md](measurement-reference.md) |
| Q-7 | research | SDR run: Windows HDR off, Creator mode gamma 2.2 | | | open | Probe `--mode sdr`. [measurement-reference.md](measurement-reference.md) |
| Q-8 | feature | Optional sRGB-to-gamma-2.2 profile for SDR content in Windows HDR | | | open | Windows maps SDR into HDR with the piecewise sRGB curve; the same LUT changes HDR content in that range too. [profiles-reference.md](profiles-reference.md) |
| Q-9 | chore | Probe speed: early stop when readings agree, one persistent spotread session, CSV written per patch | | | open | Near-black readings repeat closely; most patches need 2 readings, not 5. [measurement-reference.md](measurement-reference.md) |
| Q-10 | bug | `set_hdr_profile.py --set` does not change the default when the profile is already associated | | | confirmed | Needs remove + add, or ColorProfileSetDisplayDefaultAssociation. [set-hdr-profile](../changes/profiles/set-hdr-profile.md) |
| Q-11 | bug | Windows can drop the monitor from colour management after a restart | | | found | Seen 2026-11-18: no monitor child under `\\.\DISPLAY1`; Device Manager > Scan for hardware changes restored it. Automate a check. [profiles-reference.md](profiles-reference.md) |

## Later

| ID | Kind | Item | Owner | Branch | State | Details |
|---|---|---|---|---|---|---|
| Q-12 | research | Module architecture: core + modules, and how each module is tested | | | open | Needs a design doc before MCP, Linux or UI work. [plan-roadmap.md](plan-roadmap.md) |
| Q-13 | feature | MCP server: deterministic calibration steps for an LLM | | | open | After Q-12. [plan-roadmap.md](plan-roadmap.md) |
| Q-14 | feature | Linux support: Vulkan HDR10 patch generator and the Linux colour pipeline | | | open | After Q-12. [patchgen-reference.md](patchgen-reference.md) |
| Q-15 | feature | User interface | | | open | After Q-12. [plan-roadmap.md](plan-roadmap.md) |
| Q-16 | feature | Samsung S95B module (network control, calibration settings) | | | open | ColorControl is prior art; read and record service-menu values before changing any. [plan-roadmap.md](plan-roadmap.md) |
| Q-17 | research | 30-100 nits reads 4-8% low on True Black 400: panel tracking or the meter correction? | | | found | Only with the ccmx: without it, 30 nits reads 1.01x (T-MED2). Decide which correction to trust. [measurement-reference.md](measurement-reference.md) |
