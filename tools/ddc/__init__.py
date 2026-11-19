"""DDC/CI for Plascord: read any VCP code of a monitor, write whitelisted ones safely (Q-20).

    from ddc import open_backend, SafeDdc, scan
    with open_backend() as be:                 # dxva2 on Windows; open_backend("fake") for an in-memory monitor
        ddc = SafeDdc(be, be.find("AW3225QF"))
        print(ddc.get(0x6C))                   # VcpReply(current=50, maximum=255, vcp_type=1)
        with ddc.preserve([0x6C, 0x6E, 0x70]): # saved now, restored on leaving the block by any exit
            ddc.set(0x6C, 48)                  # never list, whitelist, 0..max check, write, read back
        result = scan(be, ddc.index)           # read only: every code 00-FF, against the capabilities string

Writing to a real display needs a named person's go first (research/docs/START-HERE.md, Rules).
Design, safety rules and open questions: research/docs/plan-ddc-module.md. CLI: python -m ddc --help (from tools/).
Standard library only, Python 3.8+.
"""
from .backend import (VCP_NAMES, Backend, DdcError, MonitorInfo, VcpReply, open_backend, parse_vcp_code,
                      vcp_name)
from .caps import Capabilities, parse_capabilities
from .mccs import MCCS_NAMES, mccs_name
from .safety import (DEFAULT_WRITE_WHITELIST, NEVER_WRITE, ReadbackMismatch, RestoreFailed, SafeDdc,
                     WriteRefused)
from .scan import ScanResult, ScanRow, scan

__all__ = ["VCP_NAMES", "Backend", "DdcError", "MonitorInfo", "VcpReply", "open_backend", "parse_vcp_code",
           "vcp_name", "Capabilities", "parse_capabilities", "DEFAULT_WRITE_WHITELIST", "NEVER_WRITE",
           "ReadbackMismatch", "RestoreFailed", "SafeDdc", "WriteRefused", "scan", "ScanResult", "ScanRow",
           "MCCS_NAMES", "mccs_name"]
