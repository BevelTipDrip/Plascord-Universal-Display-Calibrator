# Work queue: done and dropped

Parent: [plan-work-queue.md](plan-work-queue.md). Rows move here when they finish, newest first, so the queue
stays short enough to read every session. Nothing is deleted: IDs stay findable (`changemap.py queue Q-<n>`).
A `done` row names its commit or PR and who verified it; a `dropped` row says why under Result.

| ID | Kind | Item | State | Result | Commit / PR | Verified by | Date |
|---|---|---|---|---|---|---|---|
| Q-2 | feature | Peak 1000: dense sweep, then a v2 (snapped) profile | dropped | Dropped for now: True Black 400 is the mode to calibrate (BevelTipDrip, 2026-11-18: "we will drop it for now at least, the correct mode for the monitor is a well calibrated HDR400") | | | 2026-11-18 |
