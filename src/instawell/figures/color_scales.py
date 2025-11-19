import logging
from typing import Callable, Dict, List, Optional, Tuple, cast

import pandas as pd
from plotly.colors import get_colorscale, sample_colorscale

logger = logging.getLogger(__name__)


def build_discrete_colormap_from_continuous(
    df: pd.DataFrame,
    label_col: str,
    *,
    colorscale: str = "YlGnBu",
    numeric_cast: Optional[Callable[[str], float]] = None,
    vmin: Optional[float] = None,
    vmax: Optional[float] = None,
    descending: bool = False,
) -> Tuple[Dict[str, str], List[str]]:
    """
    Derive a categorical color map by sampling a continuous colorscale using
    numeric values computed from `label_col`. Returns (color_map, ordered_labels).
    """
    # Work on a shallow copy to avoid mutating caller df
    tmp = df[[label_col]].copy()

    # 1) numeric projection
    if numeric_cast is not None:
        tmp["__num__"] = tmp[label_col].apply(numeric_cast)
    else:
        logger.warning(
            "No numeric_cast provided; attempting best-effort numeric conversion for color mapping."
        )
        tmp["__num__"] = pd.to_numeric(tmp[label_col], errors="coerce")

    # 2) unique labels with their numeric value
    cats = tmp[[label_col, "__num__"]].drop_duplicates()

    # 3) sort labels by numeric value (NaNs last)
    cats = cats.sort_values("__num__", ascending=not descending, na_position="last")
    ordered_labels: List[str] = cats[label_col].astype(str).tolist()
    nums: List[Optional[float]] = cast(List[Optional[float]], cats["__num__"].tolist())

    # 4) normalize to [0,1]
    finite = [x for x in nums if x is not None and pd.notna(x)]
    logger.debug("Numeric values for color mapping: %s", nums)
    if finite:
        vmin_local: float = min(finite) if vmin is None else vmin
        vmax_local: float = max(finite) if vmax is None else vmax
        if vmin_local == vmax_local:
            t_vals: List[float] = [0.5] * len(nums)
        else:
            span = float(vmax_local - vmin_local)
            t_vals = [
                float((x - vmin_local) / span) if (x is not None and pd.notna(x)) else 0.5
                for x in nums
            ]
    else:
        # all NaN → middle of the scale
        t_vals = [0.5] * len(nums)

    if descending:
        t_vals = [1.0 - t for t in t_vals]

    # 5) sample colors (Pylance sometimes infers mixed types; cast to List[str])
    scale = get_colorscale(colorscale)
    sampled = cast(List[str], sample_colorscale(scale, t_vals))  # rgba strings
    color_map: Dict[str, str] = {lab: col for lab, col in zip(ordered_labels, sampled, strict=True)}
    return color_map, ordered_labels
