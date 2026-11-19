"""An in-memory DDC/CI backend for tests and for trying the CLI without hardware (`--backend fake`).

Each FakeMonitor holds VCP values as {code: [current, maximum]} and can be told to misbehave like a real link:
reads or writes of given codes fail, writes of given codes are accepted but change nothing (a control the current
preset locks), or a function changes what a write stores (quantizing). Every write that reached the monitor is
logged in FakeBackend.writes, so a test can prove that nothing was written.
"""
from typing import Callable, Dict, List, Optional, Tuple

from .backend import Backend, DdcError, MonitorInfo, VcpReply


class FakeMonitor:
    def __init__(self, description="FAKE", device="fake:0", values=None, caps=""):
        self.description = description
        self.device = device
        self.values = {c: [cur, mx] for c, (cur, mx) in (values or {}).items()}  # type: Dict[int, List[int]]
        self.caps = caps
        self.fail_reads = set()      # codes whose reads raise
        self.fail_writes = set()     # codes whose writes raise
        self.ignore_writes = set()   # codes whose writes are accepted and change nothing
        self.transform = None        # type: Optional[Callable[[int, int], int]]  # (code, value) -> stored value
        self.types = {}              # type: Dict[int, int]  # VCP type per code (default 1, set parameter)
        self.zero_unsupported = False  # codes without a value answer 0 of 0 instead of failing (some monitors do)


class FakeBackend(Backend):
    name = "fake"

    def __init__(self, monitors):
        self._monitors = list(monitors)
        self.writes = []  # type: List[Tuple[int, int, int]]  # (index, code, value), every write that reached a monitor
        self.reads = []   # type: List[Tuple[int, int]]  # (index, code), every read
        self.waits = []   # type: List[float]  # every Backend.wait, in seconds
        self.closed = False

    def _m(self, index) -> FakeMonitor:
        if self.closed:
            raise DdcError("backend is closed")
        if not 0 <= index < len(self._monitors):
            raise DdcError("no monitor with index %d" % index)
        return self._monitors[index]

    def monitors(self):
        return [MonitorInfo(i, m.description, m.device) for i, m in enumerate(self._monitors)]

    def get_vcp(self, index, code):
        m = self._m(index)
        self.reads.append((index, code))
        if code in m.fail_reads or (code not in m.values and not m.zero_unsupported):
            raise DdcError("VCP %02X read failed on monitor %d (fake)" % (code, index))
        cur, mx = m.values.get(code, (0, 0))
        return VcpReply(cur, mx, m.types.get(code, 1))

    def set_vcp(self, index, code, value):
        m = self._m(index)
        if code in m.fail_writes or code not in m.values:
            raise DdcError("VCP %02X write of %d failed on monitor %d (fake)" % (code, value, index))
        self.writes.append((index, code, value))
        if code in m.ignore_writes:
            return
        m.values[code][0] = m.transform(code, value) if m.transform else value

    def capabilities(self, index):
        return self._m(index).caps

    def close(self):
        self.closed = True

    def wait(self, seconds):
        self.waits.append(seconds)  # no real pause: there is no link to wait for


class FakePower:
    """ddc.power.Power for tests: logs hold / wake / release / display_off in `calls`; on_wake() runs on wake (e.g.
    set a FakeMonitor's D6 to 1, as a real monitor leaving standby would)."""
    supported = True

    def __init__(self, on_wake=None):
        self.calls = []  # type: List[str]
        self.on_wake = on_wake

    def hold(self):
        self.calls.append("hold")

    def release(self):
        self.calls.append("release")

    def wake(self):
        self.calls.append("wake")
        if self.on_wake:
            self.on_wake()

    def display_off(self):
        self.calls.append("display_off")


# What the AW3225QF reported on 2026-11-18 for the codes the probe writes (plan-nearblack-tint.md on
# feature/nearblack-tint): gains 100 of 100, black levels 50 of 255. The rest are made-up but plausible.
DEMO_VALUES = {0x10: (75, 100), 0x12: (75, 100), 0x14: (11, 12), 0x16: (100, 100), 0x18: (100, 100),
               0x1A: (100, 100), 0x60: (15, 18), 0x6C: (50, 255), 0x6E: (50, 255), 0x70: (50, 255),
               0xD6: (1, 5), 0xDC: (0, 5), 0xDF: (0x0201, 0xFFFF),
               0xE2: (20, 255)}  # E2 replies but DEMO_CAPS does not list it: a hidden-setting candidate
# A made-up capabilities string in the usual MCCS shape (not read from a real monitor).
DEMO_CAPS = ("(prot(monitor)type(LCD)model(FAKE-DEMO)cmds(01 02 03 07 0C E3 F3)vcp(02 04 05 08 10 12 14(05 08 0B 0C) "
             "16 18 1A 52 60(0F 11 12) 6C 6E 70 AC AE B2 B6 C6 C8 C9 D6(01 04 05) DC(00 02 03 05) DF)"
             "mccs_ver(2.1)mswhql(1))")


def demo_backend() -> FakeBackend:
    return FakeBackend([FakeMonitor("FAKE-DEMO (in memory)", "fake:0", DEMO_VALUES, DEMO_CAPS)])
