import logging

import numpy as np
from scipy.optimize import curve_fit
from scipy.stats import t

logger = logging.getLogger(__name__)


# ---------- Helpers ----------


def four_pl_log10x(x, bottom, top, logEC50, hill):
    logx = np.log10(x)
    return bottom + (top - bottom) / (1.0 + 10.0 ** ((logEC50 - logx) * hill))


def _guess_hill_sign(x_lin: np.ndarray, y: np.ndarray) -> float:
    """
    Sign guess for Hill coefficient based on linear trend of y vs log10(x).
    Returns +1.0 for positive slope (agonist-like), -1.0 for negative slope.
    Falls back to +1.0 if insufficient data.
    """
    x = np.asarray(x_lin, float)
    y = np.asarray(y, float)

    m = (x > 0) & np.isfinite(x) & np.isfinite(y)
    x, y = x[m], y[m]
    if x.size < 3 or np.allclose(y, y.mean()):
        return 1.0  # safe default

    logx = np.log10(x)
    try:
        # simple unweighted least squares; robust enough for a sign check
        slope, _ = np.polyfit(logx, y, 1)
        return 1.0 if slope >= 0 else -1.0
    except Exception:
        return 1.0


def fit_4pl(
    x_lin: np.ndarray,
    y: np.ndarray,
    sigma: np.ndarray | None = None,
    hill_bounds: tuple[float, float] = (-10.0, 10.0),
    maxfev: int = 20000,
):
    """
    Prism-style 4PL fit (x in log10, parameterized by logEC50) with Hill sign
    initialized from the y vs log10(x) slope.
    """
    x = np.asarray(x_lin, float)
    y = np.asarray(y, float)

    m = (x > 0) & np.isfinite(x) & np.isfinite(y)
    x, y = x[m], y[m]
    if np.unique(x).size < 4:
        return None, None

    bottom = float(np.nanmin(y))
    top = float(np.nanmax(y))
    logEC50 = float(np.median(np.log10(x)))
    hill_init = _guess_hill_sign(x, y)  # <-- NEW

    p0 = [bottom, top, logEC50, hill_init]
    lb = [-np.inf, -np.inf, -np.inf, hill_bounds[0]]
    ub = [np.inf, np.inf, np.inf, hill_bounds[1]]

    try:
        params, pcov = curve_fit(
            four_pl_log10x,
            x,
            y,
            p0=p0,
            bounds=(lb, ub),
            sigma=sigma,
            absolute_sigma=bool(sigma is not None),
            maxfev=maxfev,
        )
        return params, pcov
    except Exception:
        return None, None


def sigma_weight(y: np.ndarray) -> np.ndarray | None:
    # 1/y^2 with epsilon to avoid blow-ups near zero
    if y.size == 0:
        return None
    eps = max(1e-9, float(np.nanmin(np.abs(y[y != 0]))) if np.any(y != 0) else 1.0)
    return np.clip(np.abs(y), eps, None)


def param_ci_from_pcov(params: np.ndarray, pcov: np.ndarray, dof: int, alpha=0.05):
    if pcov is None or not np.all(np.isfinite(pcov)):
        return None
    se = np.sqrt(np.clip(np.diag(pcov), 0, np.inf))
    tval = t.ppf(1 - alpha / 2, df=max(dof, 1))
    lo = params - tval * se
    hi = params + tval * se
    return se, lo, hi
