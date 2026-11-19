---
id: hdr10-patchgen
title: Native HDR10 patch generator: D3D11 flip swapchain in R10G10B10A2 with ST 2084 / BT.2020, so exact PQ codes reach the display; driven over stdin
area: patchgen
status: active
default: n/a
origin: ours
owner: BevelTipDrip
commits: c491027
prs:
queue: Q-14
files: tools/hdrgen/hdr10_patchgen.cpp, tools/hdrgen/build.ps1
symbols: PqFromNits, Reader, WndProc, Command, Fail
switches:
tests: T-NB1, T-NB7
docs: patchgen-reference.md
depends_on:
conflicts_with:
supersedes:
related: nearblack-probe
checked:
---
## What it does

`tools/hdrgen/hdr10_patchgen.exe` opens a borderless topmost full-screen window with a flip-discard swapchain
(R10G10B10A2_UNORM) and calls `SetColorSpace1(DXGI_COLOR_SPACE_RGB_FULL_G2084_NONE_P2020)`, so the values drawn are
the PQ codes the display receives, with no Windows SDR-to-HDR mapping. A reader thread takes `N` / `P` / `B` / `Q`
commands on stdin; `C <r> <g> <b>` draws separate 10-bit codes per channel. Each frame clears the background and
`ClearView`s the patch, quantized to 10 bits; after 4 frames it prints `OK <pq> <code10>` (`OK <r> <g> <b>` for
`C`). `--composed` makes the window 2 px short so DWM composes it.

## Invariants

- Exits with `ERROR Windows HDR is off ...` unless the output's colour space is G2084 / P2020.
- Patch values are quantized to whole 10-bit codes, and the reply names the code(s) drawn; `N` and `P` draw the
  same value on all three channels.
- Prints exactly one `READY ...` line before any `OK`; the probe waits for it.
- Holds the display awake (`SetThreadExecutionState`) while running.

## Interactions

- [nearblack-probe](../measurement/nearblack-probe.md) (`HdrGenerator`) depends on the stdin / stdout protocol; a
  Linux generator (Q-14) must keep it.
- MHC2 LUTs apply to its independently flipped output (T-NB7), as they would to a fullscreen game.

## Evidence

- `C` command: built 2026-11-18 (compiles); not run yet (showing it puts a patch on screen).

- T-NB1 to T-NB9 (2026-11-18): every HDR run; uncorrected 10 nits read 10.5-10.65, tracking PQ.

## History and pitfalls

- Link error for `GetStockObject` until `gdi32.lib` was added; a stray `%d` in the READY line printed garbage.
- A `build.bat` failed on `(x86)` in the VS path; replaced by `build.ps1`.
