"""Command line for the DDC/CI package. Run from tools/:

    python -m ddc list                              # monitors DDC/CI can reach
    python -m ddc caps [--raw]                      # what the monitor says it supports
    python -m ddc get 10 12 6C                      # read VCP codes (hex): current and max
    python -m ddc scan --csv FILE --json FILE       # read every code 00-FF (read only), compare with caps
    python -m ddc display --display aw3225qf        # what the AW3225QF display module knows (no monitor needed)
    python -m ddc set 6C 48                         # dry run: checks and prints, writes nothing
    python -m ddc set 6C 48 --yes                   # write, then read back (only with a person's go)
    python -m ddc set 14 5 --allow 14 --yes         # a code beyond the whitelist: --allow names it (and a go)

Options on every command: --monitor TEXT (substring of the description or device) or --index N, needed when more
than one monitor is connected; --backend auto|windows|fake (fake = an in-memory demo monitor, no hardware);
--display auto|none|KEY (the display module, ddc/displays: names, value meanings, its own never codes; `set`
always applies the never codes of the module the monitor's description matches).

Writing a DDC/CI value to a display needs a named person's explicit go first (research/docs/START-HERE.md, Rules).
`set` writes only codes in the whitelist (ddc/safety.py) or named with --allow, never a code on the never-write
list (no option overrides it), only within the monitor's 0..max, and reads back; if the write fails or reads back
another value, it writes the old value back.
Exit status: 0 ok, 1 a DDC/CI error, 2 refused or bad arguments.
"""
import argparse
import os
import sys

from .backend import DdcError, open_backend, parse_vcp_code, vcp_name
from . import displays
from .caps import parse_capabilities
from .safety import DEFAULT_WRITE_WHITELIST, NEVER_WRITE, RestoreFailed, SafeDdc, WriteRefused
from .scan import MIN_INTERVAL, scan, table, write_csv, write_json


def _code(text):
    try:
        return parse_vcp_code(text)
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e))


def _code_list(text):
    codes = [_code(t) for t in str(text).split(",") if t.strip()]
    if not codes:
        raise argparse.ArgumentTypeError("no VCP codes given")
    return codes


def build_parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--backend", default="auto", choices=("auto", "windows", "fake"),
                        help="auto = dxva2 on Windows; fake = an in-memory demo monitor (default auto)")
    pick = common.add_mutually_exclusive_group()
    pick.add_argument("--monitor", help="substring of the monitor's description or device, e.g. AW3225QF")
    pick.add_argument("--index", type=int, help="the monitor's index from 'list'")
    common.add_argument("--display", default="auto", metavar="auto|none|KEY",
                        help="display module (ddc/displays): auto = found from the monitor's description or "
                             "capabilities model; none = MCCS names only; or a key, e.g. aw3225qf (default auto)")

    ap = argparse.ArgumentParser(prog="python -m ddc", description="Read and (carefully) write monitor VCP codes "
                                 "over DDC/CI.", epilog="Writes need a person's go first: START-HERE.md, Rules.")
    sub = ap.add_subparsers(dest="cmd")
    sub.required = True
    sub.add_parser("list", parents=[common], help="monitors DDC/CI can reach")
    p = sub.add_parser("caps", parents=[common], help="the monitor's capabilities string, parsed")
    p.add_argument("--raw", action="store_true", help="print the string as the monitor sent it")
    p = sub.add_parser("get", parents=[common], help="read VCP codes (hex)")
    p.add_argument("codes", nargs="+", type=_code, metavar="VCP")
    p = sub.add_parser("scan", parents=[common], help="read every VCP code 00-FF (Get only, never Set) and "
                       "compare with the capabilities string; codes that reply but are not listed are hidden-setting "
                       "candidates")
    p.add_argument("codes", nargs="*", type=_code, metavar="VCP", help="only these codes (default: 00 to FF)")
    p.add_argument("--interval", type=float, default=MIN_INTERVAL,
                   help="seconds between requests, at least %.2f (MCCS timing; default %.2f)"
                        % (MIN_INTERVAL, MIN_INTERVAL))
    p.add_argument("--all", action="store_true", help="print every code, not only those that reply or are listed")
    p.add_argument("--csv", metavar="FILE", help="also write one row per code to FILE (never overwritten)")
    p.add_argument("--json", metavar="FILE", help="also write the whole result to FILE (never overwritten)")
    sub.add_parser("display", parents=[common], help="what the display module knows: codes, safety classes, "
                   "sources (with --display KEY it needs no monitor)")
    p = sub.add_parser("set", parents=[common], help="write one whitelisted VCP code (dry run unless --yes)")
    p.add_argument("code", type=_code, metavar="VCP")
    p.add_argument("value", type=int, help="decimal value, 0..the monitor's max")
    p.add_argument("--yes", action="store_true",
                   help="really write it (only after a person's go for this write: START-HERE.md, Rules)")
    p.add_argument("--allow", type=_code_list, default=[], metavar="VCP[,VCP...]",
                   help="also allow these codes (hex, comma-separated) for this one call; codes on the never-write "
                        "list stay refused")
    return ap


