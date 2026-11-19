"""
Near-black curve probe for the Alienware AW3225QF, using an X-Rite i1Display / ColorMunki Display via
ArgyllCMS 3.5.0 spotread (with HCFR's AW3225QF correction matrix).

Modes
  --mode hdr : Windows HDR ON. Patches come from hdrgen/hdr10_patchgen.exe, a native HDR10 swapchain
               (10-bit, ST 2084 / BT.2020): the PQ codes go to the display as-is, with no Windows SDR-to-HDR
               mapping. Target = the exact luminance of the 10-bit PQ code sent.
  --mode sdr : Windows HDR OFF. Patches are 8-bit codes in a full-screen window (the GPU gamma ramp is set
               linear for the run and restored afterwards). Target = white * (v/255)^gamma (default 2.2).

Each run prints a table and writes research/docs/data/nearblack-<label>-<YYYY-MM-DD>.csv (the project's data
naming: research/docs/data/README.md). Give the run's test ID as --label (e.g. --label t-nb10-peak1000-dense), so
the plan doc's write-up and the file name match. A run whose reference drifts more than 5% is saved with -INVALID.

Needs ArgyllCMS spotread and a meter correction in tools/argyll/ (not in git: research/docs/building-and-tools.md).

Optional --ddc-sweep: temporarily sets the monitor's DDC/CI black level (VCP 0x6C/0x6E/0x70) to each value and
re-measures key levels. Every setting changed is restored on exit (also on Esc, Ctrl+C or errors).

Examples (meter hanging on the screen centre, room dark, display warmed up):
  python nearblack_probe.py --mode hdr --label t-nb10-peak1000-dense --dense
  python nearblack_probe.py --mode sdr --label t-sdr1-creator-g22
  python nearblack_probe.py --mode hdr --label t-ddc1 --ddc-sweep 50,48,46,44,52
"""
import argparse, csv, ctypes, math, os, queue, re, subprocess, sys, threading, time
from ctypes import wintypes as W
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
# ArgyllCMS 3.5.0 (3.0+ fixes the i1d3's low-level readings on OLED; DisplayCAL's 2.1.2 does not have it).
SPOTREAD = os.path.join(HERE, "argyll", "spotread.exe")
# AW3225QF correction for the i1 Display Pro / ColorMunki Display family, made against an i1 Pro 2, from DisplayCAL's
# colorimeter corrections database (not in git: research/docs/building-and-tools.md).
DEFAULT_CCMX = os.path.join(HERE, "argyll", "AW3225QF_i1d3.ccmx")
DATA_DIR = os.path.normpath(os.path.join(HERE, "..", "research", "docs", "data"))
HDRGEN = os.path.join(HERE, "hdrgen", "hdr10_patchgen.exe")

SDR_LEVELS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 14, 16, 20, 24, 28, 32, 40, 48, 64, 96, 128, 192, 255]
SDR_SWEEP = [0, 2, 4, 6, 8, 12, 16, 24, 32, 255]
HDR_LEVELS = [0, 0.005, 0.01, 0.015, 0.02, 0.03, 0.05, 0.075, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1, 1.5, 2, 3, 5,
              7.5, 10, 15, 20, 30, 50, 100]
HDR_SWEEP = [0, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 100]
# Dense sweep by 10-bit PQ code, for building the correction: every code through the steep onset, then coarser.
HDR_DENSE_CODES = (list(range(0, 20, 5)) + list(range(20, 60)) + list(range(60, 130, 2)) + list(range(130, 310, 10))
                   + list(range(310, 521, 30)))
REF_EVERY = 25  # re-read the reference this often during a sweep (drift / brightness limiting)
BLACK_VCPS = (0x6C, 0x6E, 0x70)
# The only VCP codes --ddc-steps may write: per-channel gain and black level (white balance).
DDC_VCPS = {0x16: "red gain", 0x18: "green gain", 0x1A: "blue gain",
            0x6C: "red black", 0x6E: "green black", 0x70: "blue black"}

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
dxva2 = ctypes.windll.dxva2
user32.SetProcessDPIAware()


# ---------------------------------------------------------------- PQ
M1, M2, C1, C2, C3 = 0.1593017578125, 78.84375, 0.8359375, 18.8515625, 18.6875


