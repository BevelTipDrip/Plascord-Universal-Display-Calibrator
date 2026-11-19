"""Windows DDC/CI backend: dxva2.dll (the Monitor Configuration API) through ctypes, no install.

Ported from tools/nearblack_probe.py (feature/nearblack-tint @ 1703b92, open_monitor / vcp_get / vcp_set), with:
argtypes on every call (handles are pointers, not ints), every physical-monitor handle owned and destroyed by
close(), the Windows error code in every error, the capabilities string, and retries on reads too.

Importing this module is safe on any platform; constructing Dxva2Backend raises DdcError off Windows.
"""
import ctypes
import sys
import time
from typing import List

from .backend import Backend, DdcError, MonitorInfo, VcpReply

# The probe's timing (plan-ddc-module.md, open question 10).
WRITE_TRIES, WRITE_RETRY_WAIT, WRITE_SETTLE = 3, 0.3, 0.15
READ_TRIES, READ_RETRY_WAIT = 2, 0.1


def _api():
    """Load the DLLs and declare the functions. Called once per backend, only on Windows."""
    from ctypes import wintypes as W

    class PHYSICAL_MONITOR(ctypes.Structure):
        _pack_ = 1  # PhysicalMonitorEnumerationAPI.h declares it under #pragma pack(push, 1)
        _fields_ = [("hPhysicalMonitor", W.HANDLE), ("szPhysicalMonitorDescription", W.WCHAR * 128)]

    class MONITORINFOEXW(ctypes.Structure):
        _fields_ = [("cbSize", W.DWORD), ("rcMonitor", W.RECT), ("rcWork", W.RECT), ("dwFlags", W.DWORD),
                    ("szDevice", W.WCHAR * 32)]

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    dxva2 = ctypes.WinDLL("dxva2", use_last_error=True)
    MONITORENUMPROC = ctypes.WINFUNCTYPE(W.BOOL, W.HMONITOR, W.HDC, ctypes.POINTER(W.RECT), W.LPARAM)

    def decl(fn, args, res=W.BOOL):
        fn.argtypes, fn.restype = args, res
        return fn

    decl(user32.EnumDisplayMonitors, [W.HDC, ctypes.POINTER(W.RECT), MONITORENUMPROC, W.LPARAM])
    decl(user32.GetMonitorInfoW, [W.HMONITOR, ctypes.POINTER(MONITORINFOEXW)])
    decl(dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR, [W.HMONITOR, ctypes.POINTER(W.DWORD)])
    decl(dxva2.GetPhysicalMonitorsFromHMONITOR, [W.HMONITOR, W.DWORD, ctypes.POINTER(PHYSICAL_MONITOR)])
    decl(dxva2.DestroyPhysicalMonitors, [W.DWORD, ctypes.POINTER(PHYSICAL_MONITOR)])
    decl(dxva2.GetVCPFeatureAndVCPFeatureReply,
         [W.HANDLE, ctypes.c_ubyte, ctypes.POINTER(W.DWORD), ctypes.POINTER(W.DWORD), ctypes.POINTER(W.DWORD)])
    decl(dxva2.SetVCPFeature, [W.HANDLE, ctypes.c_ubyte, W.DWORD])  # BYTE is unsigned; wintypes.BYTE is not
    decl(dxva2.GetCapabilitiesStringLength, [W.HANDLE, ctypes.POINTER(W.DWORD)])
    decl(dxva2.CapabilitiesRequestAndCapabilitiesReply, [W.HANDLE, ctypes.c_char_p, W.DWORD])
    return W, user32, dxva2, MONITORENUMPROC, PHYSICAL_MONITOR, MONITORINFOEXW


def error_text(code: int) -> str:
    """Windows' message for an error code. dxva2 returns HRESULT-style codes (0xC026xxxx) that FormatError only
    takes in their signed form: passing them unsigned raises OverflowError."""
    code &= 0xFFFFFFFF
    try:
        return ctypes.FormatError(code - 0x100000000 if code >= 0x80000000 else code).strip()
    except (OverflowError, AttributeError, OSError):
        return "no message"


