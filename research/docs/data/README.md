# data

Measured logs, stats, traces and captures that the docs quote, named `<topic>-<test or stage>-YYYY-MM-DD.<ext>`
(`sync-t-sync3-2026-11-18.log`). Link each file from the plan, study or handoff that uses it, and quote it as
`data/<file>:<line>`. Stored byte for byte (see `.gitattributes`). Small text only (under ~1 MB each); large
captures stay outside git, at the path given in [building-and-tools.md](../building-and-tools.md).
