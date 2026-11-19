"""Wake the display (a 1-pixel mouse nudge and back) or turn it off (SC_MONITORPOWER), for unattended runs.
  python display_power.py wake
  python display_power.py off
"""
import ctypes, sys, time
from ctypes import wintypes as W

user32 = ctypes.windll.user32


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", W.LONG), ("dy", W.LONG), ("mouseData", W.DWORD), ("dwFlags", W.DWORD), ("time", W.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class INPUT(ctypes.Structure):
    _fields_ = [("type", W.DWORD), ("mi", MOUSEINPUT), ("_pad", ctypes.c_byte * 8)]


def nudge(dx):
    inp = INPUT(type=0, mi=MOUSEINPUT(dx, 0, 0, 0x0001, 0, None))  # MOUSEEVENTF_MOVE (relative)
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "wake":
        nudge(1)
        time.sleep(0.05)
        nudge(-1)
        ctypes.windll.kernel32.SetThreadExecutionState(0x00000002)  # ES_DISPLAY_REQUIRED: reset the idle timer
        print("display wake requested")
    elif cmd == "off":
        user32.PostMessageW(0xFFFF, 0x0112, 0xF170, 2)  # HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, off
        print("display off requested")
    else:
        sys.exit(__doc__)