def pq_from_nits(n):
    yp = (max(n, 0.0) / 10000.0) ** M1
    return ((C1 + C2 * yp) / (1 + C3 * yp)) ** M2


def nits_from_pq(e):
    ep = max(e, 0.0) ** (1 / M2)
    return 10000.0 * (max(ep - C1, 0.0) / (C2 - C3 * ep)) ** (1 / M1)


def pq10(n):
    """The 10-bit code the generator sends for a request, and that code's exact luminance."""
    code = round(pq_from_nits(n) * 1023)
    return code, nits_from_pq(code / 1023)


# ---------------------------------------------------------------- DDC/CI
class _PHYS(ctypes.Structure):
    _fields_ = [("h", W.HANDLE), ("desc", W.WCHAR * 128)]


def open_monitor(name_hint="AW3225QF"):
    mons = []
    cb_t = ctypes.WINFUNCTYPE(W.BOOL, W.HMONITOR, W.HDC, ctypes.POINTER(W.RECT), W.LPARAM)
    user32.EnumDisplayMonitors(None, None, cb_t(lambda h, dc, r, l: (mons.append(h), True)[1]), 0)
    for hm in mons:
        n = W.DWORD()
        dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR(hm, ctypes.byref(n))
        arr = (_PHYS * n.value)()
        dxva2.GetPhysicalMonitorsFromHMONITOR(hm, n, arr)
        for p in arr:
            if name_hint.lower() in p.desc.lower():
                return p.h
    raise RuntimeError(f"No monitor matching {name_hint!r} found for DDC/CI")


def vcp_get(h, code):
    t, cur, mx = W.DWORD(), W.DWORD(), W.DWORD()
    if not dxva2.GetVCPFeatureAndVCPFeatureReply(h, code, ctypes.byref(t), ctypes.byref(cur), ctypes.byref(mx)):
        raise RuntimeError(f"VCP {code:02X} read failed")
    return cur.value, mx.value


def vcp_set(h, code, value):
    for _ in range(3):
        if dxva2.SetVCPFeature(h, code, value):
            time.sleep(0.15)
            return
        time.sleep(0.3)
    raise RuntimeError(f"VCP {code:02X} write failed")


def parse_ddc_steps(text):
    """'16=96;16=100,1A=96' -> [{0x16: 96}, {0x16: 100, 0x1A: 96}]. Each step changes only the codes it names;
    the others keep their value from the step before."""
    steps = []
    for part in text.split(";"):
        step = {}
        for item in filter(None, (s.strip() for s in part.split(","))):
            code, _, value = item.partition("=")
            code, value = int(code, 16), int(value)
            if code not in DDC_VCPS:
                raise argparse.ArgumentTypeError(f"VCP {code:02X} is not one of "
                                                 + ", ".join(f"{c:02X}" for c in DDC_VCPS))
            step[code] = value
        if step:
            steps.append(step)
    if not steps:
        raise argparse.ArgumentTypeError("no DDC steps given")
    return steps


def restore_vcps(h, saved):
    """Write back every saved VCP value; what was restored is removed from `saved`."""
    for c in list(saved):
        try:
            vcp_set(h, c, saved[c])
            print(f"Restored {DDC_VCPS.get(c, hex(c))} (VCP {c:02X}) to {saved.pop(c)}")
        except Exception as e:
            print(f"  ! failed to restore VCP {c:02X} to {saved[c]}: {e} -- reset it in the OSD")


# ---------------------------------------------------------------- GPU gamma ramp (SDR only)
class GammaRamp:
    """Saves the current ramp (e.g. an ICC VCGT), loads linear, restores on exit."""

    def __init__(self):
        self.dc = user32.GetDC(None)
        self.saved = (W.WORD * 768)()
        self.ok = bool(gdi32.GetDeviceGammaRamp(self.dc, ctypes.byref(self.saved)))

    def set_linear(self):
        lin = (W.WORD * 768)()
        for c in range(3):
            for i in range(256):
                lin[c * 256 + i] = i * 257
        if not gdi32.SetDeviceGammaRamp(self.dc, ctypes.byref(lin)):
            print("  ! could not load a linear gamma ramp; an active ICC calibration may skew results")

    def restore(self):
        if self.ok:
            gdi32.SetDeviceGammaRamp(self.dc, ctypes.byref(self.saved))
        user32.ReleaseDC(None, self.dc)


