import logging
from pathlib import Path
from typing import Literal, TypeAlias

import pandas as pd
import plotly.express as px

from instawell.core.exp_context import ExperimentContext
from instawell.core.steps import StepFiles
from instawell.figures.color_scales import build_discrete_colormap_from_continuous
from instawell.figures.save_figure import save_figure
from instawell.utils.utils import convert_concentration_to_float_log

logger = logging.getLogger(__name__)

DataSourceName: TypeAlias = Literal[
    "averaged_data",
    "bg_subtracted_data",
    "min_max_scaled_data",
    "derivative_data",
]

# Map the public string API → internal StepFiles enum
_DATA_SOURCE_TO_STEPFILE: dict[DataSourceName, StepFiles] = {
    "averaged_data": StepFiles.AVERAGED_DATA_LONG,
    "bg_subtracted_data": StepFiles.BG_SUB_DATA_LONG,
    "min_max_scaled_data": StepFiles.MIN_MAX_SCALED_DATA_LONG,
    "derivative_data": StepFiles.DERIVATIVE_DATA_LONG,
}
_DATA_SOURCE_TO_PLOT_DIR: dict[DataSourceName, StepFiles] = {
    "averaged_data": StepFiles.AVERAGED_PLOTS,
    "bg_subtracted_data": StepFiles.BG_SUB_PLOTS,
    "min_max_scaled_data": StepFiles.MIN_MAX_SCALED_PLOTS,
    "derivative_data": StepFiles.DERIVATIVE_PLOTS,
}


def _map_data_source(ctx: ExperimentContext, data_source: DataSourceName) -> tuple[Path, StepFiles]:
    """
    Convert a user-facing data_source name into a Path under ctx.experiment_dir.
    """
    try:
        step_file = _DATA_SOURCE_TO_STEPFILE[data_source]
        plot_dir_enum = _DATA_SOURCE_TO_PLOT_DIR[data_source]
    except KeyError as exc:  # should be impossible if type-checking is used
        raise ValueError(f"Unsupported data_source {data_source!r}") from exc

    # StepFiles is a str Enum, so either of these is fine:
    # return ctx.experiment_dir / step_file
    data_path = ctx.experiment_dir / step_file.value

    return data_path, plot_dir_enum


def processed_figure_generator(
    ctx: ExperimentContext,
    data_source: Literal[
        "averaged_data", "bg_subtracted_data", "min_max_scaled_data", "derivative_data"
    ],
    save_figs: bool = False,
    html_include_plotlyjs: str = "cdn",
    series_by: str = "concentration",
    color_scale_mapping: str = "Thermal",
):
    """
    Generates Plotly figures for the averaged data with dynamic grouping and color scales.

    This function groups data by all condition fields except for 'concentration',
    creating a separate plot for each experimental condition. Within each plot,
    lines are colored by concentration using a sequential color scale.

    Args:
        ctx: An ExperimentContext object containing experiment details.
        save_figs: If True, saves the figures to disk. Defaults to False.
        html_include_plotlyjs: How to include Plotly.js in saved HTML files.
        color_continuous_scale: The Plotly color scale to use for concentration.
    """

    long_data_path, plot_dir_enum = _map_data_source(ctx=ctx, data_source=data_source)
    if not long_data_path.exists():
        raise FileNotFoundError(f"{data_source} data file not found: {long_data_path}")

    df = pd.read_csv(long_data_path)

    if not set(ctx.condition_fields).issubset(df.columns):
        missing = set(ctx.condition_fields) - set(df.columns)
        raise ValueError(f"Missing required condition fields in the data: {sorted(missing)}")

    if series_by not in df.columns:
        raise ValueError(f"`series_by='{series_by}'` not found in data columns.")

    # ---- Determine panel keys (everything except plot_by) ----
    panel_keys = [f for f in ctx.condition_fields if f != series_by]
    if not panel_keys:
        # If plot_by is the only dimension, make a single panel
        df["__panel__"] = "all"
        panel_keys = ["__panel__"]

    # ---- Build a discrete color map from a continuous scale ----
    num_cast = convert_concentration_to_float_log if series_by == "concentration" else None
    color_map, ordered_labels = build_discrete_colormap_from_continuous(
        df, series_by, colorscale=color_scale_mapping, numeric_cast=num_cast
    )

    # 5) enforce legend/category order to match numeric ordering
    df[series_by] = pd.Categorical(
        df[series_by].astype(str), categories=ordered_labels, ordered=True
    )

    df = df.sort_values([*panel_keys, series_by, "Temperature"])

    for gvals, g in df.groupby(panel_keys):
        if isinstance(gvals, tuple):
            group_keys = {k: str(v) for k, v in zip(panel_keys, gvals, strict=True)}
        else:
            group_keys = {panel_keys[0]: str(gvals)}
        title = f"{data_source}: " + " || ".join(f"{k} = {v}" for k, v in group_keys.items())
        fig = px.line(
            g,
            x="Temperature",
            y="value",
            color=series_by,
            line_group="unqcond",
            title=title,
            color_discrete_map=color_map,
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
