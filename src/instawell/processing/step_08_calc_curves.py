from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

from instawell.core.exp_context import ExperimentContext
from instawell.core.steps import StepFiles
from instawell.utils.curve_fitting import fit_4pl, four_pl_log10x, param_ci_from_pcov, sigma_weight
from instawell.utils.logging_util import setup_experiment_logging
from instawell.utils.utils import convert_concentration_to_float

logger = logging.getLogger(__name__)


def _load_min_temps(ctx: ExperimentContext) -> pd.DataFrame:
    path = ctx.experiment_dir / StepFiles.MIN_TEMPERATURES_DATA.value
    if not path.exists():
        raise FileNotFoundError(f"Min temperatures data file not found: {path}")
    df = pd.read_csv(path)

    req = {"unqcond", "min_temperature", "concentration", *set(ctx.condition_fields)}
    missing = req - set(df.columns)
    if missing:
        raise ValueError(f"Missing required column(s): {sorted(missing)}")

    # numeric concentration column (keep original string too)
    df["conc_num"] = df["concentration"].apply(convert_concentration_to_float)
    return df


def calculate_curve_params(
    ctx: ExperimentContext,
    panel_by: Optional[list[str]] = None,
    weighting: str = "none",  # "none" or "1/y^2"
    alpha: float = 0.05,
) -> None:
    """
    Compute Prism-style 4PL fits on min-temperature data (Step 07) and save CSVs.

    Parameters
    ----------
    ctx : ExperimentContext
        Pipeline context with file locations and condition fields.
    panel_by : list[str] | None, optional
        Fields defining a panel (fit) group. Defaults to all ctx.condition_fields
        except "concentration". If empty after that, uses a single 'all' panel.
    weighting : {"none","1/y^2"}, optional
        Optional weighted least squares. "none" matches Prism default.
    alpha : float, optional
        Two-sided alpha for parameter confidence intervals (default 0.05 => 95% CI).

    Outputs
    -------
    curve_params.csv :
        One row per panel with Bottom, Top, logEC50, EC50, Hill, SEs, 95% CIs,
        RSS, RMSE, AIC, BIC, n, df, and weighting.
    curve_diagnostics.csv :
        One row per observation with observed value, model prediction (for x>0),
        and residual.

    Returns
    -------
    tuple[pd.DataFrame, pd.DataFrame]
        (params_df, diagnostics_df)
    """
    if ctx.log_to_file:
        setup_experiment_logging(
            experiment_dir=ctx.experiment_dir, filename="experiment.log", level=ctx.log_level
        )

    df = _load_min_temps(ctx)

    # panels
    if panel_by is None:
        panel_by = [f for f in ctx.condition_fields if f != "concentration"]
        if not panel_by:
            df["__panel__"] = "all"
            panel_by = ["__panel__"]

    params_rows: list[dict] = []
    diag_rows: list[dict] = []

    for gvals, g0 in df.groupby(panel_by, sort=False):
        panel_keys = (
            dict(zip(panel_by, gvals, strict=True))
            if isinstance(gvals, tuple)
            else {panel_by[0]: gvals}
        )

        # positive doses only for model domain
        g = g0[(g0["conc_num"] > 0) & np.isfinite(g0["min_temperature"])].copy()
        if g.empty or np.unique(g["conc_num"]).size < 4:  # Magic 4 is fine here b/c its a 4PL
            logger.info(f"Skipping panel {panel_keys}: insufficient positive-dose data.")
            continue

        # weighting
        sigma = None
        if weighting == "1/y^2":
            sigma = sigma_weight(g["min_temperature"].to_numpy())

        # fit
        params, pcov = fit_4pl(
            g["conc_num"].to_numpy(),
            g["min_temperature"].to_numpy(),
            sigma=sigma,
        )
        if params is None:
            logger.info(f"4PL fit failed in panel {panel_keys}.")
            continue

        bottom, top, logEC50, hill = params
        ec50 = 10**logEC50

        # diagnostics
        x = g["conc_num"].to_numpy()
        y = g["min_temperature"].to_numpy()
        yhat = four_pl_log10x(x, *params)
        resid = y - yhat
        rss = float(np.sum(resid**2))
        n = len(y)
        p = 4
        dfree = max(n - p, 1)
        rmse = float(np.sqrt(rss / dfree))
        aic = float(n * np.log(rss / n) + 2 * p)
        bic = float(n * np.log(rss / n) + p * np.log(n))

        # parameter SEs and CIs
        se, lo, hi = (None, None, None)
        ci_fields = {}
        if pcov is not None and np.all(np.isfinite(pcov)):
            out = param_ci_from_pcov(params, pcov, dof=dfree, alpha=alpha)
            if out is not None:
                se, lo, hi = out
                ci_fields = {
                    "SE_bottom": se[0],
                    "SE_top": se[1],
                    "SE_logEC50": se[2],
                    "SE_Hill": se[3],
                    "CI95_bottom_low": lo[0],
                    "CI95_bottom_high": hi[0],
                    "CI95_top_low": lo[1],
                    "CI95_top_high": hi[1],
                    "CI95_logEC50_low": lo[2],
                    "CI95_logEC50_high": hi[2],
                    "CI95_EC50_low": 10 ** lo[2],
                    "CI95_EC50_high": 10 ** hi[2],
                    "CI95_Hill_low": lo[3],
                    "CI95_Hill_high": hi[3],
                }

        params_rows.append(
            {
                **panel_keys,
                "bottom": bottom,
                "top": top,
                "logEC50": logEC50,
                "EC50": ec50,
                "Hill": hill,
                "n_points": n,
                "df": dfree,
                "rss": rss,
                "rmse": rmse,
                "aic": aic,
                "bic": bic,
                "weighting": weighting,
                **ci_fields,
            }
        )

        # diagnostics rows for all points in the panel (pred only for x>0)
        g0 = g0.copy()
        mpos = g0["conc_num"] > 0
        g0.loc[mpos, "pred"] = four_pl_log10x(g0.loc[mpos, "conc_num"].to_numpy(), *params)
        g0.loc[~mpos, "pred"] = np.nan
        g0["residual"] = g0["min_temperature"] - g0["pred"]
        for _, r in g0.iterrows():
            diag_rows.append(
                {
                    **panel_keys,
                    "concentration": r["conc_num"],
                    "min_temperature": r["min_temperature"],
                    "pred": r["pred"],
                    "residual": r["residual"],
                    "unqcond": r.get("unqcond"),
                }
            )

    params_df = pd.DataFrame(params_rows)
    diag_df = pd.DataFrame(diag_rows)

    params_out = ctx.experiment_dir / StepFiles.CURVE_PARAMS.value
    diag_out = ctx.experiment_dir / StepFiles.CURVE_DIAGNOSTICS.value

    params_df.to_csv(params_out, index=False)
    diag_df.to_csv(diag_out, index=False)
    logger.info("Curve params saved to %s", params_out)
    logger.info("Curve diagnostics saved to %s", diag_out)
