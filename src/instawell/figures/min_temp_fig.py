import logging
from typing import Literal

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from instawell.core.exp_context import ExperimentContext
from instawell.core.steps import StepFiles
from instawell.figures.save_figure import save_figure
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
    save_figs: bool = False,
    html_include_plotlyjs: str = "cdn",
):
    """
    Generate scatter plots of min temperature vs concentration using the
    aggregated output from :func:`find_min_temperature`.

    Parameters
    ----------
    ctx : ExperimentContext
        Experiment context containing ``07_min_temperatures.csv``.
    panel_by : list[str] | None, optional
        Condition fields that define a panel/group. Defaults to all condition
        fields except ``"concentration"``.
    mode : {"linear","log1p","log10_fit"}, optional
        Controls the x-axis transform and whether a 4PL curve is fit:

        - ``"linear"`` – raw concentration (zeros included), scatter only.
        - ``"log1p"`` – log(1 + concentration) transform (zeros included),
          scatter only.
        - ``"log10_fit"`` – log10 domain (zeros excluded) with optional
          weighted 4PL fit overlay.
    color_scale : str, optional
        Plotly continuous color scale name (default ``"Viridis"``).
    weighting : {"none","1/y^2"}, optional
        When ``mode="log10_fit"``, choose whether to pass a sigma array (1/y^2)
        into the 4PL fit.
    save_figs : bool, optional
        If ``True``, persist each figure to the min-temperature plots directory.
    html_include_plotlyjs : str, optional
        Passed through to Plotly when saving figures.

    Yields
    ------
    Generator[plotly.graph_objects.Figure, None, None]
        One figure per panel, configured according to ``mode``.

    Raises
    ------
    FileNotFoundError
        If ``07_min_temperatures.csv`` is missing from the experiment directory.
    ValueError
        If required columns are missing from the min temperature DataFrame.
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
            plot_dir_enum = StepFiles.MIN_TEMPERATURES_PLOTS
        elif mode == "log1p":
            fig = _plot_log1p(g0, base_title, color_scale)
            plot_dir_enum = StepFiles.MIN_TEMPERATURES_PLOTS
        elif mode == "log10_fit":
            fig = _plot_log10_fit(g0, base_title, color_scale, weighting)
            plot_dir_enum = StepFiles.MIN_TEMPERATURES_WITH_CURVES_PLOTS
            if fig is None:
                logger.info(f"No positive concentrations in panel {group_keys}; skipping.")
                continue
        else:
            raise ValueError("mode must be one of: 'linear', 'log1p', 'log10_fit'")

        fig.update_layout(hovermode="closest", margin=dict(l=40, r=20, t=60, b=40))

        if save_figs:
            save_figure(
                ctx=ctx,
                fig=fig,
                group_keys=group_keys | {"mode": mode},
                plot_dir_enum=plot_dir_enum,
                html_include_plotlyjs=html_include_plotlyjs,
            )
        yield fig
