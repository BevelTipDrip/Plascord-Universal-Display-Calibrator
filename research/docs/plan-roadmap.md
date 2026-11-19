# Plan: a universal display calibrator that measures a display and corrects it system-wide

Status: planned 2026-11-18; S1 run, the rest not started. Parent: [START-HERE.md](START-HERE.md). Order of
day-to-day work lives in [plan-work-queue.md](plan-work-queue.md); this page holds the goals, the stages and their
progress.

## Goal

Anyone with a colorimeter can measure their display with true test patches and get a correction that applies
everywhere: the desktop, video and fullscreen games, on Windows and Linux. Corrections and measurements are
deterministic and repeatable, so an LLM connected through an MCP server can run a calibration step by step with
the same result a person would get. Display-specific tools (a monitor's DDC/CI controls, a TV's network
calibration interface) are modules on a shared core.

Out of scope: modifying or bypassing display firmware (BevelTipDrip, 2026-11-18).

## The rule

One change per measurement run; every run has a test ID and is written up with its numbers; a correction is
measured before and after with the same patches, settings and meter; the reference level is re-read during and
after every run, and a run that drifts more than 5% is invalid. A stage is verified only when a person confirms it.

## Stages (proposed 2026-11-18; BevelTipDrip to confirm)

1. **S1 AW3225QF HDR near-black LUT**: per-preset MHC2 profiles that correct the raised near-black luminance
   ([plan-hdr-nearblack-lut.md](plan-hdr-nearblack-lut.md); Q-2, Q-3, Q-4, Q-5).
2. **S2 Grey scale to D65**: the whole-scale magenta lean and the near-black blue/purple shift (Q-1).
3. **S3 SDR and the SDR-in-HDR curve**: SDR measurement, DDC/CI black level, optional sRGB-to-2.2 profile
   (Q-6, Q-7, Q-8).
4. **S4 Module architecture**: a core (meter, patches, measurement runs, correction builders) and modules for
   specific displays, with how each module is tested (Q-12).
5. **S5 MCP server**: deterministic calibration steps exposed to an LLM (Q-13).
6. **S6 Linux**: a Vulkan patch generator and the Linux colour pipeline (Q-14).
7. **S7 More displays**: e.g. a Samsung S95B module over the network (Q-16).
8. **S8 User interface** (Q-15).

## Progress

States: `not started` / `in progress` / `built` / `run` / `verified` (who). PR column: number once opened.

| Stage | State | Commit | PR | Notes |
|---|---|---|---|---|
| S0 Repo and docs | built | | | Set up from the docs template 2026-11-18 |
| S1 AW3225QF HDR near-black LUT | run | | | True Black 400 v2 profile within 7% of target, 0.075-20 nits (T-NB9); Peak 1000 still v1 |
| S2 Grey scale to D65 | in progress | | | |
| S3 SDR | not started | | | |
| S4 Module architecture | not started | | | |
| S5 MCP server | not started | | | |
| S6 Linux | not started | | | |
| S7 More displays | not started | | | |
| S8 User interface | not started | | | |
