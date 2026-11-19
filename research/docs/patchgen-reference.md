# Patchgen reference: test-patch generators that put exact signal values on screen

Read it **before changing a patch generator and before every test of it.** **Keep it current:** a new rule,
symptom or dead end goes in here the same day, in one line with a pointer to the findings. Parent:
[START-HERE.md](START-HERE.md).

## 1. Directory

| What | Where |
|---|---|
| HDR10 generator (Windows, D3D11) | `tools/hdrgen/hdr10_patchgen.cpp` ([hdr10-patchgen](../changes/patchgen/hdr10-patchgen.md)) |
| Its build | `tools/hdrgen/build.ps1` ([building-and-tools.md](building-and-tools.md#build)) |
| SDR patches | `SdrWindow` in `tools/nearblack_probe.py` (tkinter) |

## 2. Invariants: must hold after every change

| # | Rule | What broke when it didn't | How to verify |
|---|---|---|---|
| 1 | HDR patches are written as R10G10B10A2 in `DXGI_COLOR_SPACE_RGB_FULL_G2084_NONE_P2020`, so the PQ codes reach the display unchanged (no SDR-to-HDR mapping) | A patch drawn in SDR inside Windows HDR goes through Windows' sRGB mapping and measures the mapping, not the panel | `SetColorSpace1` in the generator; BevelTipDrip's requirement (2026-11-18) |
| 2 | The generator refuses to run when the output is not in HDR (`ERROR Windows HDR is off`) | Patches would be SDR | `IDXGIOutput6` colour-space check |
| 3 | Values are quantized to whole 10-bit codes before drawing, and the reply names the code drawn (`OK <pq> <code10>`) | The probe's target would not match the patch | `main()` loop |
| 4 | Stdin protocol: `N <nits> <area>`, `P <pq 0-1> <area>`, `B` (background), `Q`; `READY` at start, `OK` after 4 presented frames | The probe hangs or reads the previous patch | `HdrGenerator` in the probe |
| 5 | The display is held awake while the generator runs | Display slept mid-run (2026-11-18) | `SetThreadExecutionState` |

## 3. Before every test

1. A person has said go (patches on screen).
2. Windows HDR on for the display under test.
3. `--composed` only when testing the composed path on purpose; the default is an independently flipped full-screen
   window, like a fullscreen game.

## 4. Symptom -> first place to look

| Symptom | Most likely cause | Look at |
|---|---|---|
| `ERROR Windows HDR is off` | Use HDR is off for that display | Windows Settings > Display |
| Probe waits forever after a patch | Generator closed (Esc) or did not print `OK` | `HdrGenerator.show` |

## 5. Things not to retry

| What | Why it failed | Where written up |
|---|---|---|
| (none yet) | | |

## 6. Linux (planned)

A Vulkan generator with an HDR10 (ST 2084, BT.2020) swapchain is the planned Linux counterpart (Q-14). It must keep
invariants 1-4 and the stdin protocol, so the probe can drive either.