# ---------------------------------------------------------------- meter
_RX = re.compile(r"Yxy:\s*([-\d.eE+]+)\s+([-\d.eE+]+)\s+([-\d.eE+]+)")


def read_meter(display_type, ccmx=None):
    cmd = [SPOTREAD, "-e", "-y", display_type, "-x", "-O"]
    if ccmx:
        cmd[1:1] = ["-X", ccmx]
    r = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=180)
    m = _RX.search(r.stdout + r.stderr)
    if not m:
        raise RuntimeError("spotread gave no reading:\n" + (r.stdout + r.stderr)[-800:])
    return tuple(float(x) for x in m.groups())  # Y (cd/m2), x, y


def adapt_reads(Y):
    """HCFR's low-light averaging ("Adapt"): more readings near black."""
    return 5 if Y < 1 else 4 if Y < 2 else 3 if Y < 5 else 2 if Y < 10 else 1


def readings_agree(vals, tol):
    """True when the readings' Y spread is within tol of their mean (at least 0.0003 cd/m2, the meter's noise near
    black) and their xy spread within 0.003."""
    ys = [v[0] for v in vals]
    mean = sum(ys) / len(ys)
    if max(ys) - min(ys) > max(tol * mean, 0.0003):
        return False
    lit = [v for v in vals if v[0] > 0]
    return all(max(v[i] for v in lit) - min(v[i] for v in lit) <= 0.003 for i in (1, 2)) if lit else True


def measure(display_type, min_reads, ccmx=None, agree=0.0):
    """Average of HCFR's low-light number of readings; with `agree` > 0 it stops early, from the second reading on,
    once the readings agree (readings_agree)."""
    first = read_meter(display_type, ccmx)
    want = max(min_reads, adapt_reads(first[0]))
    vals = [first]
    while len(vals) < want:
        vals.append(read_meter(display_type, ccmx))
        if agree > 0 and len(vals) >= max(2, min_reads) and readings_agree(vals, agree):
            break
    n = len(vals)
    Y = sum(v[0] for v in vals) / n
    # Chromaticity from the readings that had light (black reads 0,0).
    lit = [v for v in vals if v[0] > 0]
    x = sum(v[1] for v in lit) / len(lit) if lit else 0.0
    y = sum(v[2] for v in lit) / len(lit) if lit else 0.0
    sd = math.sqrt(sum((v[0] - Y) ** 2 for v in vals) / n)
    return Y, x, y, sd, n


# ---------------------------------------------------------------- white balance search (per-channel codes)
D65 = "0.3127,0.3290"
# Input codes the search solves by default: from the lowest step the meter resolves to ~100 nits (code 520).
SEARCH_CODES = ("31,35,40,47,52,56,64,75,85,99,120,139,153,176,193,218,254,284,307,340,365,402,450,520")
UV_TOL, Y_TOL = 0.002, 0.03  # a search point "hits" within these (Delta u'v'; luminance, as a log ratio)


def xyz_of(Y, x, y):
    return (x / y * Y, Y, (1 - x - y) / y * Y) if Y > 0 and y > 0 else (0.0, 0.0, 0.0)


def duv(x, y, white):
    """CIE 1976 u'v' distance between xy and the white point xy."""
    def uv(x, y):
        d = -2 * x + 12 * y + 3
        return 4 * x / d, 9 * y / d
    if y <= 0:
        return float("inf")
    (u, v), (uw, vw) = uv(x, y), uv(*white)
    return math.hypot(u - uw, v - vw)


def search_cost(res, T, white, raised_weight):
    """How far a reading is from (T nits, white): colour in u'v', luminance in log, too bright weighs more
    (BevelTipDrip 2026-11-18: slightly crushed black is better than raised)."""
    Y, x, y = res[:3]
    if Y <= 0:
        return float("inf")
    lr = math.log(Y / T)
    w = raised_weight if lr > 0 else 1.0
    return (duv(x, y, white) / UV_TOL) ** 2 + (w * lr / Y_TOL) ** 2


