import logging

import numpy as np
import pandas as pd

from instawell.core.exp_context import ExperimentContext
from instawell.core.steps import StepFiles
from instawell.utils.logging_util import setup_experiment_logging

# set logging level to INFO
logger = logging.getLogger(__name__)


def calculate_derivative(ctx: ExperimentContext) -> None:
    """Calclulates the derivative of the background subtracted data with respect to Temperature. And Min-Max scales the data afterwards."""
    if ctx.log_to_file:
        setup_experiment_logging(
            experiment_dir=ctx.experiment_dir, filename="experiment.log", level=ctx.log_level
        )
    # build a path the the bg subtracted data
    bg_data_path = ctx.experiment_dir / StepFiles.BG_SUB_DATA
    if not bg_data_path.exists():
        raise FileNotFoundError(f"BG subtracted data file not found: {bg_data_path}")
    # Load the background subtracted data
    data = pd.read_csv(bg_data_path)
    # ensure the first column is 'Temperature', we know it should be b/c we construct it that way
    if data.columns[0] != "Temperature":
        raise ValueError("The first column must be 'Temperature'.")

    # ensure that the min max scaled data is NOT being passed here
    # Calculate the derivative with respect to Temperature
    data_derivative = data.copy()
    for col in data.columns[1:]:  # Skip the first column (Temperature)
        data_derivative[col] = np.gradient(data[col], data["Temperature"])
        # multiply by -1 to flip the sign
        data_derivative[col] *= -1

    for col in data_derivative.columns:
        if col.startswith("Temperature"):
            continue
        if data_derivative[col].max() - data_derivative[col].min() == 0:
            logger.info(
                f"Column {col} has zero range in derivative data; skipping derivative for this column."
            )
            continue  # Avoid division by zero
        data_derivative[col] = (data_derivative[col] - data_derivative[col].min()) / (
            data_derivative[col].max() - data_derivative[col].min()
        )

    # Save the derivative data
    derivative_data_path = ctx.experiment_dir / StepFiles.DERIVATIVE_DATA
    data_derivative.to_csv(derivative_data_path, index=False)
    logging.info(f"Derivative data saved to {derivative_data_path}")
