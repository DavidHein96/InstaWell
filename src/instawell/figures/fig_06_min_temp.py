import logging

import pandas as pd
import plotly.express as px

from instawell.core.exp_context import ExperimentContext
from instawell.core.steps import StepFiles
from instawell.utils.utils import convert_concentration_to_float

# set logging level to INFO

logger = logging.getLogger(__name__)


def min_temp_figure_generator(ctx: ExperimentContext):
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
    min_temperatures_data_path = ctx.experiment_dir / StepFiles.MIN_TEMPERATURES_DATA
    if not min_temperatures_data_path.exists():
        raise FileNotFoundError(
            f"Min temperatures data file not found: {min_temperatures_data_path}"
        )
    data_df = pd.read_csv(min_temperatures_data_path)

    # ensure the necessary columns are present
    required_columns = [
        "unqcond",
        "min_temperature",
        "concentration",
        "ligand",
        "protein",
        "buffer",
    ]

    for col in required_columns:
        if col not in data_df.columns:
            raise ValueError(f"Missing required column: {col} in the data.")

    data_df["concentration2"] = data_df["concentration"].apply(convert_concentration_to_float)
    grouped_data = data_df.groupby(["ligand", "protein", "buffer"])

    for (ligand, protein, buffer), group in grouped_data:
        fig = px.scatter(
            group,
            x="concentration2",
            y="min_temperature",
            color="ligand",
            title=f"Min Temperature for {ligand} and {protein} in {buffer} Buffer",
        )
        yield fig