def _pick(backend, args):
    return backend.find(args.index if args.index is not None else args.monitor)


def _module(be, index, args, model=""):
    """The display module for this monitor (--display), or None."""
    if args.display == "none":
        return None
    if args.display != "auto":
        mod = displays.by_key(args.display)
        if mod is None:
            raise WriteRefused("no display module %r (known: aw3225qf)" % args.display)
        return mod
    desc = [m.description for m in be.monitors() if m.index == index]
    return displays.for_monitor(desc[0] if desc else "", model)


def _never(be, index, args):
    """Never codes of every display module that applies: the one --display names AND the one the monitor's
    description matches. --display none or another key never removes a matching module's never codes."""
    never = {}
    desc = [m.description for m in be.monitors() if m.index == index]
    for mod in (displays.for_monitor(desc[0] if desc else ""), _module(be, index, args)):
        if mod is not None:
            never.update(mod.never())
    return never


def _name(code, mod):
    if mod is not None and code in mod.controls:
        return mod.controls[code].name
    return vcp_name(code)


def _meaning(code, value, mod):
    if mod is None or code not in mod.controls or not mod.controls[code].values:
        return ""
    values = mod.controls[code].values
    meaning = values.get(value, values.get(value & 0xFF) if code == 0x60 else None)  # 60: low byte (vdu84)
    return "  (%s)" % meaning if meaning else ""


def _list(be, args):
    mons = be.monitors()
    for device, why in be.skipped:
        print("skipped %s: %s" % (device, why), file=sys.stderr)
    if not mons:
        print("No monitors found for DDC/CI (a display that is off, asleep or disconnected has none).")
        return 1
    for m in mons:
        print("%d  %s  %s" % (m.index, m.description, m.device))
    return 0


def _caps(be, args):
    raw = be.capabilities(_pick(be, args))
    if args.raw:
        print(raw)
        return 0
    c = parse_capabilities(raw)
    mod = _module(be, _pick(be, args), args, c.model)
    wl = DEFAULT_WRITE_WHITELIST
    never = dict(NEVER_WRITE)
    never.update(mod.never() if mod else {})
    print("model %s, type %s, MCCS %s%s" % (c.model or "?", c.type or "?", c.mccs_ver or "?",
                                            "; display module %s" % mod.model if mod else ""))
    for code, values in sorted(c.vcp.items()):
        vals = "" if values is None else "  values " + " ".join("%02X" % v for v in values)
        mark = "  [writable here]" if code in wl else "  [never written]" if code in never else ""
        line = "  %02X  %-34s%s%s" % (code, _name(code, mod), mark, vals)
        print(line.rstrip())
    if not c.vcp:
        print("  (no vcp() list found; --raw shows the string)")
    return 0


def _get(be, args):
    index = _pick(be, args)
    ddc, mod, status = SafeDdc(be, index), _module(be, index, args), 0
    for code in args.codes:
        try:
            r = ddc.get(code)
            print("VCP %02X %-30s %d of %d%s" % (code, _name(code, mod), r.current, r.maximum,
                                                 _meaning(code, r.current, mod)))
        except DdcError as e:
            print("VCP %02X %-30s ERROR %s" % (code, _name(code, mod), e), file=sys.stderr)
            status = 1
    return status


