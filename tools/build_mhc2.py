"""
Builds a Windows HDR (MHC2) colour profile whose 1D LUT corrects the measured near-black response.

In HDR mode Windows programs the MHC2 tag into the GPU's display pipeline: the 3x4 matrix, then the per-channel
1D "regamma" LUT applied to the ST 2084 (PQ) signal sent to the display. This script:
  1. reads a nearblack_probe.py CSV (PQ code -> measured cd/m2),
  2. fits a monotonic response M(code) (log-interpolated between measured codes),
  3. for every input code c finds the output code o with M(o) = target(c) (the exact PQ luminance of c),
     leaving c unchanged below the meter's reliable floor and blending back to identity between --blend-start and
     --blend-end nits, where the panel already tracks,
  4. copies the base profile (by default the current Windows HDR Calibration profile: its matrix, luminance and
     other tags) and replaces only the MHC2 LUTs, the peak luminance (optional) and the description.

With --anchors (Q-1) it instead builds three per-channel LUTs that move the grey scale to D65: at each anchor the
measured code triple with the lowest dE ITP (ITU-R BT.2124; too bright weighted x2), non-decreasing per channel;
between anchors per-channel code offsets on top of --start-profile's codes, interpolated in log luminance.

Usage:
  python build_mhc2.py --csv ../research/docs/data/<dense run>.csv --name "AW3225QF TB400 near-black fix"
  python build_mhc2.py --csv ../research/docs/data/<peak1000 run>.csv --name "AW3225QF Peak1000 near-black fix" --peak 1000
  python build_mhc2.py --anchors ../research/docs/data/nearblack-t-nt2-*.csv ../research/docs/data/nearblack-t-nt3-*.csv --name "AW3225QF TB400 grey D65 v3"
Install: Settings > System > Display > Color management > Add profile (HDR), then Set profile.
"""
import argparse, csv, hashlib, math, os, struct, sys

M1, M2, C1, C2, C3 = 0.1593017578125, 78.84375, 0.8359375, 18.8515625, 18.6875
COLOR_DIR = r"C:\Windows\System32\spool\drivers\color"
DEFAULT_BASE = os.path.join(COLOR_DIR, "HDR Calibrated Profile 11-18-2026 11563.icc")
N = 1024  # LUT entries: one per 10-bit code


def nits_from_pq(e):
    ep = max(e, 0.0) ** (1 / M2)
    return 10000.0 * (max(ep - C1, 0.0) / (C2 - C3 * ep)) ** (1 / M1)


def pq_from_nits(n):
    yp = (max(n, 0.0) / 10000.0) ** M1
    return ((C1 + C2 * yp) / (1 + C3 * yp)) ** M2


# ---------------------------------------------------------------- measured response
def load_response(path, floor):
    pts = {}
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            if r.get("mode") != "hdr" or r.get("run", "").startswith("ddc_"):
                continue  # DDC steps measure the panel at other monitor settings
            if r.get("r") and not r["r"] == r["g"] == r["b"] == r["code"]:
                continue  # per-channel search patches are not the grey response
            code, Y = int(r["code"]), float(r["Y_cdm2"])
            pts.setdefault(code, []).append(Y)
    pts = sorted((c, sum(v) / len(v)) for c, v in pts.items())
    usable = [(c, Y) for c, Y in pts if Y >= floor]
    if len(usable) < 5:
        sys.exit("not enough readings above the floor")
    # Monotone (non-decreasing) fit: pool adjacent violators, weighted equally.
    blocks = []
    for c, Y in usable:
        blocks.append([Y, 1, [c]])
        while len(blocks) > 1 and blocks[-2][0] > blocks[-1][0]:
            y2, n2, c2 = blocks.pop()
            y1, n1, c1 = blocks.pop()
            blocks.append([(y1 * n1 + y2 * n2) / (n1 + n2), n1 + n2, c1 + c2])
    fit = [(c, b[0]) for b in blocks for c in b[2]]
    # Strictly increasing for inversion: nudge equal neighbours apart by a hair.
    out = []
    for c, Y in fit:
        if out and Y <= out[-1][1]:
            Y = out[-1][1] * 1.0001
        out.append((c, Y))
    return out


