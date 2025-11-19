import logging
from typing import Literal

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from instawell.core.exp_context import ExperimentContext
from instawell.core.steps import StepFiles
from instawell.utils.curve_fitting import fit_4pl, four_pl_log10x, sigma_weight
from instawell.utils.utils import convert_concentration_to_float

logger = logging.getLogger(__name__)


# ---------- Helpers ----------

_HOVER = {
    "unqcond": True,
    "concentration": True,
    "conc_num": ":.3g",
    "min_temperature": ":.3f",
}
_LABELS_LINEAR = {"min_temperature": "Min Temperature", "conc_num": "Concentration"}
_LABELS_LOG1P = {"min_temperature": "Min Temperature", "conc_log1p": "log(1 + concentration)"}


def _decade_ticks(xmin: float, xmax: float) -> list[float]:
    d = np.arange(np.floor(np.log10(xmin)), np.ceil(np.log10(xmax)) + 1)
    return (10**d).tolist()


def _colorbar_for_log1p(conc_numeric: pd.Series):
    """Build a readable colorbar & x tick labels for log1p displays."""
    vmin = float(conc_numeric.min())
    vmax = float(conc_numeric.max())
    candidate = np.array([0, 0.1, 0.5, 1, 1.5, 3, 6, 12, 25, 50, 100, 200, 400, 800])
    ticks_lin = candidate[(candidate >= max(0, vmin)) & (candidate <= max(vmax, 0))]
    if ticks_lin.size == 0:
        ticks_lin = np.array([0, max(1.0, vmax)])
    ticks_log1p = np.log1p(ticks_lin)
    cb = dict(
        title="log(1 + conc)",
        tickvals=ticks_log1p.tolist(),
        ticktext=[str(t).rstrip("0").rstrip(".") for t in ticks_lin.tolist()],
    )
    return cb, ticks_log1p.tolist(), [str(t).rstrip("0").rstrip(".") for t in ticks_lin.tolist()]


# ---- per-mode plotters (flat, single purpose) --------------------------
def _plot_linear(g: pd.DataFrame, base_title: str, color_scale: str):
    fig = px.scatter(
        g,
        x="conc_num",
        y="min_temperature",
        color="conc_log1p",
        color_continuous_scale=color_scale,
        hover_data=_HOVER,
        labels=_LABELS_LINEAR,
        title=base_title + " — Linear (QC, no fit)",
    )
    fig.update_traces(marker=dict(size=8, line=dict(width=0)))
    return fig


def _plot_log1p(g: pd.DataFrame, base_title: str, color_scale: str):
    cb, xticks, xticktext = _colorbar_for_log1p(g["conc_num"].clip(lower=0))
    fig = px.scatter(
        g,
        x="conc_log1p",
        y="min_temperature",
        color="conc_log1p",
        color_continuous_scale=color_scale,
        hover_data=_HOVER,
        labels=_LABELS_LOG1P,
        title=base_title + " — log(1+conc) (QC, no fit)",
    )
    fig.update_xaxes(tickvals=xticks, ticktext=xticktext)
    fig.update_layout(coloraxis_colorbar=cb)
    fig.update_traces(marker=dict(size=8, line=dict(width=0)))
    return fig


def _plot_log10_fit(g0: pd.DataFrame, base_title: str, color_scale: str, weighting: str):
    g_pos = g0[g0["conc_num"] > 0].copy()
    if g_pos.empty:
        return None

    # base scatter (log10 axis)
    fig = px.scatter(
        g_pos,
        x="conc_num",
        y="min_temperature",
        color=np.log10(g_pos["conc_num"]),
        color_continuous_scale=color_scale,
        hover_data=_HOVER,
        labels=_LABELS_LINEAR,
        title=base_title + " — log10 (Prism-like fit)",
    )
    fig.update_xaxes(type="log")

    xmin, xmax = float(g_pos["conc_num"].min()), float(g_pos["conc_num"].max())
    fig.update_xaxes(tickvals=_decade_ticks(xmin, xmax))

    # weighting
    sigma = sigma_weight(g_pos["min_temperature"].to_numpy()) if weighting == "1/y^2" else None

    # 4PL fit & overlay
    params, _ = fit_4pl(g_pos["conc_num"].to_numpy(), g_pos["min_temperature"].to_numpy(), sigma)
    if params is not None:
        bottom, top, logEC50, hill = params
        xfit = np.logspace(np.log10(xmin), np.log10(xmax), 200)
        yfit = four_pl_log10x(xfit, bottom, top, logEC50, hill)
        fig.add_trace(
            go.Scatter(
                x=xfit,
                y=yfit,
                mode="lines",
                name="4PL fit",
                line=dict(width=2),
                hovertemplate="conc: %{x:.3g}<br>pred: %{y:.3f}",
                showlegend=True,
            )
        )
        ec50 = 10**logEC50
        subtitle = f"4PL: bottom={bottom:.3g}, top={top:.3g}, EC50={ec50:.3g}, Hill={hill:.3g}"
        fig.add_annotation(
            text=subtitle,
            x=0.5,
            xref="paper",
            xanchor="center",
            y=0.90,
            yref="paper",
            yanchor="top",
            showarrow=False,
            font=dict(size=12, color="gray"),
        )

    fig.update_traces(marker=dict(size=8, line=dict(width=0)))
    return fig


