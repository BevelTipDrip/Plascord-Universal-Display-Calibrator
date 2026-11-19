---
id: set-hdr-profile
title: Install an ICC/MHC2 profile and make it the display's HDR profile through mscms, show the current profiles, and toggle Windows HDR through DisplayConfig
area: profiles
status: active
default: n/a
origin: ours
owner: BevelTipDrip
commits: c491027
prs:
queue: Q-10
files: tools/set_hdr_profile.py
symbols: displays, set_advanced_color, reload_hdr, find_display, current_default, associate, dissociate
switches:
tests: T-NB7
docs: profiles-reference.md
depends_on:
conflicts_with:
supersedes:
related: mhc2-lut
checked:
---
## What it does

`tools/set_hdr_profile.py` finds the display by name through `QueryDisplayConfig` / `DisplayConfigGetDeviceInfo`,
installs a profile (`InstallColorProfileW`) and associates it as the default advanced-colour (HDR) profile for the
current user (`ColorProfileAddDisplayAssociation`), removes associations, prints the current HDR and SDR defaults
(`ColorProfileGetDisplayDefault`), and toggles Windows HDR off and on (`DisplayConfigSetDeviceInfo`, type 10).

## Invariants

- Scope is the current user; it never changes system-wide associations.
- `DISPLAYCONFIG_PATH_INFO` is 72 bytes with the target at offset 20; target-name requests are 420 bytes.

## Interactions

- The profile only takes effect when NVIDIA reference mode is off and Windows still lists the monitor
  ([profiles-reference.md](../../docs/profiles-reference.md)).

## Evidence

- 2026-11-18: installed True Black 400 v1 and v2 through the API; applied at once with reference mode off (T-NB7).

## History and pitfalls

- `--set` does not make an already-associated profile the default again (Q-10, confirmed 2026-11-18).
- The adapter-name request failed with rc 87 until its buffer was 276 bytes.