class Response:
    def __init__(self, pts):
        self.c = [p[0] for p in pts]
        self.ly = [math.log(p[1]) for p in pts]

    def __call__(self, code):
        c, ly = self.c, self.ly
        if code <= c[0]:
            return math.exp(ly[0])
        if code >= c[-1]:
            return math.exp(ly[-1])
        for i in range(1, len(c)):
            if code <= c[i]:
                t = (code - c[i - 1]) / (c[i] - c[i - 1])
                return math.exp(ly[i - 1] + t * (ly[i] - ly[i - 1]))

    def inverse(self, Y):
        """Fractional code with M(code) = Y, or None outside the measured range."""
        c, ly = self.c, self.ly
        if Y <= 0:
            return None
        l = math.log(Y)
        if l < ly[0] or l > ly[-1]:
            return None
        for i in range(1, len(c)):
            if l <= ly[i]:
                t = (l - ly[i - 1]) / (ly[i] - ly[i - 1])
                return c[i - 1] + t * (c[i] - c[i - 1])


def smoothstep(a, b, x):
    t = min(max((x - a) / (b - a), 0.0), 1.0)
    return t * t * (3 - 2 * t)


def snap_lut(lut, resp, blend_start):
    """The display pipeline truncates the LUT output to a whole 10-bit code (measured 2026-11-18: 40.87 -> 40).
    In the corrected range, pick the whole output code whose measured light is closest (in log) to the target,
    and store it as code + 0.25 so truncation and rounding both land on it."""
    out = list(lut)
    for i in range(N):
        T = nits_from_pq(i / 1023)
        o = lut[i] * 1023
        if T <= 0 or T >= blend_start or o <= resp.c[0]:
            continue
        lo, hi = math.floor(o), math.floor(o) + 1
        best = min((lo, hi), key=lambda k: abs(math.log(resp(k)) - math.log(T)))
        out[i] = (best + 0.25) / 1023
    for k in range(1, N):
        out[k] = max(out[k], out[k - 1])
    return out


def build_lut(resp, blend_start, blend_end):
    Ymin = math.exp(resp.ly[0])
    lut = [None] * N
    first = None  # first input whose target the measured response can reach
    for i in range(N):
        T = nits_from_pq(i / 1023)
        inv = resp.inverse(T)
        if inv is None:
            if T < Ymin:
                continue  # below the meter's reliable floor: filled by the ramp below
            inv = float(i)  # above the measured range
        if first is None:
            first = i
        w = smoothstep(blend_start, blend_end, T)
        lut[i] = (1 - w) * inv + w * i
    # Below the floor the panel's response is not measurable: ramp linearly from code 0 to the first solvable
    # point, so the curve stays continuous (no jump in output code).
    for i in range(first):
        lut[i] = lut[first] * i / first
    for k in range(1, N):  # never decreasing
        lut[k] = max(lut[k], lut[k - 1])
    print(f"  inputs 0-{first - 1} (targets under {Ymin:.4f} cd/m2, the lowest reliable reading) ramp to code "
          f"{lut[first]:.1f}; not verifiable with this meter")
    return [min(max(o / 1023.0, 0.0), 1.0) for o in lut]


# ---------------------------------------------------------------- ICC
def s15f16(v):
    return struct.pack(">i", int(round(v * 65536)))


def read_icc(path):
    with open(path, "rb") as f:
        d = f.read()
    n = struct.unpack_from(">I", d, 128)[0]
    entries = [struct.unpack_from(">4sII", d, 132 + 12 * i) for i in range(n)]
    return d[:128], [(s, d[o:o + z], o) for s, o, z in entries]


def mluc(text):
    s = text.encode("utf-16-be")
    return b"mluc" + b"\0" * 4 + struct.pack(">II", 1, 12) + b"enUS" + struct.pack(">II", len(s), 28) + s


