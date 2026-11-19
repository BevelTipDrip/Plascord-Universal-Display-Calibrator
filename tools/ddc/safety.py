"""The only way this package writes a VCP value: SafeDdc (plan-ddc-module.md, "Safety rules").

0. Never list: codes in NEVER_WRITE (plus a display module's own, ddc.displays) are refused always. No whitelist,
   option or argument overrides it: SafeDdc refuses to be built with one in its whitelist, and checks again before
   every write and every save.
1. Write whitelist: only codes in SafeDdc.whitelist are written (default: DEFAULT_WRITE_WHITELIST; a caller, e.g.
   the CLI's --allow, may add codes for one SafeDdc, never a never-list code).
2. Range check: before every write the code's current and max are read from the monitor; the value must be an int
   in 0..max. A failed read refuses the write.
3. Read back: after every write the code is read again; any other value raises ReadbackMismatch.
4. Save, then restore: `with ddc.preserve(codes):` saves every code first and writes each back (with a read back) on
   leaving the block, by any exit. Restore failures are raised together as RestoreFailed, chained to the exception
   that ended the block. `restore(saved)` does the same for values a caller saved itself (the CLI's `set`).

None of this is the go a person gives before a write to a real display (START-HERE, Rules): that comes first.
"""
from typing import Dict, Iterable, List, Optional, Tuple

from .backend import Backend, DdcError, VcpReply, vcp_name

# Writable by default: the probe's six white-balance codes (DDC_VCPS in tools/nearblack_probe.py), and brightness
# and contrast (BevelTipDrip, 2026-11-19: "Yes." to adding 10 and 12).
DEFAULT_WRITE_WHITELIST = {
    0x10: "brightness", 0x12: "contrast",
    0x16: "red gain", 0x18: "green gain", 0x1A: "blue gain",
    0x6C: "red black level", 0x6E: "green black level", 0x70: "blue black level",
}

# Never written, by anyone, with any option. MCCS standard codes; a display module adds its own (ddc.displays).
# Why each is here: plan-ddc-module.md, "Safety rules"; the list beyond 04/05/06/08/0A/60/D6 is the drafting
# agent's (2026-11-19), for review.
NEVER_WRITE = {
    0x04: "restore factory defaults (MCCS): wipes every user setting",
    0x05: "restore factory brightness/contrast (MCCS)",
    0x06: "restore factory geometry (MCCS)",
    0x08: "restore factory colour (MCCS)",
    0x0A: "restore factory TV defaults (MCCS)",
    0x60: "input source: a wrong value leaves the screen with no picture to recover from",
    0x76: "remote procedure call (MCCS): runs a vendor-defined procedure, effect unknown",
    0x78: "display identification data (EDID) operation (MCCS)",
    0xB0: "store / restore settings (MCCS): value 2 restores factory defaults",
    0xCA: "OSD / button lock (MCCS): a locked OSD removes the way to reset any other value by hand",
    0xD6: "power mode (MCCS): standby or off",
}


class WriteRefused(DdcError):
    """A write was refused before anything was sent to the monitor."""


class ReadbackMismatch(DdcError):
    """The monitor accepted a write but reads back another value."""

    def __init__(self, code, written, read):
        super().__init__("VCP %02X (%s): wrote %d, read back %d" % (code, vcp_name(code), written, read))
        self.code, self.written, self.read = code, written, read


class RestoreFailed(DdcError):
    """One or more saved values could not be written back."""

    def __init__(self, failures):
        lines = ["VCP %02X (%s) to %d: %s" % (c, vcp_name(c), v, why) for c, v, why in failures]
        super().__init__("could not restore " + "; ".join(lines) + " -- reset it in the monitor's OSD")
        self.failures = failures


def _codes(codes) -> str:
    return ", ".join("%02X" % c for c in sorted(codes))