def solve3(J, v):
    """x with J x = v (3x3, Cramer), or None if singular."""
    def det(m):
        return (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1]) - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
                + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))
    d = det(J)
    if abs(d) < 1e-18:
        return None
    out = []
    for c in range(3):
        m = [row[:] for row in J]
        for r in range(3):
            m[r][c] = v[r]
        out.append(det(m) / d)
    return out


def rgb_search(take, T, start, white, args, log):
    """Find the per-channel 10-bit codes whose light is closest to T nits at the white point.

    From a grey start, it measures each channel raised by a few codes (the step doubles until the change is
    above the meter's noise) to get how X, Y, Z move per code, then takes Newton steps toward the target XYZ,
    rounded to whole codes and limited to --search-max-step per channel, re-measuring the slopes at each new
    point. It stops when a point is within UV_TOL / Y_TOL, when a step repeats a point, or after --search-iters.
    Returns (best codes, best reading, number of readings)."""
    seen = {}

    def m(p):
        p = tuple(min(max(int(c), 0), 1023) for c in p)
        if p not in seen:
            seen[p] = take(("rgb",) + p)
            log(p, seen[p])
        return p, seen[p]

    def slopes(p, r):
        base, cols = xyz_of(*r[:3]), []
        for ch in range(3):
            k = args.search_step
            while True:
                q = list(p)
                q[ch] += k
                q, rq = m(q)
                d = [(a - b) / k for a, b in zip(xyz_of(*rq[:3]), base)]
                # Large enough to be above the meter's noise (1% of the light), or give up at 32 codes.
                if sum(abs(v) for v in d) * k > 0.01 * max(sum(base), sum(xyz_of(T, *white))) or k >= 32:
                    break
                k *= 2
            cols.append(d)
        return [[cols[c][row] for c in range(3)] for row in range(3)]

    target = xyz_of(T, *white)
    p, r = m((start, start, start))
    J = None
    for _ in range(args.search_iters):
        if search_cost(r, T, white, args.raised_weight) <= 1.0 or r[0] <= 0:
            break
        if J is None:  # measured at the start, and again after a step that made things worse
            J = slopes(p, r)
        delta = solve3(J, [t - b for t, b in zip(target, xyz_of(*r[:3]))])
        if delta is None:
            break
        lim = args.search_max_step
        q = tuple(min(max(int(round(a + max(-lim, min(lim, dd)))), 0), 1023) for a, dd in zip(p, delta))
        if q in seen:
            break
        q, rq = m(q)
        if search_cost(rq, T, white, args.raised_weight) > search_cost(r, T, white, args.raised_weight):
            J = None
        p, r = q, rq
    best = min(seen, key=lambda k: search_cost(seen[k], T, white, args.raised_weight))
    return best, seen[best], len(seen)


