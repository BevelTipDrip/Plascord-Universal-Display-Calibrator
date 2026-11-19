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
| Q-9 | chore | Probe speed: stop at 2 readings when they agree; CSV written per patch | BevelTipDrip | feature/nearblack-tint | built | `--agree` (fake meter: 100 -> 49 readings for 26 levels); one spotread session dropped (keyboard-only input, ~1.3 s saved of 7-15 s). Not run on the meter yet. [nearblack-probe](../changes/measurement/nearblack-probe.md) |
| Q-1 | feature | Grey scale to D65 at every level: whole-scale magenta lean plus the blue/purple shift near black | BevelTipDrip | feature/nearblack-tint | built (search, not run) | Per-channel LUTs solved by a measured search; run needs the preset choice and a go. [plan-nearblack-tint.md](plan-nearblack-tint.md) |
| Q-20 | feature | DDC/CI module: read/write a monitor's VCP codes safely, Windows first, Linux later | BevelTipDrip | feature/ddc-module | built e40689f | Package, safety layer, CLI, 62 unit tests on a fake backend; not run on a monitor (unreachable 2026-11-19); nothing written. Related: Q-6 (black-level sweep), Q-12 (module architecture, undecided). [plan-ddc-module.md](plan-ddc-module.md) |

## Next

| ID | Kind | Item | Owner | Branch | State | Details |
|---|---|---|---|---|---|---|
| Q-18 | research | Plascord loads its own correction (per-display LUT and matrix) without Windows colour management | | | open | Windows profile selection is unreliable (Q-11, T-NT0); the tool should not depend on it (BevelTipDrip, 2026-11-18). Candidates: GPU driver APIs, the kernel display gamma path. [plan-nearblack-tint.md](plan-nearblack-tint.md) |
| Q-19 | research | The near-black response drifts between sessions: how much, why, and what a profile must do about it | | | confirmed | Time, not the profile: +12-21% near black ~1 h after a power cut, settling to within 3% of T-NB3 ~3 h later (T-DRIFT1/2). Open: cause, and other triggers. [plan-nearblack-tint.md](plan-nearblack-tint.md) |
| Q-3 | feature | Re-apply the HDR profile after waking from standby | | | open | ledoge's fix: a scheduled task on System log, Power-Troubleshooter, Event ID 1. [profiles-reference.md](profiles-reference.md) |
| Q-4 | research | Check the profile reaches fullscreen games (independent flip) | | | run | Reaches the MediEvil port's swapchain (T-MED2); flip mode there unknown; confirm in a known fullscreen game. [plan-hdr-nearblack-lut.md](plan-hdr-nearblack-lut.md) |
| Q-5 | research | Visual check of codes 15, 22, 27, 31, 37 (below the meter's floor) against black | | | open | Decides how the LUT treats inputs under ~0.015 nit. [measurement-reference.md](measurement-reference.md) |
| Q-6 | research | DDC/CI black level (VCP 6C/6E/70) sweep | | | open | Probe `--ddc-sweep`; run with the uncorrected HDR profile so the LUT does not mask it. [measurement-reference.md](measurement-reference.md) |
| Q-7 | research | SDR run: Windows HDR off, Creator mode gamma 2.2 | | | open | Probe `--mode sdr`. [measurement-reference.md](measurement-reference.md) |
| Q-8 | feature | Optional sRGB-to-gamma-2.2 profile for SDR content in Windows HDR | | | open | Windows maps SDR into HDR with the piecewise sRGB curve; the same LUT changes HDR content in that range too. [profiles-reference.md](profiles-reference.md) |
| Q-10 | bug | `set_hdr_profile.py --set` does not change the default when the profile is already associated | | | confirmed | Needs remove + add, or ColorProfileSetDisplayDefaultAssociation. [set-hdr-profile](../changes/profiles/set-hdr-profile.md) |
| Q-11 | bug | Windows loses the monitor from colour management (Settings and mscms) | | | confirmed | Twice on 2026-11-18: no monitor under `\\.\DISPLAY1` in EnumDisplayDevices while PnP, WMI and DisplayConfig still have it; Settings crashes on Add profile. [profiles-reference.md](profiles-reference.md#4-symptom---first-place-to-look) Related: Q-22 (two device instances, found 2026-11-19). |
| Q-22 | bug | Second monitor device instance has no profile association: Windows can fall back to Dell's identity TB400 profile | | | found (on hold) | On hold until we know what the second instance is (BevelTipDrip, 2026-11-19). [profiles-reference.md](profiles-reference.md#7-dells-monitor-driver-and-the-profile-windows-falls-back-to-found-2026-11-19) |
| Q-23 | bug | `display_power.py wake`: SendInput gets a 48-byte INPUT (64-bit wants 40) and fails; only the ES_DISPLAY_REQUIRED call wakes the display | | | found | Found 2026-11-19 building `ddc/power.py` (fixed there, feature/ddc-module 2a5f8cd). [plan-ddc-module.md on feature/ddc-module] |

## Later

| ID | Kind | Item | Owner | Branch | State | Details |
|---|---|---|---|---|---|---|
| Q-12 | research | Module architecture: core + modules, and how each module is tested | | | open | Needs a design doc before MCP, Linux or UI work. [plan-roadmap.md](plan-roadmap.md) |
| Q-13 | feature | MCP server: deterministic calibration steps for an LLM | | | open | After Q-12. [plan-roadmap.md](plan-roadmap.md) |
| Q-14 | feature | Linux support: Vulkan HDR10 patch generator and the Linux colour pipeline | | | open | After Q-12. [patchgen-reference.md](patchgen-reference.md) |
| Q-15 | feature | User interface | | | open | After Q-12. [plan-roadmap.md](plan-roadmap.md) |
| Q-16 | feature | Samsung S95B module (network control, calibration settings) | | | open | ColorControl is prior art; read and record service-menu values before changing any. [plan-roadmap.md](plan-roadmap.md) |
| Q-17 | research | 30-100 nits reads 4-8% low on True Black 400: panel tracking or the meter correction? | | | found | Only with the ccmx: without it, 30 nits reads 1.01x (T-MED2). Decide which correction to trust. [measurement-reference.md](measurement-reference.md) |