# ---------- Main generator ----------
def min_temp_figure_generator(
    ctx: ExperimentContext,
    panel_by: list[str] | None = None,
    mode: Literal["linear", "log1p", "log10_fit"] = "log10_fit",
    color_scale: str = "Viridis",
    weighting: str = "none",  # "none" or "1/y^2" (only for log10_fit fits)
):
    """
    Scatter of minimum temperature vs concentration with selectable x-scale & fit.

    Modes
    -----
    - "linear"    : x = concentration (linear). Includes zeros. No curve fit.
    - "log1p"     : x = log(1 + concentration). Includes zeros. No curve fit.
    - "log10_fit" : x = log10(concentration). Excludes zeros (log axis).
                    Overlays Prism-style 4PL fit (fit in log10; parameter logEC50).
    """
    path = ctx.experiment_dir / StepFiles.MIN_TEMPERATURES_DATA.value
    if not path.exists():
        raise FileNotFoundError(f"Min temperatures data file not found: {path}")
    df = pd.read_csv(path)

    req = {"unqcond", "min_temperature", "concentration", *set(ctx.condition_fields)}
    missing = req - set(df.columns)
    if missing:
        raise ValueError(f"Missing required column(s): {sorted(missing)}")

    # concentrations & helpers
    df["conc_num"] = df["concentration"].apply(convert_concentration_to_float)
    df["conc_log1p"] = np.log1p(df["conc_num"].clip(lower=0))

    # panels
    if panel_by is None:
        panel_by = [f for f in ctx.condition_fields if f != "concentration"]
        if not panel_by:
            df["__panel__"] = "all"
            panel_by = ["__panel__"]

    for gvals, g0 in df.groupby(panel_by, sort=False):
        group_keys = (
            dict(zip(panel_by, gvals, strict=True))
            if isinstance(gvals, tuple)
            else {panel_by[0]: gvals}
        )
        base_title = "Min Temperature: " + " || ".join(f"{k} = {v}" for k, v in group_keys.items())

        if mode == "linear":
            fig = _plot_linear(g0, base_title, color_scale)
        elif mode == "log1p":
            fig = _plot_log1p(g0, base_title, color_scale)
        elif mode == "log10_fit":
            fig = _plot_log10_fit(g0, base_title, color_scale, weighting)
            if fig is None:
                logger.info(f"No positive concentrations in panel {group_keys}; skipping.")
                continue
        else:
            raise ValueError("mode must be one of: 'linear', 'log1p', 'log10_fit'")

        fig.update_layout(hovermode="closest", margin=dict(l=40, r=20, t=60, b=40))
        yield fig


# ---------- Main generator ----------
# def min_temp_figure_generator(
#     ctx: ExperimentContext,
#     panel_by: list[str] | None = None,
#     mode: Literal["linear", "log1p", "log10_fit"] = "log10_fit",
#     color_scale: str = "Viridis",
#     weighting: str = "none",  # "none" or "1/y^2" (only for log10_fit fits)
# ):
#     """
#     Scatter of minimum temperature vs concentration with selectable x-scale & fit.

#     Modes
#     -----
#     - "linear"      : x = concentration (linear). Includes zeros. No curve fit.
#     - "log1p"       : x = log(1 + concentration). Includes zeros. No curve fit.
#     - "log10_prism" : x = log10(concentration). Excludes zeros (log axis).
#                       Overlays Prism-style 4PL fit (fit in log10; parameter logEC50).