# ---------------------------------------------------------------- patch sources
class SdrWindow:
    """Full-screen tkinter window with a centred patch of an 8-bit grey (Windows HDR off)."""

    def __init__(self, area):
        import tkinter as tk
        self.area = area
        self.root = tk.Tk()
        self.root.configure(bg="black", cursor="none")
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)
        self.cv = tk.Canvas(self.root, bg="black", highlightthickness=0)
        self.cv.pack(fill="both", expand=True)
        self.rect = None
        self.abort = threading.Event()
        self.root.bind("<Escape>", lambda e: self.abort.set())
        self.q = queue.Queue()
        self._closing = False
        self.root.after(30, self._pump)

    def _pump(self):
        try:
            while True:
                self.q.get_nowait()()
        except queue.Empty:
            pass
        if self._closing:
            self.root.destroy()
            return
        self.root.after(20, self._pump)

    def show(self, level):
        done = threading.Event()

        def _do():
            w, h = self.root.winfo_width(), self.root.winfo_height()
            side = math.sqrt(self.area)
            pw, ph = int(w * side), int(h * side)
            if self.rect is None:
                self.rect = self.cv.create_rectangle(0, 0, 1, 1, width=0)
            self.cv.coords(self.rect, (w - pw) // 2, (h - ph) // 2, (w + pw) // 2, (h + ph) // 2)
            self.cv.itemconfig(self.rect, fill="#%02x%02x%02x" % (level, level, level))
            self.root.update_idletasks()
            self.root.after(100, done.set)  # a few frames on screen

        self.q.put(_do)
        if not done.wait(10):
            raise RuntimeError("patch window did not respond")

    def run_ui(self, worker):
        threading.Thread(target=worker, daemon=True).start()
        self.root.mainloop()

    def close(self):
        self._closing = True


class HdrGenerator:
    """hdr10_patchgen.exe: native HDR10 swapchain, PQ codes sent unchanged (Windows HDR on)."""

    def __init__(self, area, composed=False):
        if not os.path.exists(HDRGEN):
            raise RuntimeError(f"{HDRGEN} not found; build it with hdrgen/build.ps1")
        self.area = area
        self.abort = threading.Event()
        self.p = subprocess.Popen([HDRGEN] + (["--composed"] if composed else []), stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        line = self.p.stdout.readline().strip()
        if not line.startswith("READY"):
            self.p.kill()
            raise RuntimeError(f"HDR generator: {line or 'no reply'}")
        print("HDR generator:", line)

    def show(self, level):
        """level: nits (float), ('code', n) for an exact 10-bit PQ code, or ('rgb', r, g, b) for separate 10-bit
        codes per channel."""
        if self.p.poll() is not None:  # Esc in the generator window closes it
            self.abort.set()
            raise KeyboardInterrupt
        if isinstance(level, tuple) and level[0] == "rgb":
            self.p.stdin.write(f"C {int(level[1])} {int(level[2])} {int(level[3])} {self.area}\n")
        elif isinstance(level, tuple):
            self.p.stdin.write(f"P {level[1] / 1023!r} {self.area}\n")
        else:
            self.p.stdin.write(f"N {level!r} {self.area}\n")
        self.p.stdin.flush()
        line = self.p.stdout.readline().strip()
        if not line.startswith("OK"):
            self.abort.set()
            raise KeyboardInterrupt

    def run_ui(self, worker):
        worker()

    def close(self):
        try:
            if self.p.poll() is None:
                self.p.stdin.write("Q\n")
                self.p.stdin.flush()
                self.p.wait(5)
        except Exception:
            self.p.kill()


# ---------------------------------------------------------------- run
def data_path(outdir, label, valid):
    """research/docs/data naming: nearblack-<label>[-INVALID]-<YYYY-MM-DD>[-n].csv, never overwriting a file."""
    label = re.sub(r"[^a-z0-9.]+", "-", label.lower()).strip("-")
    base = f"nearblack-{label}" + ("" if valid else "-INVALID") + datetime.now().strftime("-%Y-%m-%d")
    path, n = os.path.join(outdir, base + ".csv"), 2
    while os.path.exists(path):
        path, n = os.path.join(outdir, f"{base}-{n}.csv"), n + 1
    return path


CSV_HEADER = ["run", "mode", "requested", "code", "target_cdm2", "Y_cdm2", "Y_sd", "x", "y", "reads", "r", "g", "b"]


def run(args, src):
    rows, ramp, mon, saved_vcp = [], None, None, {}
    os.makedirs(args.outdir, exist_ok=True)
    hdr = args.mode == "hdr"
    ref_level = 100 if hdr else 255
    valid = True
    csv_path = None

    def save(extra=()):
        """Rewrite the CSV with every row so far (after each patch), so a stopped run keeps its data."""
        nonlocal csv_path
        if not rows and not extra:
            return
        if csv_path is None:
            csv_path = data_path(args.outdir, args.label or args.mode, True)
        with open(csv_path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(CSV_HEADER)
            w.writerows(list(rows) + list(extra))

    try:
        if not hdr:
            ramp = GammaRamp()
            ramp.set_linear()

        def take(level, settle=None):
            if src.abort.is_set():
                raise KeyboardInterrupt
            src.show(level)
            time.sleep(args.settle if settle is None else settle)
            return measure(args.display_type, args.reads, args.ccmx, args.agree)

        # Pre-flight: the meter must see a plausible reference before the sweep (screen on, meter on the patch).
        ref0 = take(ref_level, settle=3.0)[0]
        lo, hi = (50, 200) if hdr else (20, 1000)
        print(f"Reference {ref_level}{' nits' if hdr else ''}: {ref0:.2f} cd/m2")
        if not lo <= ref0 <= hi and args.diagnostic:
            print(f"  (reference outside {lo}-{hi}; continuing: --diagnostic)")
        elif not lo <= ref0 <= hi:
            raise RuntimeError(f"reference read {ref0:.2f} cd/m2, expected {lo}-{hi}: is the meter on the patch "
                               "and the screen on?")

        def sweep(tag, levels):
            print(f"\n[{tag}]")
            res = {}
            for i, lvl in enumerate(levels):
                if i and i % REF_EVERY == 0:
                    r = take(ref_level, settle=1.0)[0]
                    print(f"  (reference {r:.2f} cd/m2, {r / ref0 - 1:+.1%} vs start)", flush=True)
                res[lvl] = take(lvl)
                name = f"code {lvl[1]}" if isinstance(lvl, tuple) else f"{lvl:g}"
                print(f"  {name:>9}: {res[lvl][0]:.5f} cd/m2  ({res[lvl][4]} reads)", flush=True)
                save(rows_for(tag, res))
            report(tag, res)

        def rows_for(tag, res):
            """CSV rows for a sweep's readings: HDR targets are the exact luminance of the code sent; SDR targets
            follow --gamma from the measured white (255)."""
            out = []
            white = res[255][0] if not hdr and 255 in res else float("nan")
            for lvl, (Y, x, y, sd, n) in res.items():
                if not hdr:
                    out.append([tag, "sdr", lvl, lvl, white * (lvl / 255.0) ** args.gamma, Y, sd, x, y, n, lvl, lvl, lvl])
                    continue
                if isinstance(lvl, tuple):
                    code = lvl[1]
                    tgt = nits_from_pq(code / 1023)
                    lvl = round(tgt, 5)
                else:
                    code, tgt = pq10(lvl)
                out.append([tag, "hdr", lvl, code, tgt, Y, sd, x, y, n, code, code, code])
            return out

        def report(tag, res):
            new = rows_for(tag, res)
            rows.extend(new)
            save()
            if hdr:
                print(f"\n[{tag}]  HDR10 PQ, absolute targets")
                print(f"{'asked':>7} {'code':>5} {'target':>9} {'measured':>9} {'ratio':>6} {'sd':>7} {'x':>6} {'y':>6}")
            else:
                white = res[255][0] if 255 in res else float("nan")
                print(f"\n[{tag}]  SDR, gamma {args.gamma} target from measured white {white:.2f} cd/m2")
                print(f"{'code':>5} {'target':>9} {'measured':>9} {'ratio':>6} {'sd':>7} {'x':>6} {'y':>6}")
            for _, _, lvl, code, tgt, Y, sd, x, y, *_ in new:
                ratio = Y / tgt if tgt > 0 else float("nan")
                first = f"{lvl:>7g} {code:>5}" if hdr else f"{code:>5}"
                print(f"{first} {tgt:>9.5f} {Y:>9.5f} {ratio:>6.2f} {sd:>7.5f} {x:>6.4f} {y:>6.4f}")

        if args.search:
            if not hdr:
                raise RuntimeError("--search is for --mode hdr")
            start_of = None
            if args.response:
                import build_mhc2  # same folder; its fit of a grey run gives the luminance-correct start
                resp = build_mhc2.Response(build_mhc2.load_response(args.response, 0.008))
                start_of = lambda T: resp.inverse(T)
            white = tuple(float(v) for v in args.white.split(","))
            codes = [int(c) for c in args.search_codes.split(",")]
            print(f"\n[search] D65 target xy {white[0]:.4f}/{white[1]:.4f}, {len(codes)} input codes, "
                  f"too-bright errors x{args.raised_weight:g}")
            summary, since_ref = [], 0
            for code in codes:
                if since_ref >= REF_EVERY:
                    r = take(ref_level, settle=1.0)[0]
                    print(f"  (reference {r:.2f} cd/m2, {r / ref0 - 1:+.1%} vs start)", flush=True)
                    since_ref = 0
                T = nits_from_pq(code / 1023)
                s = start_of(T) if start_of else None
                start = int(round(s)) if s is not None else code

                def log(p, res, code=code, T=T):
                    Y, x, y, sd, n = res
                    print(f"  in {code:>4}  rgb {p[0]:>4} {p[1]:>4} {p[2]:>4}: Y {Y:.5f} ({Y / T:.2f}x)  "
                          f"xy {x:.4f}/{y:.4f}  duv {duv(x, y, white):.4f}", flush=True)
                    rows.append([f"search_{code}", "hdr", code, code, T, Y, sd, x, y, n] + list(p))
                    save()

                best, res, count = rgb_search(take, T, start, white, args, log)
                since_ref += count
                Y, x, y, sd, n = res
                rows.append(["best", "hdr", code, code, T, Y, sd, x, y, n] + list(best))
                save()
                summary.append((code, T, best, Y, x, y))
            print(f"\n[search]  best per input code (target D65 {white[0]:.4f}/{white[1]:.4f})")
            print(f"{'in':>5} {'target':>9} {'r':>5} {'g':>5} {'b':>5} {'measured':>9} {'ratio':>6} {'x':>6} {'y':>6} "
                  f"{'duv':>6}")
            for code, T, b, Y, x, y in summary:
                print(f"{code:>5} {T:>9.5f} {b[0]:>5} {b[1]:>5} {b[2]:>5} {Y:>9.5f} {Y / T:>6.2f} {x:>6.4f} "
                      f"{y:>6.4f} {duv(x, y, white):>6.4f}")

        if args.levels:
            levels = [float(v) if hdr else int(v) for v in args.levels.split(",")]
        elif args.dense:
            if not hdr:
                raise RuntimeError("--dense is for --mode hdr")
            levels = [("code", c) for c in HDR_DENSE_CODES]
        else:
            levels = HDR_LEVELS if hdr else SDR_LEVELS
        if not args.search:
            sweep(args.label or "baseline", levels)

        steps = args.ddc_steps or ([{c: v for c in BLACK_VCPS} for v in args.ddc_sweep] if args.ddc_sweep else None)
        if steps:
            mon = open_monitor(args.monitor)
            vcps = sorted({c for s in steps for c in s})
            for c in vcps:
                cur, mx = vcp_get(mon, c)
                bad = [s[c] for s in steps if c in s and not 0 <= s[c] <= mx]
                if bad:
                    raise RuntimeError(f"VCP {c:02X} value {bad[0]} is outside the monitor's 0..{mx}")
                saved_vcp[c] = cur
            print("\nSaved DDC/CI: " + ", ".join(f"{DDC_VCPS[c]} {saved_vcp[c]}" for c in vcps))
            if args.ddc_levels:
                ddc_levels = [float(v) if hdr else int(v) for v in args.ddc_levels.split(",")]
            else:
                ddc_levels = HDR_SWEEP if hdr else SDR_SWEEP
            for step in steps:
                for c, v in step.items():
                    vcp_set(mon, c, v)
                tag = "ddc_" + "_".join(f"{c:02X}={vcp_get(mon, c)[0]}" for c in vcps)
                print(f"\nDDC/CI -> {tag} (readback)")
                time.sleep(2.0)
                sweep(tag, ddc_levels)
            # Back to the saved values before the end reference, so the drift check compares like with like.
            restore_vcps(mon, saved_vcp)
            time.sleep(2.0)

        # Drift check: the same reference again at the end.
        ref1 = take(ref_level, settle=2.0)[0]
        drift = ref1 / ref0 - 1
        valid = abs(drift) <= 0.05
        print(f"\nReference at end: {ref1:.2f} cd/m2 ({drift:+.1%} vs start)"
              + ("" if valid else "  ** RUN INVALID: display output changed during the run **"))
    except KeyboardInterrupt:
        print("\nAborted.")
    except Exception as e:
        print(f"\nERROR: {e}")
    finally:
        if mon is not None and saved_vcp:
            restore_vcps(mon, saved_vcp)  # aborted or failed mid-sweep
        if mon is not None:
            dxva2.DestroyPhysicalMonitor(mon)
        if ramp is not None:
            ramp.restore()
        if rows:
            save()
            if not valid:
                bad = data_path(args.outdir, args.label or args.mode, False)
                os.replace(csv_path, bad)
                csv_path = bad
            print(f"\nSaved {csv_path}")
        src.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=["sdr", "hdr"], required=True)
    ap.add_argument("--label", default="",
                    help="test ID and setting, lower case with hyphens (e.g. t-nb10-peak1000-dense); names the CSV")
    ap.add_argument("--dense", action="store_true",
                    help="hdr: code-by-code sweep through the near-black onset (~110 patches, ~25 min), for the "
                         "correction profile")
    ap.add_argument("--composed", action="store_true",
                    help="hdr: window 2 px short of full screen, so Windows composes it (no independent flip)")
    ap.add_argument("--diagnostic", action="store_true",
                    help="don't stop when the reference reads out of range (for test profiles that change it)")
    ap.add_argument("--levels", help="custom comma list (hdr: nits, sdr: 0-255 codes) for quick spot checks")
    ap.add_argument("--gamma", type=float, default=2.2, help="SDR target gamma (default 2.2)")
    ap.add_argument("--reads", type=int, default=1,
                    help="minimum readings per level; HCFR's Adapt rule adds more below 10 cd/m2 (up to 5)")
    ap.add_argument("--agree", type=float, default=0.01,
                    help="stop a level's readings early, from the second on, once they agree within this share of "
                         "Y (and 0.003 in xy); 0 = always take HCFR's full count (default 0.01)")
    ap.add_argument("--settle", type=float, default=0.5, help="seconds between patch and reading")
    ap.add_argument("--area", type=float, default=0.1, help="patch area as share of the screen (HCFR: 0.1)")
    ap.add_argument("--display-type", default="o", help="spotread -y display type (default 'o' = OLED)")
    ap.add_argument("--ccmx", default=DEFAULT_CCMX if os.path.exists(DEFAULT_CCMX) else None,
                    help="meter correction .ccmx/.ccss (default: HCFR's AW3225QF ccmx; '' for none)")
    ddc = ap.add_mutually_exclusive_group()
    ddc.add_argument("--ddc-sweep", type=lambda s: [int(x) for x in s.split(",")],
                     help="comma list of DDC black-level values to test on all three channels, e.g. 50,48,46,44,52")
    ddc.add_argument("--ddc-steps", type=parse_ddc_steps,
                     help="DDC/CI settings to measure in turn, ';' between steps, hex VCP=value, e.g. "
                          "'16=96;16=100,1A=96;1A=100' (gain 16/18/1A, black level 6C/6E/70); each step keeps the "
                          "values it does not name; everything is restored before the end reference")
    ap.add_argument("--ddc-levels", help="comma list measured at each DDC step (default: a short sweep)")
    ap.add_argument("--search", action="store_true",
                    help="hdr: for each --search-codes input, search the per-channel codes that give its PQ "
                         "luminance at --white (run it with an identity / uncorrected HDR profile)")
    ap.add_argument("--search-codes", default=SEARCH_CODES, help="comma list of 10-bit input codes to solve")
    ap.add_argument("--response", help="grey run CSV (dense) whose fit gives each search's luminance-correct start")
    ap.add_argument("--white", default=D65, help="target white point x,y (default D65 0.3127,0.3290)")
    ap.add_argument("--raised-weight", type=float, default=2.0,
                    help="how much more a too-bright luminance error counts than a too-dark one (default 2)")
    ap.add_argument("--search-iters", type=int, default=4, help="Newton steps per input code (default 4)")
    ap.add_argument("--search-step", type=int, default=2, help="first per-channel probe step in codes (default 2)")
    ap.add_argument("--search-max-step", type=int, default=12, help="largest change per channel per step (codes)")
    ap.add_argument("--monitor", default="AW3225QF", help="substring of the monitor name for DDC/CI")
    ap.add_argument("--outdir", default=DATA_DIR, help="where the CSV goes (default: research/docs/data)")
    args = ap.parse_args()
    if not os.path.exists(SPOTREAD):
        sys.exit(f"spotread not found at {SPOTREAD}: see research/docs/building-and-tools.md")
    if args.ddc_sweep and any(not 0 <= v <= 100 for v in args.ddc_sweep):
        sys.exit("Keep --ddc-sweep values within 0..100")

    # Keep the display awake for the whole run (the generator does the same for itself).
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000002 | 0x00000001)
    src = HdrGenerator(args.area, args.composed) if args.mode == "hdr" else SdrWindow(args.area)
    src.run_ui(lambda: run(args, src))


if __name__ == "__main__":
    main()
