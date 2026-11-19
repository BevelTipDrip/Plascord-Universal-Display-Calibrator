"""Keep the display awake while DDC/CI commands run, and let it sleep again afterwards (Windows; Q-20).

Why (T-DDC2 / T-DDC2c, 2026-11-19, plan-ddc-module.md): the AW3225QF answers DDC/CI while asleep, but in standby
(VCP D6 = 4) it reports standby values for brightness, E2, F2 and F4/F5; during a scan Windows turned the display
off again mid-run; and for ~2 s after D6 first reads 1 (on), F4/F5 flip between 48 and 16 and some reads fail, then
hold steady. So `--keep-awake`: hold the display on, wake it, wait until D6 reads 1, then SETTLE_S more seconds.

Nothing here is a DDC/CI write: waking is a 1-pixel mouse nudge and back (SendInput, as tools/display_power.py does),
holding is SetThreadExecutionState, and `display_off` is the SC_MONITORPOWER message Windows itself sends when the
display-off timer runs out.
"""
import sys
import time
from typing import Callable, Optional

from .backend import Backend, DdcError

POWER_ON = 1        # MCCS VCP D6 value: on
SETTLE_S = 5.0      # seconds after D6 first reads 1 before state codes are trusted (T-DDC2c: ~2 s unsettled)
WAKE_TIMEOUT_S = 20.0
POLL_S = 0.5

ES_CONTINUOUS, ES_SYSTEM_REQUIRED, ES_DISPLAY_REQUIRED = 0x80000000, 0x00000001, 0x00000002


class Power:
    """What the CLI needs from the OS. hold(): keep the display on until release(). wake(): ask it to wake now.
    display_off(): turn it off as the idle timer would."""
    supported = False

    def hold(self) -> None:
        pass

    def release(self) -> None:
        pass

    def wake(self) -> None:
        pass

    def display_off(self) -> None:
        pass


class WindowsPower(Power):
    supported = True

    def __init__(self):
        import ctypes
        from ctypes import wintypes as W
        self._ct, self._W = ctypes, W
        self._k32 = ctypes.windll.kernel32
        self._u32 = ctypes.windll.user32

    def hold(self):
        self._k32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED)

    def release(self):
        self._k32.SetThreadExecutionState(ES_CONTINUOUS)

    def _nudge(self, dx):
        ct, W = self._ct, self._W

        class MOUSEINPUT(ct.Structure):
            _fields_ = [("dx", W.LONG), ("dy", W.LONG), ("mouseData", W.DWORD), ("dwFlags", W.DWORD),
                        ("time", W.DWORD), ("dwExtraInfo", ct.POINTER(ct.c_ulong))]

        # No padding: MOUSEINPUT is the largest member of INPUT's union, so this is sizeof(INPUT) exactly (40 bytes on
        # 64-bit, 28 on 32-bit). SendInput fails (returns 0) on any other size; display_power.py's 48-byte INPUT
        # does (found 2026-11-19).
        class INPUT(ct.Structure):
            _fields_ = [("type", W.DWORD), ("mi", MOUSEINPUT)]

        inp = INPUT(type=0, mi=MOUSEINPUT(dx, 0, 0, 0x0001, 0, None))  # INPUT_MOUSE, MOUSEEVENTF_MOVE (relative)
        return self._u32.SendInput(1, ct.byref(inp), ct.sizeof(INPUT))

    def wake(self):
        """A one-shot ES_DISPLAY_REQUIRED (without ES_CONTINUOUS) is what wakes a display the idle timer turned off
        (2026-11-19: the continuous form alone left the AW3225QF in standby for 20 s); the mouse nudge is a second
        route."""
        self._k32.SetThreadExecutionState(ES_DISPLAY_REQUIRED)
        self._nudge(1)
        time.sleep(0.05)
        self._nudge(-1)

    def display_off(self):
        # HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, 2 = off
        self._u32.PostMessageW(0xFFFF, 0x0112, 0xF170, 2)


def platform_power() -> Power:
    return WindowsPower() if sys.platform == "win32" else Power()


def wait_awake(backend: Backend, index: int, settle: float = SETTLE_S, timeout: float = WAKE_TIMEOUT_S,
               poll: float = POLL_S, log: Optional[Callable[[str], None]] = None) -> bool:
    """Poll VCP D6 every `poll` s (via backend.wait) until it reads POWER_ON, up to `timeout` s, then wait `settle`
    s more. Returns True when D6 read on. Read only. Time is counted from the waits, so the fake backend needs no
    real time."""
    waited = 0.0
    while True:
        try:
            on = backend.get_vcp(index, 0xD6).current == POWER_ON
        except DdcError:
            on = False
        if on:
            if log:
                log("display on (VCP D6 = 1) after %.1f s; settling %.0f s" % (waited, settle))
            backend.wait(settle)
            return True
        if waited >= timeout:
            if log:
                log("WARNING display not on after %.0f s (VCP D6 is not 1): state codes will read standby values"
                    % timeout)
            return False
        backend.wait(poll)
        waited += poll
