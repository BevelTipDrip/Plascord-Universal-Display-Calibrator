"""The probe's `--ddc-steps` syntax, in the package, for when tools/nearblack_probe.py switches to it (plan D4).

parse_ddc_steps is the probe's function (tools/nearblack_probe.py, blob 221f64c) with the allowed codes as a
parameter: the same results and the same exceptions (argparse.ArgumentTypeError for an unlisted code or no steps,
ValueError for text that is not hex=decimal), checked against a table recorded from the probe
(tests/test_steps.py). Values are not range-checked here: the caller checks them against the monitor's max.
The probe is not switched yet: plan-ddc-module.md, "How the probe would adopt it".
"""
import argparse
from typing import Dict, Iterable, List

# The probe's DDC_VCPS: the only codes --ddc-steps may write (per-channel gain and black level). Narrower than
# safety.DEFAULT_WRITE_WHITELIST (no brightness 10 / contrast 12), on purpose: the probe's runs stay as they were.
PROBE_VCPS = {0x16: "red gain", 0x18: "green gain", 0x1A: "blue gain",
              0x6C: "red black", 0x6E: "green black", 0x70: "blue black"}


def parse_ddc_steps(text: str, codes: Iterable[int] = PROBE_VCPS) -> List[Dict[int, int]]:
    """'16=96;16=100,1A=96' -> [{0x16: 96}, {0x16: 100, 0x1A: 96}]. Each step changes only the codes it names;
    the others keep their value from the step before."""
    allowed = list(codes)
    steps = []
    for part in text.split(";"):
        step = {}
        for item in filter(None, (s.strip() for s in part.split(","))):
            code, _, value = item.partition("=")
            code, value = int(code, 16), int(value)
            if code not in allowed:
                raise argparse.ArgumentTypeError(f"VCP {code:02X} is not one of "
                                                 + ", ".join(f"{c:02X}" for c in allowed))
            step[code] = value
        if step:
            steps.append(step)
    if not steps:
        raise argparse.ArgumentTypeError("no DDC steps given")
    return steps