#     Panels
#     ------
#     One chart per unique combination of fields in `panel_by`.
#     Default = all ctx.condition_fields except "concentration".
#     """

#     path = ctx.experiment_dir / StepFiles.MIN_TEMPERATURES_DATA.value
#     if not path.exists():
#         raise FileNotFoundError(f"Min temperatures data file not found: {path}")
#     df = pd.read_csv(path)

#     req = {"unqcond", "min_temperature", "concentration", *set(ctx.condition_fields)}
#     missing = req - set(df.columns)
#     if missing:
#         raise ValueError(f"Missing required column(s): {sorted(missing)}")

#     # concentrations
#     df["conc_num"] = df["concentration"].apply(convert_concentration_to_float)
#     df["conc_log1p"] = np.log1p(df["conc_num"].clip(lower=0))

#     # panel keys
#     if panel_by is None:
#         panel_by = [f for f in ctx.condition_fields if f != "concentration"]
#         if not panel_by:
#             df["__panel__"] = "all"
#             panel_by = ["__panel__"]

#     # iterate panels
#     for gvals, g0 in df.groupby(panel_by, sort=False):
#         group_keys = (
#             dict(zip(panel_by, gvals, strict=True))
#             if isinstance(gvals, tuple)
#             else {panel_by[0]: gvals}
#         )
#         base_title = "Min Temperature: " + " || ".join(f"{k} = {v}" for k, v in group_keys.items())

#         if mode == "linear":
#             # include zeros; linear x; no fit
#             g = g0.copy()
#             fig = px.scatter(
#                 g,
#                 x="conc_num",
#                 y="min_temperature",
#                 color="conc_log1p",  # continuous for readability
#                 color_continuous_scale=color_scale,
#                 hover_data={
#                     "unqcond": True,
#                     "concentration": True,
#                     "conc_num": ":.3g",
#                     "min_temperature": ":.3f",
#                 },
#                 labels={"min_temperature": "Min Temperature", "conc_num": "Concentration"},
#                 title=base_title + " — Linear (QC, no fit)",
#             )
#             fig.update_traces(marker=dict(size=8, line=dict(width=0)))

#         elif mode == "log1p":
#             # include zeros; log1p display; no fit
#             g = g0.copy()
#             cb, xticks, xticktext = _colorbar_for_log1p(g["conc_num"].clip(lower=0))
#             fig = px.scatter(
#                 g,
#                 x="conc_log1p",
#                 y="min_temperature",
#                 color="conc_log1p",
#                 color_continuous_scale=color_scale,
#                 hover_data={
#                     "unqcond": True,
#                     "concentration": True,
#                     "conc_num": ":.3g",
#                     "min_temperature": ":.3f",
#                 },
#                 labels={
#                     "min_temperature": "Min Temperature",
#                     "conc_log1p": "log(1 + concentration)",
#                 },
#                 title=base_title + " — log(1+conc) (QC, no fit)",
#             )
#             fig.update_xaxes(tickvals=xticks, ticktext=xticktext)
#             fig.update_layout(coloraxis_colorbar=cb)
#             fig.update_traces(marker=dict(size=8, line=dict(width=0)))

#         elif mode == "log10_fit":
#             # exclude zeros for log axis and fit
#             g_pos = g0[g0["conc_num"] > 0].copy()
#             if g_pos.empty:
#                 logger.info(f"No positive concentrations in panel {group_keys}; skipping.")
#                 continue

#             # base scatter (log10 axis)
#             fig = px.scatter(
#                 g_pos,
#                 x="conc_num",
#                 y="min_temperature",
#                 color=np.log10(g_pos["conc_num"]),
#                 color_continuous_scale=color_scale,
#                 hover_data={
#                     "unqcond": True,
#                     "concentration": True,
#                     "conc_num": ":.3g",
#                     "min_temperature": ":.3f",
#                 },
#                 labels={"min_temperature": "Min Temperature", "conc_num": "Concentration"},
#                 title=base_title + " — log10 (Prism-like fit)",
#             )
#             fig.update_xaxes(type="log")

#             # decade ticks for readability
#             xmin, xmax = float(g_pos["conc_num"].min()), float(g_pos["conc_num"].max())
#             decades = np.arange(np.floor(np.log10(xmin)), np.ceil(np.log10(xmax)) + 1)
#             tickvals = (10**decades).tolist()
#             fig.update_xaxes(tickvals=tickvals)

