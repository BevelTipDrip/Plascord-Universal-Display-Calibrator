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

Usage:
  python build_mhc2.py --csv ../research/docs/data/<dense run>.csv --name "AW3225QF TB400 near-black fix"
  python build_mhc2.py --csv ../research/docs/data/<peak1000 run>.csv --name "AW3225QF Peak1000 near-black fix" --peak 1000
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
            if r.get("mode") != "hdr":
                continue
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
    d = open(path, "rb").read()
    n = struct.unpack_from(">I", d, 128)[0]
    entries = [struct.unpack_from(">4sII", d, 132 + 12 * i) for i in range(n)]
    return d[:128], [(s, d[o:o + z], o) for s, o, z in entries]


def mluc(text):
    s = text.encode("utf-16-be")
    return b"mluc" + b"\0" * 4 + struct.pack(">II", 1, 12) + b"enUS" + struct.pack(">II", len(s), 28) + s


def mhc2(old, lut, peak):
    _, _, size, minL, oldpeak, moff, *_ = struct.unpack_from(">4s4sIiiIIII", old)
    matrix = old[moff:moff + 48]
    if peak is None:
        peak = oldpeak / 65536
    hdr_len, mat_len = 36, 48
    lut_len = 8 + 4 * len(lut)
    l0 = hdr_len + mat_len
    body = (b"MHC2" + b"\0" * 4 + struct.pack(">I", len(lut)) + struct.pack(">i", minL) + s15f16(peak)
            + struct.pack(">IIII", hdr_len, l0, l0 + lut_len, l0 + 2 * lut_len) + matrix)
    one = b"sf32" + b"\0" * 4 + b"".join(s15f16(v) for v in lut)
    return body + one * 3, peak


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
    ap.add_argument("--csv", required=True, help="nearblack_probe.py HDR CSV (dense run preferred)")
    ap.add_argument("--name", required=True, help="profile description (shown in Windows Settings)")
    ap.add_argument("--base", default=DEFAULT_BASE, help="HDR profile to copy matrix / tags from")
    ap.add_argument("--peak", type=float, help="peak luminance to report (default: the base profile's)")
    ap.add_argument("--floor", type=float, default=0.008, help="lowest reading trusted from the meter (cd/m2)")
    ap.add_argument("--blend-start", type=float, default=20.0, help="nits where the correction starts fading out")
    ap.add_argument("--blend-end", type=float, default=30.0, help="nits from which the LUT is identity")
    ap.add_argument("--no-snap", action="store_true",
                    help="keep fractional output codes (the GPU truncates them; snapping is the default)")
    ap.add_argument("--out", help="output .icc (default: ../profiles/<name>.icc)")
    args = ap.parse_args()

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
            data, peak = mhc2(data, lut, args.peak)
        elif sig == b"desc":
            data, off = mluc(args.name), "desc"
        elif sig == b"lumi" and args.peak:
            data, off = b"XYZ " + b"\0" * 4 + s15f16(args.peak) * 3, "lumi"
        new_tags.append((sig, data, off))
    out = args.out or os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "profiles",
                                                    args.name + ".icc"))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    write_icc(header, new_tags, out)
    print(f"Wrote {out}  (peak {peak:.0f} nits, LUT {N} entries)")

    print(f"\n{'in code':>7} {'target':>9} {'uncorrected':>11} {'out code':>8} {'predicted':>9}")
    for c in (20, 27, 31, 35, 40, 47, 56, 64, 75, 85, 99, 120, 153, 193, 254, 307, 365, 402, 520):
        o = lut[c] * 1023
        T = nits_from_pq(c / 1023)
        sent = math.floor(o)  # what the pipeline sends (truncation)
        print(f"{c:>7} {T:>9.4f} {resp(c):>11.4f} {o:>8.2f} {resp(sent):>9.4f}")


if __name__ == "__main__":
    main()
