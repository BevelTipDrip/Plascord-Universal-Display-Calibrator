"""Command line for the DDC/CI package. Run from tools/:

    python -m ddc list                              # monitors DDC/CI can reach
    python -m ddc caps [--raw]                      # what the monitor says it supports
    python -m ddc get 10 12 6C                      # read VCP codes (hex): current and max
    python -m ddc set 6C 48                         # dry run: checks and prints, writes nothing
    python -m ddc set 6C 48 --yes                   # write, then read back (only with a person's go)
    python -m ddc set 14 5 --allow 14 --yes         # a code beyond the whitelist: --allow names it (and a go)

Options on every command: --monitor TEXT (substring of the description or device) or --index N, needed when more
than one monitor is connected; --backend auto|windows|fake (fake = an in-memory demo monitor, no hardware).

Writing a DDC/CI value to a display needs a named person's explicit go first (research/docs/START-HERE.md, Rules).
`set` writes only codes in the whitelist (ddc/safety.py) or named with --allow, never a code on the never-write
list (no option overrides it), only within the monitor's 0..max, and reads back; if the write fails or reads back
another value, it writes the old value back.
Exit status: 0 ok, 1 a DDC/CI error, 2 refused or bad arguments.
"""
import argparse
import sys

from .backend import DdcError, open_backend, parse_vcp_code, vcp_name
from .caps import parse_capabilities
from .safety import DEFAULT_WRITE_WHITELIST, NEVER_WRITE, RestoreFailed, SafeDdc, WriteRefused


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

    ap = argparse.ArgumentParser(prog="python -m ddc", description="Read and (carefully) write monitor VCP codes "
                                 "over DDC/CI.", epilog="Writes need a person's go first: START-HERE.md, Rules.")
    sub = ap.add_subparsers(dest="cmd")
    sub.required = True
    sub.add_parser("list", parents=[common], help="monitors DDC/CI can reach")
    p = sub.add_parser("caps", parents=[common], help="the monitor's capabilities string, parsed")
    p.add_argument("--raw", action="store_true", help="print the string as the monitor sent it")
    p = sub.add_parser("get", parents=[common], help="read VCP codes (hex)")
    p.add_argument("codes", nargs="+", type=_code, metavar="VCP")
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
    wl = DEFAULT_WRITE_WHITELIST
    print("model %s, type %s, MCCS %s" % (c.model or "?", c.type or "?", c.mccs_ver or "?"))
    for code, values in sorted(c.vcp.items()):
        vals = "" if values is None else "  values " + " ".join("%02X" % v for v in values)
        mark = "  [writable here]" if code in wl else "  [never written]" if code in NEVER_WRITE else ""
        line = "  %02X  %-34s%s%s" % (code, vcp_name(code), mark, vals)
        print(line.rstrip())
    if not c.vcp:
        print("  (no vcp() list found; --raw shows the string)")
    return 0


def _get(be, args):
    ddc, status = SafeDdc(be, _pick(be, args)), 0
    for code in args.codes:
        try:
            r = ddc.get(code)
            print("VCP %02X %-30s %d of %d" % (code, vcp_name(code), r.current, r.maximum))
        except DdcError as e:
            print("VCP %02X %-30s ERROR %s" % (code, vcp_name(code), e), file=sys.stderr)
            status = 1
    return status


def _set(be, args):
    index = _pick(be, args)
    whitelist = dict(DEFAULT_WRITE_WHITELIST)
    extra = [c for c in args.allow if c not in whitelist]
    whitelist.update({c: vcp_name(c) for c in args.allow})
    ddc = SafeDdc(be, index, whitelist=whitelist)  # a never-list code in --allow -> WriteRefused, exit 2
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


COMMANDS = {"list": _list, "caps": _caps, "get": _get, "set": _set}


def main(argv=None, backend=None):
    """argv: the arguments (default sys.argv[1:]). backend: use this backend instead of opening one (tests);
    it is not closed here."""
    args = build_parser().parse_args(argv)
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
