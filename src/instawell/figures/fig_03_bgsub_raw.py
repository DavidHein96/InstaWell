import logging

import pandas as pd
import plotly.express as px

from instawell.core.exp_context import ExperimentContext
from instawell.core.steps import StepFiles
from instawell.utils.utils import split_unqcon_column

# set logging level to INFO

logger = logging.getLogger(__name__)


def bgsub_figure_generator(ctx: ExperimentContext):
    """
    Generates Plotly figures from grouped data.

    This function groups the input DataFrame by 'ligand', 'protein', and
    'buffer', then yields a line plot figure for each group.

    Args:
        data_df: A pandas DataFrame containing the data to plot.
                 It must include 'ligand', 'protein', 'buffer',
                 'Temperature', 'value', and 'well_unqcond' columns.

    Yields:
        A Plotly figure object for each group.
    """
    # Load the organized data
    bg_data_path = ctx.experiment_dir / StepFiles.BG_SUB_DATA
    if not bg_data_path.exists():
        raise FileNotFoundError(f"BG subtracted data file not found: {bg_data_path}")
    data_df = pd.read_csv(bg_data_path)

    # ensure the first column is 'Temperature'
    if data_df.columns[0] != "Temperature":
        raise ValueError("The first column must be 'Temperature'.")

    plotting_df = data_df.melt(id_vars=["Temperature"], var_name="unqcond", value_name="value")
    # ensure the necessary columns are present
    plotting_df = split_unqcon_column(plotting_df)
    required_columns = [
        "Temperature",
        "unqcond",
        "value",
        "concentration",
        "ligand",
        "protein",
        "buffer",
    ]

    for col in required_columns:
        if col not in plotting_df.columns:
            raise ValueError(f"Missing required column: {col} in the data.")
    grouped_data = plotting_df.groupby(["ligand", "protein", "buffer"])

    for (ligand, protein, buffer), group in grouped_data:
        fig = px.line(
            group,
            x="Temperature",
            y="value",
            color="unqcond",
            title=f"BG subtracted Data for {ligand} and {protein} in {buffer} Buffer",
        )
        yield fig