IDENTITY_MATRIX = b"".join(s15f16(v) for v in (1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0))  # 3x4: no colour change


def mhc2(old, lut, peak, neutral=False):
    """The MHC2 tag with new LUTs: `lut` is one list (the same on all three channels) or three lists (R, G, B, the
    same length); the base's matrix, or identity if `neutral` (the Windows HDR Calibration matrix carries that app's
    saturation setting)."""
    _, _, size, minL, oldpeak, moff, *_ = struct.unpack_from(">4s4sIiiIIII", old)
    matrix = IDENTITY_MATRIX if neutral else old[moff:moff + 48]
    if peak is None:
        peak = oldpeak / 65536
    luts = lut if isinstance(lut[0], (list, tuple)) else (lut, lut, lut)
    if len(luts) != 3 or len({len(l) for l in luts}) != 1:
        raise ValueError("three LUTs of the same length are needed")
    n = len(luts[0])
    hdr_len, mat_len = 36, 48
    lut_len = 8 + 4 * n
    l0 = hdr_len + mat_len
    body = (b"MHC2" + b"\0" * 4 + struct.pack(">I", n) + struct.pack(">i", minL) + s15f16(peak)
            + struct.pack(">IIII", hdr_len, l0, l0 + lut_len, l0 + 2 * lut_len) + matrix)
    return body + b"".join(b"sf32" + b"\0" * 4 + b"".join(s15f16(v) for v in l) for l in luts), peak


def read_mhc2_luts(path):
    """The three MHC2 LUTs of a profile, as lists of floats (0..1)."""
    _, tags = read_icc(path)
    for sig, data, _ in tags:
        if sig == b"MHC2":
            n = struct.unpack_from(">I", data, 8)[0]
            offs = struct.unpack_from(">4I", data, 20)
            return [[struct.unpack_from(">i", data, o + 8 + 4 * k)[0] / 65536 for k in range(n)] for o in offs[1:]]
    sys.exit(f"{path}: no MHC2 tag")


# ---------------------------------------------------------------- anchors (Q-1): per-channel LUTs, grey to D65
D65 = (0.3127, 0.3290)
DEFAULT_START = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "profiles",
                                              "AW3225QF TB400 near-black fix v2.icc"))


def ictcp(Y, x, y):
    """ICtCp (ITU-R BT.2100) of absolute luminance Y (cd/m2) at chromaticity x, y."""
    X, Z = x * Y / y, (1 - x - y) * Y / y
    lms = (0.3593 * X + 0.6976 * Y - 0.0359 * Z, -0.1921 * X + 1.1005 * Y + 0.0754 * Z,
           0.0071 * X + 0.0748 * Y + 0.8433 * Z)
    L, M, S = (pq_from_nits(v) for v in lms)
    return 0.5 * L + 0.5 * M, (6610 * L - 13613 * M + 7003 * S) / 4096, (17933 * L - 17390 * M - 543 * S) / 4096


def delta_e_itp(a, b):
    """Delta E ITP (ITU-R BT.2124); 1 is about one just-noticeable difference."""
    return 720 * math.sqrt((a[0] - b[0]) ** 2 + (0.5 * (a[1] - b[1])) ** 2 + (a[2] - b[2]) ** 2)


def anchor_score(T, Y, x, y, raised_weight=2.0):
    """(penalised, total dE ITP, Y/T) of a reading against D65 at the target T. Penalised: the colour part and the
    luminance part of dE ITP combined, the luminance part times `raised_weight` when too bright (crush before raise,
    BevelTipDrip 2026-11-18)."""
    a, t = ictcp(Y, x, y), ictcp(T, *D65)
    colour = delta_e_itp((t[0], a[1], a[2]), t)
    lum = delta_e_itp((a[0], t[1], t[2]), t)
    return math.hypot(colour, lum * (raised_weight if Y > T else 1.0)), delta_e_itp(a, t), Y / T


