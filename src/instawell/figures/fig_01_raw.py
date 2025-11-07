import logging

import pandas as pd
import plotly.express as px

from instawell.core.exp_context import ExperimentContext
from instawell.core.steps import StepFiles
from instawell.utils.utils import slugify

# set logging level to INFO

logger = logging.getLogger(__name__)


def raw_figure_generator(
    ctx: ExperimentContext,
    save_figs: bool = False,
    html_include_plotlyjs: str = "cdn",
):
    """
    Generates Plotly figures from grouped data.

    This function groups the input DataFrame by 'ligand', 'protein', and
    'buffer', then yields a line plot figure for each group.

    Args:
        ctx: An ExperimentContext object containing experiment details.

    Yields:
        A Plotly figure object for each group.
    """
    # Load the organized data
    organized_data_path = ctx.experiment_dir / StepFiles.INGESTED_DATA
    if not organized_data_path.exists():
        raise FileNotFoundError(f"Organized data file not found: {organized_data_path}")
    data_df = pd.read_csv(organized_data_path)

    # ensure the necessary columns are present
    required_columns = [
        "Temperature",
        "well",
        "value",
        "ligand",
        "protein",
        "buffer",
        "concentration",
        "well_unqcond",
    ]
    for col in required_columns:
        if col not in data_df.columns:
            raise ValueError(f"Missing required column: {col} in the data.")
    grouped_data = data_df.groupby(["ligand", "protein", "buffer"])

    for (ligand, protein, buffer), group in grouped_data:
        fig = px.line(
            group,
            x="Temperature",
            y="value",
            color="well_unqcond",
            title=f"Raw Data for {ligand} and {protein} in {buffer} Buffer",
        )
        if save_figs:
            slug = slugify(f"{ligand}__{protein}__{buffer}")
            html_path = ctx.experiment_dir / f"{slug}.html"
            fig.write_html(html_path, include_plotlyjs=html_include_plotlyjs)
            logger.info(
                "Saved raw figure for ligand=%s, protein=%s, buffer=%s to %s",
                ligand,
                protein,
                buffer,
                html_path,
            )
        yield fig