def _display(be, args):
    if be is None:
        mod = displays.by_key(args.display)
    else:
        mod = _module(be, _pick(be, args), args)
    if mod is None:
        print("No display module for this monitor (known: aw3225qf); MCCS names only.")
        return 0
    print("%s display module (tools/ddc/displays/%s.py). Safety: safe = default whitelist; ask first = only with "
          "--allow and a go; never = refused always. caps = listed in a capabilities string of this model "
          "(source in the module)." % (mod.model, mod.key))
    for code, ctl in sorted(mod.controls.items()):
        caps = "?" if ctl.in_caps is None else "caps" if ctl.in_caps else "NOT in caps"
        print("  %02X  %-34s %-9s %-11s %s" % (code, ctl.name, ctl.safety, caps,
                                               ctl.confirmed or "not confirmed on this monitor"))
    for note in mod.notes:
        print("- " + note)
    return 0


def _scan(be, args):
    if args.interval < MIN_INTERVAL:
        raise WriteRefused("--interval %.3f is below %.2f s (MCCS timing)" % (args.interval, MIN_INTERVAL))
    for path in (args.csv, args.json):
        if path and os.path.exists(path):
            raise WriteRefused("%s exists; a scan never overwrites a file, give it a new name" % path)
    index = _pick(be, args)
    codes = args.codes or range(0x100)
    tty = sys.stderr.isatty()
    progress = (lambda c: print("\rreading VCP %02X" % c, end="", file=sys.stderr, flush=True)) if tty else None
    result = scan(be, index, codes, args.interval, progress=progress)
    if tty:
        print("\r" + " " * 20 + "\r", end="", file=sys.stderr)
    mod = _module(be, index, args, result.caps.model if result.caps else "")
    if mod is not None:  # the module's names for the codes it knows (manufacturer codes above all)
        result = result._replace(rows=[r._replace(name=_name(r.code, mod)) for r in result.rows])
    print(table(result, args.all))
    if mod is not None:
        print("Display module: %s (python -m ddc display --display %s)" % (mod.model, mod.key))
    if args.csv:
        write_csv(result, args.csv)
        print("CSV: %s" % args.csv)
    if args.json:
        write_json(result, args.json)
        print("JSON: %s" % args.json)
    return 0


def _set(be, args):
    index = _pick(be, args)
    whitelist = dict(DEFAULT_WRITE_WHITELIST)
    extra = [c for c in args.allow if c not in whitelist]
    whitelist.update({c: vcp_name(c) for c in args.allow})
    # A never-list code (the core's or a display module's) in --allow -> WriteRefused, exit 2
    ddc = SafeDdc(be, index, whitelist=whitelist, never=_never(be, index, args))
    if extra:
        print("Allowed for this call beyond the whitelist: VCP %s" % ", ".join("%02X" % c for c in extra))
    r = ddc.check_write(args.code, args.value)  # WriteRefused -> exit 2, nothing written
    print("VCP %02X (%s): now %d of %d; set to %d" % (args.code, vcp_name(args.code), r.current, r.maximum,
                                                       args.value))
    allow = " --allow %02X" % args.code if args.code in extra else ""
    if not args.yes:
        print("Dry run: nothing written. Add --yes to write, only with a person's go for this write "
              "(START-HERE.md, Rules).")
        return 0
    try:
        got = ddc.set(args.code, args.value)
    except DdcError as e:
        # The write failed or read back another value: put the value read just before back (with a read back).
        failures = ddc.restore({args.code: r.current})
        if failures:
            raise RestoreFailed(failures) from e
        print("Write failed; VCP %02X is back at %d (read back)." % (args.code, r.current), file=sys.stderr)
        raise
    print("Wrote %d; read back %d. To put it back: python -m ddc set %02X %d --index %d%s --yes"
          % (args.value, got, args.code, r.current, index, allow))
    return 0


COMMANDS = {"list": _list, "caps": _caps, "get": _get, "scan": _scan, "display": _display, "set": _set}


def main(argv=None, backend=None):
    """argv: the arguments (default sys.argv[1:]). backend: use this backend instead of opening one (tests);
    it is not closed here."""
    args = build_parser().parse_args(argv)
    if args.cmd == "display" and args.display not in ("auto", "none") and backend is None:
        return _display(None, args)  # a named module needs no monitor
    try:
        be = backend if backend is not None else open_backend(args.backend)
    except DdcError as e:
        print("ERROR %s" % e, file=sys.stderr)
        return 1
    try:
        return COMMANDS[args.cmd](be, args)
    except WriteRefused as e:
        print("REFUSED %s (nothing written)" % e, file=sys.stderr)
        return 2
    except DdcError as e:
        print("ERROR %s" % e, file=sys.stderr)
        return 1
    finally:
        if backend is None:
            be.close()