#             # 4PL fit
#             sigma = None
#             if weighting == "1/y^2":
#                 y = g_pos["min_temperature"].to_numpy()
#                 epsy = max(1e-9, float(np.nanmin(np.abs(y[y != 0]))) if np.any(y != 0) else 1.0)
#                 sigma = np.clip(np.abs(y), epsy, None)

#             params, pcov = _fit_4pl(
#                 g_pos["conc_num"].to_numpy(),
#                 g_pos["min_temperature"].to_numpy(),
#                 sigma=sigma,
#             )
#             if params is not None:
#                 bottom, top, logEC50, hill = params
#                 xfit = np.logspace(np.log10(xmin), np.log10(xmax), 200)
#                 yfit = _four_pl_log10x(xfit, bottom, top, logEC50, hill)

#                 fig.add_trace(
#                     go.Scatter(
#                         x=xfit,
#                         y=yfit,
#                         mode="lines",
#                         name="4PL fit",
#                         line=dict(width=2),
#                         hovertemplate="conc: %{x:.3g}<br>pred: %{y:.3f}",
#                         showlegend=True,
#                     )
#                 )

#                 ec50 = 10**logEC50
#                 subtitle = (
#                     f"4PL: bottom={bottom:.3g}, top={top:.3g}, EC50={ec50:.3g}, Hill={hill:.3g}"
#                 )
#                 fig.add_annotation(
#                     text=subtitle,
#                     x=0.5,
#                     xref="paper",
#                     xanchor="center",
#                     y=0.90,
#                     yref="paper",
#                     yanchor="top",
#                     showarrow=False,
#                     font=dict(size=12, color="gray"),
#                 )
#             else:
#                 logger.info(
#                     f"4PL fit skipped in panel {group_keys} (insufficient/degenerate data)."
#                 )

#             fig.update_traces(marker=dict(size=8, line=dict(width=0)))

#         else:
#             raise ValueError("mode must be one of: 'linear', 'log1p', 'log10_prism'")

#         fig.update_layout(hovermode="closest", margin=dict(l=40, r=20, t=60, b=40))
#         yield fig


# def _four_pl(x, bottom, top, ec50, hill):
#     # 4-parameter logistic
#     return bottom + (top - bottom) / (1.0 + (x / ec50) ** hill)


# def _init_guess(x, y):
#     # heuristic initial guesses
#     y = np.asarray(y)
#     x = np.asarray(x)
#     bottom = np.nanmin(y)
#     top = np.nanmax(y)
#     # EC50: geometric-like center of positive x’s; fallback to median
#     pos = x[x > 0]
#     if pos.size >= 2:
#         ec50 = np.exp(np.mean(np.log(pos)))
#     elif pos.size == 1:
#         ec50 = float(pos[0])
#     else:
#         ec50 = max(1.0, np.nanmedian(x))
#     # hill sign from correlation (coarse)
#     corr = (
#         np.corrcoef(x, y)[0, 1]
#         if (np.isfinite(x).all() and np.isfinite(y).all() and x.size > 1)
#         else 0
#     )
#     hill = (
#         1.0 if corr < 0 else -1.0
#     )  # common for agonist (upward) vs inverse; flip if your biology needs
#     return bottom, top, ec50, hill


# def _fit_4pl_safe(x, y):
#     """Return (params, xfit, yfit) or (None, None, None) if fit fails."""
#     x = np.asarray(x, dtype=float)
#     y = np.asarray(y, dtype=float)

#     # Must have at least 4 unique x with finite y to fit
#     mask = np.isfinite(x) & np.isfinite(y)
#     x, y = x[mask], y[mask]
#     if np.unique(x).size < 4:
#         return None, None, None

#     # Ensure some positive x for EC50 meaning; allow zero in data
#     if np.nanmax(x) <= 0:
#         return None, None, None

#     p0 = _init_guess(x, y)
#     # Bounds: ec50 > 0, hill in a reasonable range; bottom/top free
#     lb = [-np.inf, -np.inf, 1e-12, -10.0]
#     ub = [np.inf, np.inf, np.inf, 10.0]