class SafeDdc:
    def __init__(self, backend: Backend, index: int, whitelist: Optional[Dict[int, str]] = None,
                 never: Optional[Dict[int, str]] = None):
        """whitelist: the codes this SafeDdc may write (default DEFAULT_WRITE_WHITELIST). never: codes refused on
        top of NEVER_WRITE (a display module's). A whitelist naming a never code raises WriteRefused."""
        self.backend = backend
        self.index = index
        self.never = dict(NEVER_WRITE)
        self.never.update(never or {})
        self.whitelist = dict(DEFAULT_WRITE_WHITELIST if whitelist is None else whitelist)
        bad = [c for c in self.whitelist if c in self.never]
        if bad:
            raise WriteRefused("VCP %s: on the never-write list (%s); no whitelist or option can make it writable"
                               % (_codes(bad), "; ".join(self.never[c] for c in sorted(bad))))

    def get(self, code: int) -> VcpReply:
        """Read any code (reads are not limited by the whitelist)."""
        return self.backend.get_vcp(self.index, code)

    def _writable(self, code: int) -> None:
        if code in self.never:  # checked first and on every call: self.whitelist is a plain dict a caller can edit
            raise WriteRefused("VCP %02X (%s) is on the never-write list: %s. No option overrides this"
                               % (code, vcp_name(code), self.never[code]))
        if code not in self.whitelist:
            raise WriteRefused("VCP %02X (%s) is not in the write whitelist (%s)"
                               % (code, vcp_name(code), _codes(self.whitelist)))

    def check_write(self, code: int, value) -> VcpReply:
        """Every check a write must pass, without writing. Returns the code's current reply."""
        self._writable(code)
        if isinstance(value, bool) or not isinstance(value, int):
            raise WriteRefused("VCP %02X: value %r is not an integer" % (code, value))
        try:
            reply = self.get(code)
        except DdcError as e:
            raise WriteRefused("VCP %02X: cannot read its current value and max, so it is not written: %s"
                               % (code, e)) from e
        if not 0 <= value <= reply.maximum:
            raise WriteRefused("VCP %02X (%s): %d is outside the monitor's 0..%d"
                               % (code, vcp_name(code), value, reply.maximum))
        return reply

    def set(self, code: int, value: int) -> int:
        """Check, write, read back. Returns the value read back (equal to value, or ReadbackMismatch is raised)."""
        self.check_write(code, value)
        self.backend.set_vcp(self.index, code, value)
        got = self.get(code).current
        if got != value:
            raise ReadbackMismatch(code, value, got)
        return got

    def preserve(self, codes: Iterable[int]) -> "Preserve":
        """Context manager: save the codes now, restore them on leaving the block by any exit."""
        return Preserve(self, codes)

    def restore(self, saved: Dict[int, int]) -> List[Tuple[int, int, str]]:
        """Write values the caller read from this monitor back (e.g. after a failed or mismatched write). Never-list
        and unlisted codes are refused before anything is written; each value is read back. Returns the failures
        (an empty list when everything is back) instead of raising them."""
        for code in saved:
            self._writable(code)
        return self._restore(saved)

    def _restore(self, saved: Dict[int, int]) -> List[Tuple[int, int, str]]:
        """Write every saved value back with a read back; never stops early. The saved values came from the monitor,
        so they skip the range check (a monitor reporting current > max must still get its value back)."""
        failures = []
        for code, value in saved.items():
            try:
                self.backend.set_vcp(self.index, code, value)
                got = self.get(code).current
                if got != value:
                    failures.append((code, value, "read back %d" % got))
            except (Exception, KeyboardInterrupt) as e:  # keep restoring the others, then report
                failures.append((code, value, str(e) or type(e).__name__))
        return failures


class Preserve:
    def __init__(self, ddc: SafeDdc, codes: Iterable[int]):
        self.ddc = ddc
        self.codes = list(dict.fromkeys(codes))
        self.saved = {}  # type: Dict[int, int]

    def __enter__(self) -> Dict[int, int]:
        never = [c for c in self.codes if c in self.ddc.never]
        if never:
            raise WriteRefused("cannot save and restore VCP %s: on the never-write list" % _codes(never))
        refused = [c for c in self.codes if c not in self.ddc.whitelist]
        if refused:
            raise WriteRefused("cannot save and restore VCP %s: not in the write whitelist" % _codes(refused))
        saved = {}
        for c in self.codes:
            saved[c] = self.ddc.get(c).current  # a failed read raises here, before anything is written
        self.saved = saved
        return dict(saved)

    def __exit__(self, exc_type, exc, tb):
        failures = self.ddc._restore(self.saved)
        if failures:
            if exc is not None:
                raise RestoreFailed(failures) from exc
            raise RestoreFailed(failures)
        return False
