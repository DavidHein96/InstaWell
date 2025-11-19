import logging

import numpy as np
import pandas as pd

from instawell.core.exp_context import ExperimentContext
from instawell.core.steps import StepFiles
from instawell.utils.logging_util import setup_experiment_logging

# set logging level to INFO
logger = logging.getLogger(__name__)


def _load_data(ctx: ExperimentContext) -> pd.DataFrame:
    bg_data_path = ctx.experiment_dir / StepFiles.BG_SUB_DATA.value
    if not bg_data_path.exists():
        raise FileNotFoundError(f"Background subtracted data file not found: {bg_data_path}")
    data = pd.read_csv(bg_data_path)

    if data.columns[0] != "Temperature":
        raise ValueError("The first column must be 'Temperature'.")
    return data


def calculate_derivative(ctx: ExperimentContext) -> None:
    """
    _summary_

    Parameters
    ----------
    ctx : ExperimentContext
        _description_
    """
    if ctx.log_to_file:
        setup_experiment_logging(
            experiment_dir=ctx.experiment_dir, filename="experiment.log", level=ctx.log_level
        )

    data = _load_data(ctx)

    # ---- Calculate Derivative ----
    data_derivative = data.copy()
    # Skip the first column ('Temperature')
    for col in data.columns[1:]:
        # We calculate negative so the peaks point upwards
        data_derivative[col] = np.gradient(data[col], data["Temperature"]) * -1

    # ---- Min-Max Scale the Derivative Data ----
    # we min max AFTER derivative calc
    for col in data_derivative.columns:
        if col == "Temperature":
            continue

        col_min = data_derivative[col].min()
        col_max = data_derivative[col].max()
        denominator = col_max - col_min

        if denominator == 0:
            logger.warning("Column '%s' has no variance in derivative data; cannot scale.", col)
            continue  # Avoid division by zero

        data_derivative[col] = (data_derivative[col] - col_min) / denominator

    # ---- Save Wide Format Data ----
    derivative_data_path = ctx.experiment_dir / StepFiles.DERIVATIVE_DATA.value
    data_derivative.to_csv(derivative_data_path, index=False)
    logger.info("Derivative wide data saved to %s", derivative_data_path)

    # ---- Create and Save Long Format Data ----

    value_cols = [col for col in data_derivative.columns if col != "Temperature"]
    long_data = data_derivative.melt(
        id_vars=["Temperature"],
        value_vars=value_cols,
        var_name="unqcond",
        value_name="value",
    )
    derivative_long_path = ctx.experiment_dir / StepFiles.DERIVATIVE_DATA_LONG.value
    long_data.to_csv(derivative_long_path, index=False)
    logger.info("Derivative long data saved to %s", derivative_long_path)
