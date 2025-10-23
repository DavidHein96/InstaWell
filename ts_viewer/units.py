import re

_unit_re = re.compile(r"\s*([0-9]*\.?[0-9]+)\s*([mun]M)?\s*$", re.I)


def to_uM(s: str) -> float:
    """Convert '10 mM' / '500 nM' / '12 uM' / '5' → µM (float)."""
    s = str(s)
    m = _unit_re.match(s)
    if not m:
        return float(s.strip())
    val = float(m.group(1))
    unit = (m.group(2) or "").lower()
    if unit == "mm":
        return val * 1000.0
    if unit == "nm":
        return val / 1000.0
    # 'um' or no unit
    return val
