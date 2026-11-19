"""Per-display knowledge on top of the MCCS core (plan-ddc-module.md, "AW3225QF display module"; open question 2).

The core (ddc.backend, ddc.safety, ddc.scan) knows the MCCS protocol, the same on every monitor. A display module
says what a given model does with its codes: names for manufacturer codes, value meanings, which OSD presets lock a
control, and a safety class per code:

    safe       in the core's default write whitelist; written with `set ... --yes` (and a person's go)
    ask first  writable only when named with `--allow` (and a person's go for that write)
    never      refused always, like the core's NEVER_WRITE; the module's never codes are added to it

Every entry carries its source and whether it was confirmed on BevelTipDrip's monitor; anything else is "from
<source>, not confirmed on this monitor". A module can only add never codes; it cannot make a code writable.
"""
from typing import Dict, List, NamedTuple, Optional

SAFE, ASK, NEVER = "safe", "ask first", "never"


class Control(NamedTuple):
    code: int
    name: str
    safety: str                          # SAFE, ASK or NEVER
    what: str                            # what it does on this model, as far as known
    source: str                          # where that comes from
    confirmed: str = ""                  # how and when it was confirmed on BevelTipDrip's monitor; "" = not
    values: Optional[Dict[int, str]] = None  # value -> meaning, when the values are discrete
    locked_by: str = ""                  # OSD presets in which the monitor ignores or hides it
    in_caps: Optional[bool] = None       # listed in the model's capabilities string (per `source`); None = unknown


class DisplayModule(NamedTuple):
    key: str                             # e.g. "aw3225qf"
    model: str                           # e.g. "AW3225QF"
    match: List[str]                     # lower-case substrings of the monitor description or caps model
    controls: Dict[int, Control]
    presets: Dict[str, str]              # OSD preset -> what is known about it
    notes: List[str]
    sources: Dict[str, str]              # short name -> URL or doc

    def names(self) -> Dict[int, str]:
        return {c: ctl.name for c, ctl in self.controls.items()}

    def never(self) -> Dict[int, str]:
        """{code: why} for SafeDdc(never=...)."""
        return {c: "%s (%s display module): %s" % (ctl.name, self.model, ctl.what)
                for c, ctl in self.controls.items() if ctl.safety == NEVER}

    def by_safety(self, safety: str) -> List[int]:
        return sorted(c for c, ctl in self.controls.items() if ctl.safety == safety)


def _registry() -> List[DisplayModule]:
    from . import aw3225qf
    return [aw3225qf.MODULE]


def for_monitor(description: str = "", model: str = "") -> Optional[DisplayModule]:
    """The display module whose match strings occur in the monitor's description or capabilities model, or None."""
    text = ("%s %s" % (description or "", model or "")).lower()
    for mod in _registry():
        if any(m in text for m in mod.match):
            return mod
    return None


def by_key(key: str) -> Optional[DisplayModule]:
    for mod in _registry():
        if mod.key == key.lower():
            return mod
    return None


__all__ = ["SAFE", "ASK", "NEVER", "Control", "DisplayModule", "for_monitor", "by_key"]