def load_anchor_candidates(paths):
    """{anchor code: {(r, g, b): (target, Y, x, y, readings)}} from nearblack_probe.py --anchors CSVs: the rows of
    runs `anchor_<code>` (not `best`, `settle` or references), averaged per code triple."""
    acc = {}
    for path in paths:
        with open(path, newline="") as f:
            for r in csv.DictReader(f):
                if not r.get("run", "").startswith("anchor_") or not r.get("r"):
                    continue
                Y = float(r["Y_cdm2"] or 0)
                if Y <= 0:
                    continue
                key = (int(r["code"]), (int(r["r"]), int(r["g"]), int(r["b"])))
                acc.setdefault(key, []).append((float(r["target_cdm2"]), Y, float(r["x"]), float(r["y"])))
    out = {}
    for (code, rgb), v in acc.items():
        n = len(v)
        out.setdefault(code, {})[rgb] = (v[0][0], sum(e[1] for e in v) / n, sum(e[2] for e in v) / n,
                                         sum(e[3] for e in v) / n, n)
    return out


def pick_anchors(cands, raised_weight=2.0, monotone=True):
    """{anchor code: (r, g, b)} minimising the summed penalised score. With `monotone`, each channel's code never
    decreases from one anchor to the next (a dynamic programme over the measured triples); otherwise each anchor's
    best triple on its own."""
    codes = sorted(cands)
    score = {(k, c): anchor_score(*v[:4], raised_weight)[0] for k in codes for c, v in cands[k].items()}
    if not monotone:
        return {k: min(cands[k], key=lambda c: score[(k, c)]) for k in codes}
    best = {c: (score[(codes[0], c)], [c]) for c in cands[codes[0]]}
    for k in codes[1:]:
        nxt = {}
        for c in cands[k]:
            prev = [v for p, v in best.items() if all(c[i] >= p[i] for i in range(3))]
            if prev:
                tot, path = min(prev, key=lambda v: v[0])
                nxt[c] = (tot + score[(k, c)], path + [c])
        if not nxt:
            sys.exit(f"no measured triple at anchor {k} keeps every channel non-decreasing")
        best = nxt
    return dict(zip(codes, min(best.values(), key=lambda v: v[0])[1]))


def sent_codes(lut):
    """The whole codes the pipeline sends for each input (it truncates the LUT output, T-NB7)."""
    return [min(max(math.floor(v * 1023 + 1e-4), 0), 1023) for v in lut]


def anchor_output_codes(start_luts, picks, monotone=True):
    """Per-channel output codes for every input, from the start profile's sent codes and the anchor picks:
    - an input on the same start output step as an anchor (all three channels): that anchor's codes (near black,
      where the start profile is a staircase and an anchor was measured on each step);
    - below the first anchor (under the meter's floor): the start's codes, capped at the first anchor's;
    - between anchors: the start's codes plus per-channel offsets interpolated in log target luminance;
    - above the last anchor: the last anchor's offsets.
    With `monotone`, each channel is made non-decreasing afterwards."""
    sent = [sent_codes(l) for l in start_luts]
    anchors = sorted(picks)
    off = {a: [picks[a][c] - sent[c][a] for c in range(3)] for a in anchors}
    lt = {a: math.log(nits_from_pq(a / 1023)) for a in anchors}
    out = [[0] * N for _ in range(3)]
    for i in range(N):
        same = [a for a in anchors if all(sent[c][i] == sent[c][a] for c in range(3))]
        if same:
            a = min(same, key=lambda a: abs(a - i))
            codes = [sent[c][i] + off[a][c] for c in range(3)]
        elif i < anchors[0]:
            codes = [min(sent[c][i], picks[anchors[0]][c]) for c in range(3)]
        elif i > anchors[-1]:
            codes = [sent[c][i] + off[anchors[-1]][c] for c in range(3)]
        else:
            hi = next(a for a in anchors if a > i)
            lo = max(a for a in anchors if a < i)
            t = (math.log(nits_from_pq(i / 1023)) - lt[lo]) / (lt[hi] - lt[lo])
            codes = [sent[c][i] + round(off[lo][c] + t * (off[hi][c] - off[lo][c])) for c in range(3)]
        for c in range(3):
            out[c][i] = min(max(codes[c], 0), 1023)
    if monotone:
        for c in range(3):
            for i in range(1, N):
                out[c][i] = max(out[c][i], out[c][i - 1])
    return out


