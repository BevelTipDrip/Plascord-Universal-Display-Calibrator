"""The backend interface every DDC/CI backend implements, and the types they share.

A backend talks to monitors and does no checking of its own: it lists monitors, reads any VCP code, writes any VCP
code, and returns the capabilities string. Only ddc.safety.SafeDdc calls set_vcp (plan-ddc-module.md, safety
rule 6); everything else goes through SafeDdc too.
"""
import sys
import time
from typing import List, NamedTuple

from .mccs import MCCS_NAMES, mccs_name

# Names of the MCCS 2.2a VCP codes (ddc.mccs), for messages. Reading any code is allowed; writing is limited by
# ddc.safety (never list, whitelist).
VCP_NAMES = MCCS_NAMES


class DdcError(Exception):
    """A DDC/CI operation failed or was refused."""


class MonitorInfo(NamedTuple):
    index: int          # position in Backend.monitors(); how every other call names the monitor
    description: str    # what the OS or the monitor calls it (dxva2: the physical monitor description)
    device: str         # where it is attached (Windows: \\.\DISPLAY1; Linux: /dev/i2c-<n>)


class VcpReply(NamedTuple):
    current: int
    maximum: int
    vcp_type: int = 1   # MCCS: 0 = momentary, 1 = set parameter (continuous or non-continuous)


def vcp_name(code: int) -> str:
    """The MCCS 2.2a name ('manufacturer specific' for E0-FF)."""
    return mccs_name(code)


def parse_vcp_code(text) -> int:
    """'6C', '0x6C', '6c' -> 0x6C. VCP codes are always hex, as in MCCS and the probe's --ddc-steps.
    An int is taken as it is."""
    if isinstance(text, int):
        code = text
    else:
        s = str(text).strip().lower()
        if s.startswith("0x"):
            s = s[2:]
        if not s or any(ch not in "0123456789abcdef" for ch in s):
            raise ValueError("VCP code %r is not hex (e.g. 6C or 0x6C)" % (text,))
        code = int(s, 16)
    if not 0 <= code <= 0xFF:
        raise ValueError("VCP code %r is outside 00..FF" % (text,))
    return code


class Backend:
    """Base class. Subclasses implement the five methods; use as a context manager so handles are released."""

    name = "base"
    skipped = ()  # (device, why) for displays the backend found but cannot talk DDC/CI to; shown by `list`

    def monitors(self) -> List[MonitorInfo]:
        raise NotImplementedError

    def get_vcp(self, index: int, code: int) -> VcpReply:
        raise NotImplementedError

    def set_vcp(self, index: int, code: int, value: int) -> None:
        """Raw write with no checks. Only ddc.safety.SafeDdc calls this."""
        raise NotImplementedError

    def capabilities(self, index: int) -> str:
        raise NotImplementedError

    def close(self) -> None:
        pass

    def wait(self, seconds: float) -> None:
        """Pause between DDC/CI requests (ddc.scan). The fake backend records it instead of sleeping."""
        time.sleep(seconds)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    def find(self, hint=None) -> int:
        """The index of one monitor: by index (an int or a digit string), by a case-insensitive substring of its
        description or device, or the only monitor when hint is None. Raises DdcError when none or several match."""
        mons = self.monitors()
        if not mons:
            why = "; ".join("%s: %s" % s for s in self.skipped)
            raise DdcError("no monitors found for DDC/CI (a display that is off, asleep or disconnected has none)"
                           + (" -- skipped " + why if why else ""))
        if hint is None or hint == "":
            if len(mons) == 1:
                return mons[0].index
            raise DdcError("%d monitors found; choose one with --monitor or --index: %s"
                           % (len(mons), describe(mons)))
        if isinstance(hint, int) or str(hint).isdigit():
            i = int(hint)
            for m in mons:
                if m.index == i:
                    return i
            raise DdcError("no monitor with index %d: %s" % (i, describe(mons)))
        h = str(hint).lower()
        hits = [m for m in mons if h in m.description.lower() or h in m.device.lower()]
        if len(hits) == 1:
            return hits[0].index
        if not hits:
            raise DdcError("no monitor matching %r: %s" % (hint, describe(mons)))
        raise DdcError("%d monitors match %r; use --index: %s" % (len(hits), hint, describe(hits)))


def describe(mons: List[MonitorInfo]) -> str:
    return "; ".join("%d %s (%s)" % (m.index, m.description, m.device) for m in mons)


def open_backend(name: str = "auto", **kwargs) -> Backend:
    """'auto' (dxva2 on Windows; elsewhere an error until the Linux backend exists), 'windows', or 'fake' (a demo
    monitor in memory, for trying the CLI without hardware)."""
    if name == "auto":
        name = "windows" if sys.platform == "win32" else "linux"
    if name == "windows":
        from .windows import Dxva2Backend
        return Dxva2Backend(**kwargs)
    if name == "fake":
        from .fake import demo_backend
        return demo_backend()
    if name == "linux":
        raise DdcError("the Linux backend is not built yet (plan-ddc-module.md, 'Linux route')")
    raise DdcError("unknown backend %r (auto, windows, fake)" % name)


__all__ = ["VCP_NAMES", "DdcError", "MonitorInfo", "VcpReply", "Backend", "vcp_name", "parse_vcp_code",
           "describe", "open_backend"]
