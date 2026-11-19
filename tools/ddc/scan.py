"""Read-only discovery: ask the monitor for every VCP code (Get VCP Feature only) and compare with its capabilities.

`scan()` never writes: it calls only Backend.capabilities and Backend.get_vcp (a test proves it on a backend whose
set_vcp raises). In MCCS, Get VCP Feature (opcode 01) and Set VCP Feature (03) are different requests, so reading a
code such as 04 (restore factory defaults) asks for its value and cannot trigger it.

Timing: MCCS wants at least 40-50 ms between the end of one DDC/CI exchange and the next request; scan() waits
`interval` (default 0.05 s, not less) before every request after the first, the capabilities request included.

A code is a hidden-setting candidate when it replies but the capabilities string does not list it. A reply of
0 of 0 is flagged: some monitors answer that way for codes they do not support.
"""
import csv
import json
import time
from typing import Callable, Dict, Iterable, List, NamedTuple, Optional

from .backend import Backend, DdcError
from .caps import Capabilities, parse_capabilities
from .mccs import WRITE_ONLY, mccs_name

MIN_INTERVAL = 0.05  # seconds between DDC/CI requests (MCCS: 40-50 ms)

VCP_TYPES = {0: "momentary", 1: "set parameter"}  # dxva2's MC_VCP_CODE_TYPE


class ScanRow(NamedTuple):
    code: int
    name: str                     # MCCS name, or the display module's when it has one
    replied: bool
    vcp_type: Optional[int]
    current: Optional[int]
    maximum: Optional[int]
    in_caps: Optional[bool]       # None: no capabilities string to compare with
    caps_values: Optional[List[int]]
    error: str

    @property
    def hidden(self) -> bool:
        """Replies, but the capabilities string (which we have) does not list it."""
        return self.replied and self.in_caps is False

    @property
    def note(self) -> str:
        notes = []
        if self.hidden:
            notes.append("hidden: replies, not in caps")
        if self.in_caps and not self.replied:
            notes.append("in caps, no reply")
        if self.replied and self.current == 0 and self.maximum == 0:
            notes.append("0 of 0: may be unsupported")
        if self.code in WRITE_ONLY:
            notes.append("write-only in MCCS")
        return "; ".join(notes)


class ScanResult(NamedTuple):
    monitor: str
    caps: Optional[Capabilities]
    caps_error: str
    rows: List[ScanRow]
    interval: float
    started: str                  # local time, ISO 8601

    @property
    def replied(self) -> List[ScanRow]:
        return [r for r in self.rows if r.replied]

    @property
    def hidden(self) -> List[ScanRow]:
        return [r for r in self.rows if r.hidden]


def scan(backend: Backend, index: int, codes: Iterable[int] = range(0x100), interval: float = MIN_INTERVAL,
         names: Optional[Dict[int, str]] = None, sleep: Optional[Callable[[float], None]] = None,
         progress: Optional[Callable[[int], None]] = None) -> ScanResult:
    """Read the capabilities string, then Get VCP Feature for each code, `interval` seconds apart. Never writes.
    names: display-specific names that override the MCCS ones. sleep: default backend.wait (time.sleep; the fake
    backend records it instead). progress(code) is called before each read."""
    if interval < MIN_INTERVAL:
        raise ValueError("interval %.3f s is below the %.0f ms MCCS needs between requests"
                         % (interval, MIN_INTERVAL * 1000))
    names = names or {}
    sleep = sleep or backend.wait
    started = time.strftime("%Y-%m-%dT%H:%M:%S")
    mon = [m for m in backend.monitors() if m.index == index]
    caps, caps_error = None, ""
    try:
        caps = parse_capabilities(backend.capabilities(index))
        if not caps.vcp:
            caps_error = "the capabilities string lists no vcp() codes"
    except DdcError as e:
        caps_error = str(e)
    rows = []
    for code in codes:
        sleep(interval)  # after the capabilities request too
        if progress:
            progress(code)
        in_caps = None if caps is None or not caps.vcp else code in caps.vcp
        caps_values = caps.vcp.get(code) if in_caps else None
        name = names.get(code) or mccs_name(code)
        try:
            r = backend.get_vcp(index, code)
            rows.append(ScanRow(code, name, True, r.vcp_type, r.current, r.maximum, in_caps, caps_values, ""))
        except DdcError as e:
            rows.append(ScanRow(code, name, False, None, None, None, in_caps, caps_values, str(e)))
    return ScanResult(mon[0].description if mon else "monitor %d" % index, caps, caps_error, rows, interval,
                      started)


