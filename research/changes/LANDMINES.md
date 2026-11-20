# Landmines

Traps found while reading or checking the code (by a card checker, a review, a study) that nobody has acted on yet.
**Treat each item as a lead to confirm before acting on it.** Ordered by what they could cost: wrong past
conclusions first, then latent bugs, then traps for future changes. Name the cards involved.

When an item is acted on, do not delete it: add its outcome in bold with the status word and date
(**confirmed in code 2026-11-20; fix built `abc1234`**), and move it to Resolved once verified or dropped.

## Past results that may be wrong

- **Absolute luminance depends on one community meter correction.** Every T-NB run used
  `tools/argyll/AW3225QF_i1d3.ccmx`, a user-submitted entry in DisplayCAL's corrections database, made on another
  unit with an i1 Pro 2 (building-and-tools.md, Toolchain). Ratios between runs hold; absolute values,
  and the 4-8% low reading at 30-100 nits, may be the correction's (Q-17). Cards: nearblack-probe, mhc2-lut.

## Latent bugs

- **`build_mhc2.py` defaults `--base` to a file on one machine** (`DEFAULT_BASE`); anyone else gets a
  FileNotFoundError until they pass `--base`. Card: mhc2-lut.
- **The identity part of a corrected LUT stores exactly `i/1023`** (`build_lut` above `--blend-end`), and the
  pipeline truncates LUT output (T-NB7). If the s15.16 value lands a hair under, that input goes out one code low
  (about 1% above 30 nits). Not seen clearly in T-NB9 (30-100 nits matched the uncorrected panel within 2%) [I].
  Storing `(i + 0.25)/1023` as `snap_lut` does would rule it out. Cards: mhc2-lut, lut-snap. **Confirmed
  2026-11-19:** v2's LUT, read back, sends 401 for 402 and 593 for 594 (one code low across its identity range).
  `--anchors` profiles (v3) store every code as code + 0.25 and are built on the codes v2 actually sends.
- **`Response.__call__` clamps outside the measured codes** (returns the end values), so `snap_lut` compares
  against flat light there. Harmless while snapping stops above `--blend-start`; a trap if that range grows.
  Cards: mhc2-lut, lut-snap.

## Traps for future changes

- **Two copies of the DDC/CI code until the probe adopts `tools/ddc/`.** `tools/nearblack_probe.py` (on
  `feature/nearblack-tint`) keeps its own `open_monitor` / `vcp_set` / `DDC_VCPS`: no `argtypes` on the dxva2
  calls, the read back after a write printed but not compared, and the other monitors' physical handles never
  destroyed [inferred from code, not tested]. A change to the write whitelist or the safety rules must go in both
  until plan-ddc-module.md stage D4. Cards: nearblack-probe, ddc-module.

- **The `run` column in the moved CSVs holds the old labels** (e.g. `tb400_fix_v2_verify`), not the test IDs in the
  file names (`research/docs/data/nearblack-t-nb9-...`). Files are byte for byte; go by the file name.

## Resolved

- **`build_mhc2.py` averaged every HDR row per code, whatever the `run` column said** (DDC-step rows would have
  entered the fit). **fix built 2026-11-18**: `load_response` skips `ddc_` runs and non-grey rows. Cards: mhc2-lut,
  nearblack-probe.
- **MHC2 profiles silently ignored**: NVIDIA "Override to reference mode" was ticked. **confirmed 2026-11-18**:
  unticking it applied the LUT at once (T-NB7). Cards: set-hdr-profile, mhc2-lut.
