import logging

import pandas as pd

from instawell.core.exp_context import ExperimentContext
from instawell.core.steps import StepFiles
from instawell.utils.logging_util import setup_experiment_logging

# set logging level to INFO
logger = logging.getLogger(__name__)


def min_max_scale(ctx: ExperimentContext) -> None:
    """Min-max scales the background subtracted data."""
    if ctx.log_to_file:
        setup_experiment_logging(
            experiment_dir=ctx.experiment_dir, filename="experiment.log", level=ctx.log_level
        )
    # Build the path to the background subtracted data
    bg_data_path = ctx.experiment_dir / StepFiles.BG_SUB_DATA
    if not bg_data_path.exists():
        raise FileNotFoundError(f"BG subtracted data file not found: {bg_data_path}")
    # Load the background subtracted data
    data = pd.read_csv(bg_data_path)
    # ensure the first column is 'Temperature', we know it should be b/c we construct it that way
    if data.columns[0] != "Temperature":
        raise ValueError("The first column must be 'Temperature'.")
    for col in data.columns:
        if col.startswith("Temperature"):
            continue
        if data[col].max() - data[col].min() == 0:
            continue  # Avoid division by zero
        data[col] = (data[col] - data[col].min()) / (data[col].max() - data[col].min())
    # ensure columns except Temperature are scaled between 0 and 1
    for col in data.columns:
        if col.startswith("Temperature"):
            continue
        if data[col].min() < 0 or data[col].max() > 1:
            raise ValueError(f"Column {col} not scaled between 0 and 1.")
    # ensure Temperature column is unchanged
    if not data["Temperature"].equals(pd.read_csv(bg_data_path)["Temperature"]):
        raise ValueError("Temperature column has been altered during scaling.")
    # Save the min-max scaled data
    scaled_data_path = ctx.experiment_dir / StepFiles.MIN_MAX_SCALED_DATA
    data.to_csv(scaled_data_path, index=False)
    logging.info(f"Min-max scaled data saved to {scaled_data_path}")
