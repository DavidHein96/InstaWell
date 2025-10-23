import json
from typing import Tuple


def make_group_key(conc_uM: float, ligand: str, protein: str, buffer: str) -> str:
    return json.dumps((float(conc_uM), str(ligand), str(protein), str(buffer)))


def parse_group_key(key_str: str) -> Tuple[float, str, str, str]:
    c, l, p, b = json.loads(key_str)
    return float(c), l, p, b