def _err(what):
    code = ctypes.get_last_error() & 0xFFFFFFFF
    return DdcError("%s (Windows error 0x%08X: %s)" % (what, code, error_text(code)))


class Dxva2Backend(Backend):
    name = "windows"

    def __init__(self):
        if sys.platform != "win32":
            raise DdcError("the dxva2 backend runs only on Windows")
        self._W, self._user32, self._dxva2, enum_t, self._PM, self._MI = _api()
        self._arrays = []   # (count, PHYSICAL_MONITOR array) per HMONITOR, destroyed by close()
        self._mons = []     # (MonitorInfo, handle)
        self.skipped = []   # (device, why) for displays with no usable physical monitor
        hmons = []
        cb = enum_t(lambda hm, dc, rect, lp: (hmons.append(hm), True)[1])
        if not self._user32.EnumDisplayMonitors(None, None, cb, 0):
            raise _err("EnumDisplayMonitors failed")
        for hm in hmons:
            self._add(hm)

    def _add(self, hm):
        W = self._W
        info = self._MI()
        info.cbSize = ctypes.sizeof(self._MI)
        device = info.szDevice if self._user32.GetMonitorInfoW(hm, ctypes.byref(info)) else "?"
        n = W.DWORD()
        if not self._dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR(hm, ctypes.byref(n)):
            # e.g. \\.\WinDisc: Windows' stand-in when no display is connected, or the display is off or asleep
            self.skipped.append((device, str(_err("no physical monitor"))))
            return
        if n.value == 0:
            self.skipped.append((device, "no physical monitor"))
            return
        arr = (self._PM * n.value)()
        if not self._dxva2.GetPhysicalMonitorsFromHMONITOR(hm, n, arr):
            self.skipped.append((device, str(_err("GetPhysicalMonitorsFromHMONITOR failed"))))
            return
        self._arrays.append((n.value, arr))
        for p in arr:
            mi = MonitorInfo(len(self._mons), p.szPhysicalMonitorDescription, device)
            self._mons.append((mi, p.hPhysicalMonitor))

    def _h(self, index):
        if not 0 <= index < len(self._mons):
            raise DdcError("no monitor with index %d" % index)
        return self._mons[index][1]

    def monitors(self) -> List[MonitorInfo]:
        return [m for m, _ in self._mons]

    def get_vcp(self, index, code):
        W, h = self._W, self._h(index)
        t, cur, mx = W.DWORD(), W.DWORD(), W.DWORD()
        for i in range(READ_TRIES):
            if self._dxva2.GetVCPFeatureAndVCPFeatureReply(h, code, ctypes.byref(t), ctypes.byref(cur),
                                                           ctypes.byref(mx)):
                return VcpReply(cur.value, mx.value, t.value)
            e = _err("VCP %02X read failed on monitor %d" % (code, index))
            if i + 1 < READ_TRIES:
                time.sleep(READ_RETRY_WAIT)
        raise e

    def set_vcp(self, index, code, value):
        h = self._h(index)
        for i in range(WRITE_TRIES):
            if self._dxva2.SetVCPFeature(h, code, value):
                time.sleep(WRITE_SETTLE)
                return
            e = _err("VCP %02X write of %d failed on monitor %d" % (code, value, index))
            if i + 1 < WRITE_TRIES:
                time.sleep(WRITE_RETRY_WAIT)
        raise e

    def capabilities(self, index):
        W, h = self._W, self._h(index)
        n = W.DWORD()
        if not self._dxva2.GetCapabilitiesStringLength(h, ctypes.byref(n)):
            raise _err("capabilities length request failed on monitor %d" % index)
        buf = ctypes.create_string_buffer(n.value)
        if not self._dxva2.CapabilitiesRequestAndCapabilitiesReply(h, buf, n.value):
            raise _err("capabilities request failed on monitor %d" % index)
        return buf.value.decode("ascii", "replace")

    def close(self):
        for n, arr in self._arrays:
            self._dxva2.DestroyPhysicalMonitors(n, arr)
        self._arrays, self._mons = [], []