def _fmt(v) -> str:
    return "" if v is None else str(v)


def table(result: ScanResult, all_rows: bool = False) -> str:
    """Text table: codes that replied or that the capabilities list (every code with all_rows), then a summary."""
    out = ["%-4s %-42s %-5s %-13s %7s %7s %-5s %s" % ("VCP", "name", "reply", "type", "current", "max", "caps",
                                                        "note")]
    for r in result.rows:
        if not (all_rows or r.replied or r.in_caps):
            continue
        caps = "?" if r.in_caps is None else "yes" if r.in_caps else "no"
        out.append(("%02X   %-42s %-5s %-13s %7s %7s %-5s %s" % (
            r.code, r.name[:42], "yes" if r.replied else "no", VCP_TYPES.get(r.vcp_type, _fmt(r.vcp_type)),
            _fmt(r.current), _fmt(r.maximum), caps, r.note)).rstrip())
    out.append("")
    out.append(summary(result))
    return "\n".join(out)


def summary(result: ScanResult) -> str:
    c = result.caps
    lines = ["%s: %d codes read, %d replied; capabilities: %s" % (
        result.monitor, len(result.rows), len(result.replied),
        "%d codes listed (model %s, MCCS %s)" % (len(c.vcp), c.model or "?", c.mccs_ver or "?")
        if c is not None and c.vcp else "not available (%s)" % result.caps_error)]
    hidden = result.hidden
    if hidden:
        lines.append("Hidden-setting candidates (reply, not in caps): " + " ".join("%02X" % r.code for r in hidden))
    silent = [r for r in result.rows if r.in_caps and not r.replied]
    if silent:
        lines.append("In caps but no reply: " + " ".join("%02X" % r.code for r in silent))
    return "\n".join(lines)


CSV_COLUMNS = ["vcp", "name", "replied", "vcp_type", "current", "maximum", "in_caps", "caps_values", "hidden",
               "note", "error"]


def _row_dict(r: ScanRow) -> dict:
    return {"vcp": "%02X" % r.code, "name": r.name, "replied": r.replied, "vcp_type": r.vcp_type,
            "current": r.current, "maximum": r.maximum, "in_caps": r.in_caps,
            "caps_values": None if r.caps_values is None else ["%02X" % v for v in r.caps_values],
            "hidden": r.hidden, "note": r.note, "error": r.error}


def write_csv(result: ScanResult, path: str) -> None:
    """One row per code. Refuses to overwrite a file (a scan is evidence; give each run its own name)."""
    with open(path, "x", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        w.writeheader()
        for r in result.rows:
            d = _row_dict(r)
            d["caps_values"] = "" if d["caps_values"] is None else " ".join(d["caps_values"])
            w.writerow({k: "" if v is None else v for k, v in d.items()})


def to_json(result: ScanResult) -> dict:
    c = result.caps
    return {"monitor": result.monitor, "started": result.started, "interval_s": result.interval,
            "capabilities": None if c is None else {"raw": c.raw, "model": c.model, "type": c.type,
                                                    "mccs_ver": c.mccs_ver, "vcp": ["%02X" % v for v in sorted(c.vcp)]},
            "capabilities_error": result.caps_error,
            "hidden": ["%02X" % r.code for r in result.hidden],
            "codes": [_row_dict(r) for r in result.rows]}


def write_json(result: ScanResult, path: str) -> None:
    """Refuses to overwrite a file, like write_csv."""
    with open(path, "x", encoding="utf-8") as f:
        json.dump(to_json(result), f, indent=1)
        f.write("\n")
