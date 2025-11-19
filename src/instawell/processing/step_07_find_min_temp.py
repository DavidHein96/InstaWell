import logging

import pandas as pd

from instawell.core.exp_context import ExperimentContext
from instawell.core.steps import StepFiles
from instawell.utils.logging_util import setup_experiment_logging
from instawell.utils.utils import split_unqcon_column

# set logging level to INFO
logger = logging.getLogger(__name__)


def find_min_temperature(ctx: ExperimentContext) -> None:
    """
    Finds the temperature at the minimum of the derivative curve for each condition.

    This step uses the long-format derivative data. It groups the data by each
    unique condition, finds the index of the minimum derivative value within each
    group, and retrieves the corresponding temperature. The final output is a table
    mapping each condition to its calculated minimum temperature.

    Parameters
    ----------
    ctx : ExperimentContext
        _description_

    Raises
    ------
    FileNotFoundError
        _description_
    """
    if ctx.log_to_file:
        setup_experiment_logging(
            experiment_dir=ctx.experiment_dir, filename="experiment.log", level=ctx.log_level
        )

    # ---- Load Long Format Derivative Data ----
    long_data_path = ctx.experiment_dir / StepFiles.DERIVATIVE_DATA_LONG.value
    if not long_data_path.exists():
        raise FileNotFoundError(f"Long format derivative data file not found: {long_data_path}")
    long_data = pd.read_csv(long_data_path)

    # ---- Find Temperature at Minimum Derivative for Each Condition ----
    # Get the index of the minimum value for each group
    min_indices = long_data.groupby("unqcond")["value"].idxmin()
    # Select the rows corresponding to these minimums
    min_temps_df = long_data.loc[min_indices].copy()

    # ---- Prepare Final DataFrame ----
    # We only need the condition and the temperature
    min_temps_df = min_temps_df[["unqcond", "Temperature"]]
    # Rename 'Temperature' to 'min_temperature' for clarity
    min_temps_df = min_temps_df.rename(columns={"Temperature": "min_temperature"})

    # Split the 'unqcond' column back into its component parts
    if "unqcond" in min_temps_df.columns:
        min_temps_df = split_unqcon_column(
            min_temps_df, fields=ctx.condition_fields, delimiter=ctx.condition_separator
        )

    # ---- Save Outputs ----
    # Theres only one format for this
    min_temps_path = ctx.experiment_dir / StepFiles.MIN_TEMPERATURES_DATA.value
    min_temps_df.to_csv(min_temps_path, index=False)
    logger.info("Min temperatures (wide) saved to %s", min_temps_path)
