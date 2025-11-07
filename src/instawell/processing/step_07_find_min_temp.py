import logging

import pandas as pd

from instawell.core.exp_context import ExperimentContext
from instawell.core.steps import StepFiles
from instawell.utils.logging_util import setup_experiment_logging
from instawell.utils.utils import split_unqcon_column

# set logging level to INFO
logger = logging.getLogger(__name__)


def find_min_temperature(ctx: ExperimentContext) -> None:
    """Finds the minimum temperature for each unique condition in the derivative data."""
    if ctx.log_to_file:
        setup_experiment_logging(
            experiment_dir=ctx.experiment_dir, filename="experiment.log", level=ctx.log_level
        )
    # Build the path to the derivative data
    derivative_data_path = ctx.experiment_dir / StepFiles.DERIVATIVE_DATA
    if not derivative_data_path.exists():
        raise FileNotFoundError(f"Derivative data file not found: {derivative_data_path}")
    # Load the derivative data
    data = pd.read_csv(derivative_data_path)
    # ensure the first column is 'Temperature', we know it should be b/c we construct it that way
    if data.columns[0] != "Temperature":
        raise ValueError("The first column must be 'Temperature'.")
    min_temps = {}
    for col in data.columns:  # Skip the first column (Temperature)
        if col in ["Temperature", "index"]:
            continue
        min_index = data[col].idxmin()
        # if min_index is not None:
        # BUG? this should probnably always be an int
        min_temp = data["Temperature"].iloc[int(min_index)]
        min_temps[col] = min_temp
    # need to convert the min_temps dictionary to a DataFrame
    min_temps_df = pd.DataFrame(list(min_temps.items()), columns=["unqcond", "min_temperature"])
    # Save the min temperatures to a CSV file
    min_temps_df = split_unqcon_column(min_temps_df)
    min_temps_path = ctx.experiment_dir / StepFiles.MIN_TEMPERATURES_DATA
    min_temps_df.to_csv(min_temps_path, index=False)
    logging.info(f"Min temperatures saved to {min_temps_path}")
