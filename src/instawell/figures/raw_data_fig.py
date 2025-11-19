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
    Raw per-well plots with a discrete color scale.

    - One chart per unique combo of all condition fields EXCEPT `series_by`.
    - Lines are uniquely colored per well.
    - This is used for the "raw" and "filtered" data views,
        to inspect individual well behavior and select outliers.

    Parameters
    ----------
    ctx : ExperimentContext
    save_figs : bool, optional
        Saves figs as html files to the exp folder, you can preview them in a browser, by default False
    html_include_plotlyjs : Literal["cdn",], optional
        Leaving this as cdn means the html files will be small, but an internet connection is required to view them in browser, b/c the javascript needs to be loaded. Setting it to 'inline' will embed the javascript in the html file, making it larger but viewable offline, setting it to directory saves the js in a file in the plots dir, so you can open it offline but have to keep the html and js files together, by default "cdn"
    series_by : str, optional
        When making the figures, they are logically grouped by conditions, so all lines on a single figure pane have the same conditions, except for the condition selected here. For example if the conditions were concentration, protein, buffer, ligand, each pane would have the same protein, buffer, and ligand, but different concentration, by default "concentration"
    use_filtered_data : bool, optional
        _description_, by default False

    Yields
    ------
    Generator[go.Figure, None, None]
        A generator that yields Plotly Figure objects.

    Raises
    ------
    FileNotFoundError
        If prerequisite data files are missing.
    ValueError
        If required columns are missing from the data (indicates data integrity issues).
    ValueError
        If the `series_by` column is not found in the data.
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