#     try:
#         params, _ = curve_fit(_four_pl, x, y, p0=p0, bounds=(lb, ub), maxfev=20000)
#     except Exception as e:
#         logger.debug(f"4PL fit failed: {e}")
#         return None, None, None

#     # Smooth x-grid (include zero + log-spaced positive range)
#     xmin, xmax = float(np.nanmin(x)), float(np.nanmax(x))
#     pos_min = max(1e-8, np.min(x[x > 0])) if np.any(x > 0) else 1.0
#     pos_grid = np.logspace(np.log10(pos_min), np.log10(max(xmax, pos_min * 10)), 200)
#     xfit = np.unique(np.concatenate([[0.0], pos_grid])) if xmin <= 0 else pos_grid
#     yfit = _four_pl(xfit, *params)
#     return params, xfit, yfit


# def _build_colorbar_for_linear_conc(conc_numeric: pd.Series):
#     vmin = float(conc_numeric.min())
#     vmax = float(conc_numeric.max())
#     candidate = np.array([0, 0.1, 0.5, 1, 1.5, 3, 6, 12, 25, 50, 100, 200, 400, 800])
#     ticks_lin = candidate[(candidate >= max(0, vmin)) & (candidate <= max(vmax, 0))]
#     if ticks_lin.size == 0:
#         ticks_lin = np.array([0, max(1.0, vmax)])
#     ticks_log1p = np.log1p(ticks_lin)
#     return dict(
#         title="log(1 + conc)",
#         tickvals=ticks_log1p.tolist(),
#         ticktext=[str(t).rstrip("0").rstrip(".") for t in ticks_lin.tolist()],
#     )


# def min_temp_figure_generator(
#     ctx: ExperimentContext,
#     panel_by: list[str] | None = None,
#     x_scale: str = "log1p",  # "log1p" or "linear"
#     color_scale: str = "Viridis",
#     fit_4pl: bool = True,  # <- NEW
#     show_params_in_title: bool = False,  # optionally append fitted params
# ):
#     """
#     Scatter of minimum temperature vs. concentration with optional 4PL fit.

#     Panels
#     ------
#     One chart per unique combination of fields in `panel_by`. By default,
#     uses all `ctx.condition_fields` except "concentration".

#     Marks
#     -----
#     • x = concentration (numeric), optionally log1p-transformed
#     • y = min_temperature
#     • color = log1p(concentration) (continuous gradient)

#     Fit
#     ---
#     If `fit_4pl=True`, overlays a 4-parameter logistic curve per panel.
#     """
#     path = ctx.experiment_dir / StepFiles.MIN_TEMPERATURES_DATA.value
#     if not path.exists():
#         raise FileNotFoundError(f"Min temperatures data file not found: {path}")
#     df = pd.read_csv(path)

#     req = {"unqcond", "min_temperature", *set(ctx.condition_fields)}
#     missing = req - set(df.columns)
#     if missing:
#         raise ValueError(f"Missing required column(s): {sorted(missing)}")
#     if "concentration" not in df.columns:
#         raise ValueError("Expected 'concentration' in min-temperature table.")

#     # concentrations
#     df["conc_num"] = df["concentration"].apply(convert_concentration_to_float).clip(lower=0)
#     df["conc_log1p"] = np.log1p(df["conc_num"])

#     # axis settings
#     if x_scale == "log1p":
#         x_field = "conc_log1p"
#         x_title = "log(1 + concentration)"
#         colorbar = _build_colorbar_for_linear_conc(df["conc_num"])
#         x_ticks = colorbar["tickvals"]
#         x_ticktext = colorbar["ticktext"]
#     elif x_scale == "linear":
#         x_field = "conc_num"
#         x_title = "Concentration"
#         colorbar = None
#         x_ticks = None
#         x_ticktext = None
#     else:
#         raise ValueError("x_scale must be 'log1p' or 'linear'")

#     # panels
#     if panel_by is None:
#         panel_by = [f for f in ctx.condition_fields if f != "concentration"]
#         if not panel_by:
#             df["__panel__"] = "all"
#             panel_by = ["__panel__"]

#     for gvals, g in df.groupby(panel_by, sort=False):
#         group_keys = (
#             dict(zip(panel_by, gvals)) if isinstance(gvals, tuple) else {panel_by[0]: gvals}
#         )
#         base_title = "Min Temperature: " + " || ".join(f"{k} = {v}" for k, v in group_keys.items())

