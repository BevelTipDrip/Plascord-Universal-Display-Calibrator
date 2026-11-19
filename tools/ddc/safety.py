"""The only way this package writes a VCP value: SafeDdc (plan-ddc-module.md, "Safety rules").

1. Write whitelist: only codes in SafeDdc.whitelist are written (default: the probe's six white-balance codes).
2. Range check: before every write the code's current and max are read from the monitor; the value must be an int
   in 0..max. A failed read refuses the write.
3. Read back: after every write the code is read again; any other value raises ReadbackMismatch.
4. Save, then restore: `with ddc.preserve(codes):` saves every code first and writes each back (with a read back) on
   leaving the block, by any exit. Restore failures are raised together as RestoreFailed, chained to the exception
   that ended the block.

None of this is the go a person gives before a write to a real display (START-HERE, Rules): that comes first.
"""
from typing import Dict, Iterable, List, Optional, Tuple

from .backend import Backend, DdcError, VcpReply, vcp_name

# The codes tools/nearblack_probe.py writes (DDC_VCPS there): per-channel gain and black level.
DEFAULT_WRITE_WHITELIST = {
    0x16: "red gain", 0x18: "green gain", 0x1A: "blue gain",
    0x6C: "red black level", 0x6E: "green black level", 0x70: "blue black level",
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


class SafeDdc:
    def __init__(self, backend: Backend, index: int, whitelist: Optional[Dict[int, str]] = None):
        self.backend = backend
        self.index = index
        self.whitelist = dict(DEFAULT_WRITE_WHITELIST if whitelist is None else whitelist)

    def get(self, code: int) -> VcpReply:
        """Read any code (reads are not limited by the whitelist)."""
        return self.backend.get_vcp(self.index, code)

    def check_write(self, code: int, value) -> VcpReply:
        """Every check a write must pass, without writing. Returns the code's current reply."""
        if code not in self.whitelist:
            raise WriteRefused("VCP %02X (%s) is not in the write whitelist (%s)"
                               % (code, vcp_name(code), ", ".join("%02X" % c for c in sorted(self.whitelist))))
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
        refused = [c for c in self.codes if c not in self.ddc.whitelist]
        if refused:
            raise WriteRefused("cannot save and restore VCP %s: not in the write whitelist"
                               % ", ".join("%02X" % c for c in refused))
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
