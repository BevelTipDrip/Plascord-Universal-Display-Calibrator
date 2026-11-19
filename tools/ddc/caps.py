"""Parse an MCCS capabilities string, e.g.

    (prot(monitor)type(LCD)model(AW3225QF)cmds(01 02 03 07 0C E3 F3)vcp(02 04 10 12 14(05 08 0B) 16 18 1A 60(0F 11)
     DC(00 02 03))mccs_ver(2.1))

into its model, type, MCCS version, command list, and VCP codes with their allowed values (None when the string
lists none: a continuous control). Lenient, as real monitors' strings often are: a missing outer pair of brackets,
spaces before '(', codes run together without spaces ('1012' -> 10, 12), and unknown groups are tolerated.
"""
import string
from typing import Dict, List, NamedTuple, Optional

HEX = set(string.hexdigits)


class Capabilities(NamedTuple):
    raw: str
    model: str
    type: str
    mccs_ver: str
    cmds: List[int]
    vcp: Dict[int, Optional[List[int]]]
    groups: Dict[str, str]  # every top-level group by lower-case name, as text


def _match(s: str, i: int) -> int:
    """Index of the ')' closing the '(' at s[i]; len(s) if it is never closed."""
    depth = 0
    for k in range(i, len(s)):
        if s[k] == "(":
            depth += 1
        elif s[k] == ")":
            depth -= 1
            if depth == 0:
                return k
    return len(s)


def _groups(s: str) -> Dict[str, str]:
    out, i, n = {}, 0, len(s)
    while i < n:
        j = i
        while j < n and (s[j].isalnum() or s[j] in "_-"):
            j += 1
        name = s[i:j]
        k = j
        while k < n and s[k] == " ":
            k += 1
        if name and k < n and s[k] == "(":
            end = _match(s, k)
            out.setdefault(name.lower(), s[k + 1:end])
            i = end + 1
        else:
            i = max(j, i + 1)
    return out


def _hex_list(s: str) -> List[int]:
    out = []
    for tok in s.split():
        if tok and all(ch in HEX for ch in tok):
            if len(tok) > 2 and len(tok) % 2 == 0:
                out += [int(tok[p:p + 2], 16) for p in range(0, len(tok), 2)]
            else:
                out.append(int(tok, 16))
    return out


def _vcp(s: str) -> Dict[int, Optional[List[int]]]:
    codes = {}  # type: Dict[int, Optional[List[int]]]
    i, n = 0, len(s)
    while i < n:
        if s[i] not in HEX:
            i += 1
            continue
        j = i
        while j < n and s[j] in HEX:
            j += 1
        tok = s[i:j]
        pairs = [tok[p:p + 2] for p in range(0, len(tok), 2)] if len(tok) > 2 and len(tok) % 2 == 0 else [tok]
        for p in pairs:
            codes[int(p, 16) & 0xFF] = None
        k = j
        while k < n and s[k] == " ":
            k += 1
        if k < n and s[k] == "(":
            end = _match(s, k)
            codes[int(pairs[-1], 16) & 0xFF] = _hex_list(s[k + 1:end])
            j = end + 1
        i = j
    return codes


def parse_capabilities(raw: str) -> Capabilities:
    s = (raw or "").strip().rstrip("\x00")
    if s.startswith("(") and _match(s, 0) >= len(s) - 1:
        s = s[1:_match(s, 0)]
    g = _groups(s)
    return Capabilities(raw=raw or "", model=g.get("model", ""), type=g.get("type", ""),
                        mccs_ver=g.get("mccs_ver", ""), cmds=_hex_list(g.get("cmds", "")),
                        vcp=_vcp(g.get("vcp", "")), groups=g)