#         fig = px.scatter(
#             g,
#             x=x_field,
#             y="min_temperature",
#             color="conc_log1p",
#             color_continuous_scale=color_scale,
#             hover_data={
#                 "unqcond": True,
#                 "concentration": True,
#                 "conc_num": ":.3g",
#                 "min_temperature": ":.3f",
#             },
#             labels={"min_temperature": "Min Temperature", x_field: x_title},
#             title=base_title,
#         )

#         # beautify axes/colorbar
#         if x_ticks is not None:
#             fig.update_xaxes(tickvals=x_ticks, ticktext=x_ticktext)
#         if colorbar is not None:
#             fig.update_layout(coloraxis_colorbar=colorbar)
#         fig.update_traces(marker=dict(size=8, line=dict(width=0)))

#         # ---- 4PL fit overlay ----
#         if fit_4pl:
#             params, xfit, yfit = _fit_4pl_safe(g["conc_num"].values, g["min_temperature"].values)
#             if params is not None:
#                 bottom, top, ec50, hill = params
#                 # map xfit onto chosen display scale
#                 xfit_disp = np.log1p(xfit) if x_scale == "log1p" else xfit

#                 fig.add_trace(
#                     go.Scatter(
#                         x=xfit_disp,
#                         y=yfit,
#                         mode="lines",
#                         name="4PL fit",
#                         line=dict(width=2),
#                         hovertemplate=("conc: %{customdata[0]:.3g}<br>pred: %{y:.3f}"),
#                         customdata=np.c_[xfit],  # show linear conc in hover
#                         showlegend=True,
#                     )
#                 )

#                 if show_params_in_title:
#                     fig.update_layout(
#                         title=(
#                             base_title + f"<br><sup>4PL: bottom={bottom:.3g}, top={top:.3g}, "
#                             f"EC50={ec50:.3g}, Hill={hill:.3g}</sup>"
#                         )
#                     )
#             else:
#                 logger.info(f"4PL fit skipped (insufficient/degenerate data) for {group_keys}")

#         fig.update_layout(hovermode="closest", margin=dict(l=40, r=20, t=60, b=40))
#         yield fig


# WORKING VERSION BELOW

# def _build_colorbar_for_linear_conc(conc_numeric: pd.Series):
#     vmin = float(conc_numeric.min())
#     vmax = float(conc_numeric.max())
#     # pick pleasant ticks in linear space, clipped to data
#     candidate = np.array([0, 0.1, 0.5, 1, 1.5, 3, 6, 12, 25, 50, 100, 200, 400, 800])
#     ticks_lin = candidate[(candidate >= max(0, vmin)) & (candidate <= max(vmax, 0))]
#     if ticks_lin.size == 0:
#         ticks_lin = np.array([0, max(1.0, vmax)])
#     ticks_log1p = np.log1p(ticks_lin)
#     return dict(
#         title="log(1 + conc)",
#         tickvals=ticks_log1p.tolist(),
#         ticktext=[str(t).rstrip("0").rstrip(".") for t in ticks_lin.tolist()],
#     )


# def min_temp_figure_generator(
#     ctx: ExperimentContext,
#     panel_by: list[str] | None = None,
#     x_scale: str = "log1p",  # "log1p" or "linear"
#     color_scale: str = "Viridis",
# ):
#     """
#     Scatter of minimum temperature vs. concentration.

#     Panels
#     ------
#     One chart per unique combination of fields in `panel_by`. By default,
#     uses all `ctx.condition_fields` except "concentration".

#     Marks
#     -----
#     • x = concentration (numeric), optionally log1p-transformed
#     • y = min_temperature
#     • color = log1p(concentration) with a readable colorbar
#     """
#     # ---- Load ----
#     path = ctx.experiment_dir / StepFiles.MIN_TEMPERATURES_DATA.value
#     if not path.exists():
#         raise FileNotFoundError(f"Min temperatures data file not found: {path}")
#     df = pd.read_csv(path)

#     # ---- Validate ----
#     req = {"unqcond", "min_temperature", *set(ctx.condition_fields)}
#     missing = req - set(df.columns)
#     if missing:
#         raise ValueError(f"Missing required column(s): {sorted(missing)}")

#     if "concentration" not in df.columns:
#         raise ValueError("Expected 'concentration' in min-temperature table.")

