import logging
from collections.abc import Generator
from typing import Literal

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from instawell.core.exp_context import ExperimentContext
from instawell.core.steps import StepFiles
from instawell.figures.save_figure import save_figure

logger = logging.getLogger(__name__)


def raw_figure_generator(
    ctx: ExperimentContext,
    save_figs: bool = False,
    html_include_plotlyjs: Literal["cdn",] = "cdn",
    series_by: str = "concentration",
    use_filtered_data: bool = False,
) -> Generator[go.Figure, None, None]:
    """
    Yield per-well raw traces grouped by all condition fields except the
    dimension specified in ``series_by``. Each figure is a Plotly line chart with
    a discrete color per well, allowing quick visual inspection and manual
    filtering.

    Parameters
    ----------
    ctx : ExperimentContext
        Experiment context whose ``experiment_dir`` contains either
        ``01_raw_organized_data.csv`` or ``02_filtered_organized_data.csv``.
    save_figs : bool, optional
        If ``True``, each generated figure is written to the appropriate plots
        directory under ``ctx.experiment_dir`` using
        :func:`instawell.figures.save_figure`.
    html_include_plotlyjs : {"cdn"}, optional
        Passed through to Plotly's ``write_html`` when ``save_figs`` is enabled.
        The default keeps the HTML lightweight while requiring internet access.
    series_by : str, optional
        Condition column that varies within a panel. All other condition fields
        define the grouping key (default ``"concentration"``).
    use_filtered_data : bool, optional
        If ``True``, plot the already filtered dataset (step 02). Otherwise plot
        the ingested raw data (step 01).

    Yields
    ------
    Generator[plotly.graph_objects.Figure, None, None]
        One figure per unique combination of ``ctx.condition_fields`` other than
        ``series_by``.

    Raises
    ------
    FileNotFoundError
        If the required CSV (raw or filtered) is missing.
    ValueError
        If key columns such as ``Temperature``, ``well``, ``value``, ``unqcond``,
        or ``series_by`` are absent, indicating corrupted input.
    """

    if use_filtered_data:
        data_path = ctx.experiment_dir / StepFiles.FILTERED_DATA.value
        d_source = "Filtered"
        plot_dir_enum = StepFiles.FILTERED_PLOTS
    else:
        data_path = ctx.experiment_dir / StepFiles.INGESTED_DATA.value
        d_source = "Ingested"
        plot_dir_enum = StepFiles.RAW_PLOTS

    if not data_path.exists():
        raise FileNotFoundError(f"{d_source} data file not found: {data_path}")
    df = pd.read_csv(data_path)
    # ---- Validate columns ----
    base_req = {"Temperature", "well", "value", "well_unqcond", "unqcond"}
    missing = (base_req | set(ctx.condition_fields)) - set(df.columns)
    if missing:
        raise ValueError(f"Missing required column(s): {sorted(missing)}")

    if series_by not in df.columns:
        raise ValueError(f"`series_by='{series_by}'` not found in data columns.")

    # ---- Determine panel keys (everything except series_by) ----
    panel_keys = [f for f in ctx.condition_fields if f != series_by]
    if not panel_keys:
        # If plot_by is the only dimension, make a single panel
        df["__panel__"] = "all"
        panel_keys = ["__panel__"]

    for gvals, g in df.groupby(panel_keys):
        if isinstance(gvals, tuple):
            group_keys = {k: str(v) for k, v in zip(panel_keys, gvals, strict=True)}
        else:
            group_keys = {panel_keys[0]: str(gvals)}
        title = f"Raw Data ({d_source}): " + " || ".join(
            f"{k} = {v}" for k, v in group_keys.items()
        )
        fig = px.line(
            g,
            x="Temperature",
            y="value",
            color="well_unqcond",
            title=title,
        )

        if save_figs:
            save_figure(
                ctx=ctx,
                fig=fig,
                group_keys=group_keys | {"series_by": series_by},
                plot_dir_enum=plot_dir_enum,
                html_include_plotlyjs=html_include_plotlyjs,
            )

        yield fig
