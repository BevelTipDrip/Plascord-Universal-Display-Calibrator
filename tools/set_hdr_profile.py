"""
Installs an ICC/MHC2 profile and sets it as the current HDR (advanced colour) profile of a display -- the same
as Settings > Display > Color management > Add profile + Set profile. Also lists / switches between installed
HDR profiles.

  python set_hdr_profile.py --show
  python set_hdr_profile.py --install "../profiles/AW3225QF TB400 near-black fix v1.icc"
  python set_hdr_profile.py --set "HDR Calibrated Profile 11-18-2026 11563.icc"     (back to the old one)
"""
import argparse, ctypes, os, struct, sys
from ctypes import wintypes as W

user32 = ctypes.windll.user32
mscms = ctypes.windll.mscms
COLOR_DIR = r"C:\Windows\System32\spool\drivers\color"
SCOPE_CURRENT_USER = 1  # WCS_PROFILE_MANAGEMENT_SCOPE_CURRENT_USER
CPT_ICC = 0
CPST_STANDARD_DISPLAY_COLOR_MODE, CPST_EXTENDED_DISPLAY_COLOR_MODE = 7, 8


class LUID(ctypes.Structure):
    _fields_ = [("LowPart", W.DWORD), ("HighPart", W.LONG)]


def displays():
    """[(adapter LUID, source id, monitor name)] for active display paths."""
    QDC_ONLY_ACTIVE_PATHS = 2
    np_, nm = ctypes.c_uint32(), ctypes.c_uint32()
    if user32.GetDisplayConfigBufferSizes(QDC_ONLY_ACTIVE_PATHS, ctypes.byref(np_), ctypes.byref(nm)):
        raise OSError("GetDisplayConfigBufferSizes failed")
    paths = ctypes.create_string_buffer(72 * np_.value)
    modes = ctypes.create_string_buffer(64 * nm.value)
    if user32.QueryDisplayConfig(QDC_ONLY_ACTIVE_PATHS, ctypes.byref(np_), paths, ctypes.byref(nm), modes, None):
        raise OSError("QueryDisplayConfig failed")
    out = []
    for i in range(np_.value):
        p = paths.raw[72 * i:72 * (i + 1)]
        s_lo, s_hi, s_id = struct.unpack_from("<IiI", p, 0)
        t_lo, t_hi, t_id = struct.unpack_from("<IiI", p, 20)
        req = ctypes.create_string_buffer(420)
        struct.pack_into("<IIIiI", req, 0, 2, 420, t_lo, t_hi, t_id)  # GET_TARGET_NAME
        name = ""
        if user32.DisplayConfigGetDeviceInfo(req) == 0:
            name = req.raw[36:36 + 128].decode("utf-16-le").split("\0")[0]
        out.append((LUID(s_lo, s_hi), s_id, name, (t_lo, t_hi, t_id)))
    return out


def set_advanced_color(target, enable):
    """Windows HDR on/off for a display target (DISPLAYCONFIG_DEVICE_INFO_SET_ADVANCED_COLOR_STATE)."""
    req = ctypes.create_string_buffer(24)
    struct.pack_into("<IIIiII", req, 0, 10, 24, target[0], target[1], target[2], 1 if enable else 0)
    rc = user32.DisplayConfigSetDeviceInfo(req)
    if rc:
        raise OSError(f"DisplayConfigSetDeviceInfo failed: {rc}")


def reload_hdr(target):
    """Toggle Windows HDR off and on so the display pipeline reloads the HDR profile."""
    import time
    set_advanced_color(target, False)
    time.sleep(3)
    set_advanced_color(target, True)
    time.sleep(5)


def find_display(hint):
    for d in displays():
        if hint.lower() in d[2].lower():
            return d
    sys.exit(f"no active display matching {hint!r}: {[d[2] for d in displays()]}")


def current_default(luid, sid, subtype):
    p = ctypes.c_wchar_p()
    mscms.ColorProfileGetDisplayDefault.argtypes = [ctypes.c_int, LUID, ctypes.c_uint32, ctypes.c_int, ctypes.c_int,
                                                    ctypes.POINTER(ctypes.c_wchar_p)]
    hr = mscms.ColorProfileGetDisplayDefault(SCOPE_CURRENT_USER, luid, sid, CPT_ICC, subtype, ctypes.byref(p))
    if hr != 0:
        return f"(none, hr=0x{hr & 0xFFFFFFFF:08X})"
    name = p.value
    ctypes.windll.kernel32.LocalFree(p)
    return name


def associate(luid, sid, profile_name):
    f = mscms.ColorProfileAddDisplayAssociation
    f.argtypes = [ctypes.c_int, ctypes.c_wchar_p, LUID, ctypes.c_uint32, W.BOOL, W.BOOL]
    hr = f(SCOPE_CURRENT_USER, profile_name, luid, sid, True, True)  # set as default, advanced colour (HDR)
    if hr != 0:
        sys.exit(f"ColorProfileAddDisplayAssociation failed: hr=0x{hr & 0xFFFFFFFF:08X}")


def dissociate(luid, sid, profile_name):
    f = mscms.ColorProfileRemoveDisplayAssociation
    f.argtypes = [ctypes.c_int, ctypes.c_wchar_p, LUID, ctypes.c_uint32, W.BOOL]
    hr = f(SCOPE_CURRENT_USER, profile_name, luid, sid, True)
    if hr != 0:
        sys.exit(f"ColorProfileRemoveDisplayAssociation failed: hr=0x{hr & 0xFFFFFFFF:08X}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--install", help="profile file to install and set as the HDR profile")
    g.add_argument("--set", help="already-installed profile file name to set as the HDR profile")
    g.add_argument("--show", action="store_true", help="show the current profiles")
    g.add_argument("--remove", help="installed profile file name to remove from the display's HDR profiles")
    g.add_argument("--reload", action="store_true", help="toggle Windows HDR off/on to reload the HDR profile")
    ap.add_argument("--display", default="AW3225QF")
    args = ap.parse_args()

    luid, sid, name, target = find_display(args.display)
    if args.reload:
        reload_hdr(target)
        print(f"{name}: Windows HDR toggled off/on")
    if args.install:
        src = os.path.abspath(args.install)
        if not mscms.InstallColorProfileW(None, src):
            err = ctypes.GetLastError()
            sys.exit(f"InstallColorProfile failed (error {err}); "
                     + ("needs an elevated (administrator) prompt" if err == 5 else ""))
        profile = os.path.basename(src)
        print(f"Installed {profile} into {COLOR_DIR}")
        associate(luid, sid, profile)
    elif args.remove:
        dissociate(luid, sid, args.remove)
        print(f"Removed {args.remove} from {name}")
    elif args.set:
        if not os.path.exists(os.path.join(COLOR_DIR, args.set)):
            sys.exit(f"{args.set} is not installed in {COLOR_DIR}")
        associate(luid, sid, args.set)
    print(f"{name}: HDR profile = {current_default(luid, sid, CPST_EXTENDED_DISPLAY_COLOR_MODE)}")
    print(f"{name}: SDR profile = {current_default(luid, sid, CPST_STANDARD_DISPLAY_COLOR_MODE)}")


if __name__ == "__main__":
    main()