def codes_to_lut(codes):
    """LUT values that the truncating pipeline sends as exactly these codes: code + 0.25 (lut-snap); 0 stays 0 and
    1023 is 1.0."""
    return [0.0 if k == 0 else 1.0 if k >= 1023 else (k + 0.25) / 1023 for k in codes]


def write_icc(header, tags, path):
    # Lay tags out in order, keeping shared data shared (e.g. r/g/bTRC), 4-byte aligned.
    table_len = 4 + 12 * len(tags)
    pos = 128 + table_len
    blobs, placed, entries = [], {}, []
    for sig, data, key in tags:
        if key in placed:
            off = placed[key]
        else:
            pos += (-pos) % 4
            off = pos
            blobs.append((off, data))
            placed[key] = off
            pos += len(data)
        entries.append((sig, off, len(data)))
    total = pos + (-pos) % 4
    buf = bytearray(total)
    buf[:128] = header
    struct.pack_into(">I", buf, 0, total)
    struct.pack_into(">I", buf, 128, len(tags))
    for i, (sig, off, size) in enumerate(entries):
        struct.pack_into(">4sII", buf, 132 + 12 * i, sig, off, size)
    for off, data in blobs:
        buf[off:off + len(data)] = data
    # ICC v4 profile ID: MD5 with flags, rendering intent and the ID itself zeroed.
    tmp = bytearray(buf)
    tmp[44:48] = b"\0" * 4
    tmp[64:68] = b"\0" * 4
    tmp[84:100] = b"\0" * 16
    buf[84:100] = hashlib.md5(tmp).digest()
    with open(path, "wb") as f:
        f.write(buf)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", help="nearblack_probe.py HDR CSV (dense run preferred)")
    ap.add_argument("--identity-lut", action="store_true",
                    help="no correction: a 2-entry identity LUT, as Windows' HDR Calibration profiles have (with "
                         "--neutral: a profile that changes nothing, for measuring)")
    ap.add_argument("--neutral", action="store_true",
                    help="identity matrix instead of the base profile's (which carries its saturation setting)")
    ap.add_argument("--name", required=True, help="profile description (shown in Windows Settings)")
    ap.add_argument("--base", default=DEFAULT_BASE, help="HDR profile to copy matrix / tags from")
    ap.add_argument("--peak", type=float, help="peak luminance to report (default: the base profile's)")
    ap.add_argument("--floor", type=float, default=0.008, help="lowest reading trusted from the meter (cd/m2)")
    ap.add_argument("--blend-start", type=float, default=20.0, help="nits where the correction starts fading out")
    ap.add_argument("--blend-end", type=float, default=30.0, help="nits from which the LUT is identity")
    ap.add_argument("--no-snap", action="store_true",
                    help="keep fractional output codes (the GPU truncates them; snapping is the default)")
    ap.add_argument("--out", help="output .icc (default: ../profiles/<name>.icc)")
    ap.add_argument("--anchors", nargs="+", metavar="CSV",
                    help="nearblack_probe.py --anchors CSVs: per-channel LUTs that move the grey scale to D65 (Q-1), "
                         "built on --start-profile")
    ap.add_argument("--start-profile", default=DEFAULT_START,
                    help="profile the anchors were measured from (its sent codes are the base; default: v2)")
    ap.add_argument("--raised-weight", type=float, default=2.0,
                    help="anchor pick: weight on the luminance part of dE ITP when too bright (default 2)")
    ap.add_argument("--allow-non-monotone", action="store_true",
                    help="anchor pick: each anchor's best reading even if a channel's code then decreases (default: "
                         "non-decreasing per channel)")
    args = ap.parse_args()
    if sum((bool(args.csv), args.identity_lut, bool(args.anchors))) != 1:
        ap.error("give one of --csv (a near-black correction), --anchors (grey to D65) or --identity-lut (none)")

    resp = None
    picks = None
    if args.identity_lut:
        lut = [0.0, 1.0]
    elif args.anchors:
        cands = load_anchor_candidates(args.anchors)
        if not cands:
            sys.exit("no anchor_<code> readings in " + ", ".join(args.anchors))
        monotone = not args.allow_non_monotone
        picks = pick_anchors(cands, args.raised_weight, monotone)
        start = read_mhc2_luts(args.start_profile)
        codes = anchor_output_codes(start, picks, monotone)
        lut = [codes_to_lut(c) for c in codes]
    else:
        pts = load_response(args.csv, args.floor)
        resp = Response(pts)
        print(f"Response: {len(pts)} codes, {pts[0][0]}..{pts[-1][0]} ({pts[0][1]:.4f}..{pts[-1][1]:.1f} cd/m2)")
        lut = build_lut(resp, args.blend_start, args.blend_end)
        if not args.no_snap:
            lut = snap_lut(lut, resp, args.blend_start)

    header, tags = read_icc(args.base)
    new_tags, peak = [], None
    for sig, data, off in tags:
        if sig == b"MHC2":
            data, peak = mhc2(data, lut, args.peak, args.neutral)
        elif sig == b"desc":
            data, off = mluc(args.name), "desc"
        elif sig == b"lumi" and args.peak:
            data, off = b"XYZ " + b"\0" * 4 + s15f16(args.peak) * 3, "lumi"
        new_tags.append((sig, data, off))
    out = args.out or os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "profiles",
                                                    args.name + ".icc"))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    write_icc(header, new_tags, out)
    size = len(lut[0]) if isinstance(lut[0], list) else len(lut)
    print(f"Wrote {out}  (peak {peak:.0f} nits, LUT {size} entries, "
          f"{'identity' if args.neutral else 'base profile'} matrix)")
    if picks is not None:
        sent = sent_codes(start[0])
        print(f"\nAnchors ({'non-decreasing per channel' if monotone else 'each best on its own'}; dE ITP against "
              f"D65 at the PQ target, too bright x{args.raised_weight:g}):")
        print(f"{'in':>4} {'target':>8} {'start sends':>11} {'v3 sends':>13} {'Y/target':>8} {'dE ITP':>6} {'patches':>7}")
        for a in sorted(picks):
            T, Y, x, y, n = cands[a][picks[a]]
            _, tot, ratio = anchor_score(T, Y, x, y, args.raised_weight)
            print(f"{a:>4} {T:>8.4f} {sent[a]:>11} {'/'.join(str(codes[c][a]) for c in range(3)):>13} "
                  f"{ratio:>7.2f}x {tot:>6.1f} {n:>7}")
        print("\nBetween anchors the codes are interpolated (not measured); verify with a run before trusting them.")
        for c, ch in enumerate("RGB"):
            drops = sum(1 for i in range(1, N) if codes[c][i] < codes[c][i - 1])
            if drops:
                print(f"  {ch}: {drops} inputs where the output code decreases")
        return
    if resp is None:
        return

    print(f"\n{'in code':>7} {'target':>9} {'uncorrected':>11} {'out code':>8} {'predicted':>9}")
    for c in (20, 27, 31, 35, 40, 47, 56, 64, 75, 85, 99, 120, 153, 193, 254, 307, 365, 402, 520):
        o = lut[c] * 1023
        T = nits_from_pq(c / 1023)
        sent = math.floor(o)  # what the pipeline sends (truncation)
        print(f"{c:>7} {T:>9.4f} {resp(c):>11.4f} {o:>8.2f} {resp(sent):>9.4f}")


if __name__ == "__main__":
    main()
