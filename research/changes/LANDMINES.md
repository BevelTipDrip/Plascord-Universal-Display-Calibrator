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
- **`Response.__call__` clamps outside the measured codes** (returns the end values), so `snap_lut` compares
  against flat light there. Harmless while snapping stops above `--blend-start`; a trap if that range grows.
  Cards: mhc2-lut, lut-snap.

## Traps for future changes

- **The `run` column in the moved CSVs holds the old labels** (e.g. `tb400_fix_v2_verify`), not the test IDs in the
  file names (`research/docs/data/nearblack-t-nb9-...`). Files are byte for byte; go by the file name.

## Resolved

- **MHC2 profiles silently ignored**: NVIDIA "Override to reference mode" was ticked. **confirmed 2026-11-18**:
  unticking it applied the LUT at once (T-NB7). Cards: set-hdr-profile, mhc2-lut.