#     # ---- Prep concentration ----
#     df["conc_num"] = df["concentration"].apply(convert_concentration_to_float).clip(lower=0)
#     df["conc_log1p"] = np.log1p(df["conc_num"])

#     # x-field + axis cosmetics
#     if x_scale == "log1p":
#         x_field = "conc_log1p"
#         x_title = "log(1 + concentration)"
#         colorbar = _build_colorbar_for_linear_conc(df["conc_num"])
#         x_ticks = colorbar["tickvals"]
#         x_ticktext = colorbar["ticktext"]
#     elif x_scale == "linear":
#         x_field = "conc_num"
#         x_title = "Concentration"
#         colorbar = None
#         x_ticks = None
#         x_ticktext = None
#     else:
#         raise ValueError("x_scale must be 'log1p' or 'linear'")

#     # ---- Panels ----
#     if panel_by is None:
#         panel_by = [f for f in ctx.condition_fields if f != "concentration"]
#         if not panel_by:
#             df["__panel__"] = "all"
#             panel_by = ["__panel__"]

#     # ---- Plot per panel ----
#     for gvals, g in df.groupby(panel_by, sort=False):
#         group_keys = (
#             dict(zip(panel_by, gvals)) if isinstance(gvals, tuple) else {panel_by[0]: gvals}
#         )
#         title = "Min Temperature: " + " || ".join(f"{k} = {v}" for k, v in group_keys.items())

#         fig = px.scatter(
#             g,
#             x=x_field,
#             y="min_temperature",
#             color="conc_log1p",  # continuous gradient by concentration (log1p)
#             color_continuous_scale=color_scale,
#             hover_data={
#                 "unqcond": True,
#                 "concentration": True,  # original label
#                 "conc_num": ":.3g",
#                 "min_temperature": ":.3f",
#             },
#             labels={"min_temperature": "Min Temperature", x_field: x_title},
#             title=title,
#         )

#         # axis + colorbar formatting
#         if x_ticks is not None:
#             fig.update_xaxes(tickvals=x_ticks, ticktext=x_ticktext)
#         if colorbar is not None:
#             fig.update_layout(coloraxis_colorbar=colorbar)

#         fig.update_traces(marker=dict(size=8, line=dict(width=0)))
#         fig.update_layout(
#             hovermode="closest",
#             margin=dict(l=40, r=20, t=60, b=40),
#         )

#         yield fig


# ====
# OLD VERSION BELOW
# import logging

# import pandas as pd
# import plotly.express as px

# from instawell.core.exp_context import ExperimentContext
# from instawell.core.steps import StepFiles
# from instawell.utils.utils import convert_concentration_to_float

# # set logging level to INFO

# logger = logging.getLogger(__name__)


# def min_temp_figure_generator(ctx: ExperimentContext):
#     """
#     Generates Plotly figures from grouped data.

#     This function groups the input DataFrame by 'ligand', 'protein', and
#     'buffer', then yields a line plot figure for each group.

#     Args:
#         data_df: A pandas DataFrame containing the data to plot.
#                  It must include 'ligand', 'protein', 'buffer',
#                  'Temperature', 'value', and 'well_unqcond' columns.

#     Yields:
#         A Plotly figure object for each group.
#     """
#     # Load the organized data
#     min_temperatures_data_path = ctx.experiment_dir / StepFiles.MIN_TEMPERATURES_DATA
#     if not min_temperatures_data_path.exists():
#         raise FileNotFoundError(
#             f"Min temperatures data file not found: {min_temperatures_data_path}"
#         )
#     data_df = pd.read_csv(min_temperatures_data_path)

#     # ensure the necessary columns are present
#     required_columns = [
#         "unqcond",
#         "min_temperature",
#         "concentration",
#         "ligand",
#         "protein",
#         "buffer",
#     ]

#     for col in required_columns:
#         if col not in data_df.columns:
#             raise ValueError(f"Missing required column: {col} in the data.")

#     data_df["concentration2"] = data_df["concentration"].apply(convert_concentration_to_float)
#     grouped_data = data_df.groupby(["ligand", "protein", "buffer"])

#     for (ligand, protein, buffer), group in grouped_data:
#         fig = px.scatter(
#             group,
#             x="concentration2",
#             y="min_temperature",
#             color="ligand",
#             title=f"Min Temperature for {ligand} and {protein} in {buffer} Buffer",
#         )
#         yield fig
