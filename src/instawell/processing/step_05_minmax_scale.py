import logging

import pandas as pd

from instawell.core.exp_context import ExperimentContext
from instawell.core.steps import StepFiles
from instawell.utils.logging_util import setup_experiment_logging

# set logging level to INFO
logger = logging.getLogger(__name__)


def _load_data(ctx: ExperimentContext) -> pd.DataFrame:
    long_data_path = ctx.experiment_dir / StepFiles.BG_SUB_DATA_LONG.value
    if not long_data_path.exists():
        raise FileNotFoundError(
            f"Long format background subtracted data file not found: {long_data_path}"
        )
    long_data = pd.read_csv(long_data_path)
    return long_data


def min_max_scale(ctx: ExperimentContext) -> None:
    """
    Scale each background-subtracted trace to the [0, 1] range to aid
    shape-comparison QC.

    Parameters
    ----------
    ctx : ExperimentContext
        Experiment context pointing at background-subtracted data.

    Side Effects
    ------------
    - Reads ``04_bg_subtracted_data_long.csv`` (and optionally the wide file to
      preserve column order).
    - Writes ``05_min_max_scaled_data_long.csv`` and
      ``05_min_max_scaled_data.csv``.

    Raises
    ------
    FileNotFoundError
        If the background-subtracted long file is missing.
    ValueError
        If any scaled column falls outside [0, 1], indicating bad input.
    """
    if ctx.log_to_file:
        setup_experiment_logging(
            experiment_dir=ctx.experiment_dir, filename="experiment.log", level=ctx.log_level
        )

    # ---- Load Long Format Data ----
    long_data = _load_data(ctx)

    # ---- Define Scaling Function ----
    def scale_group(group: pd.Series) -> pd.Series:
        min_val = group.min()
        max_val = group.max()
        denominator = max_val - min_val
        if denominator == 0:
            # Log a warning for the specific group (unique condition)
            unqcond = long_data.loc[group.index, "unqcond"].iloc[0]
            logger.warning("Condition '%s' has no variance and will not be scaled.", unqcond)
            return group  # Return original values if no variance
        return (group - min_val) / denominator

    # ---- Apply Scaling ----
    long_data["value"] = long_data.groupby("unqcond")["value"].transform(scale_group)

    # ---- Post-Scaling Verification ----
    # Using a small tolerance for floating point comparisons
    if not (long_data["value"].min() >= -1e-9 and long_data["value"].max() <= 1 + 1e-9):
        raise ValueError(
            "Data not scaled between 0 and 1. "
            f"Min: {long_data['value'].min()}, Max: {long_data['value'].max()}"
        )

    # ---- Save Long Format Data ----
    scaled_long_path = ctx.experiment_dir / StepFiles.MIN_MAX_SCALED_DATA_LONG.value
    long_data.to_csv(scaled_long_path, index=False)
    logger.info("Min-max scaled long data saved to %s", scaled_long_path)

    # ---- Create and Save Wide Format Data ----
    wide_data = long_data.pivot(
        index="Temperature", columns="unqcond", values="value"
    ).reset_index()

    # Re-order columns to match the original wide format for consistency
    original_wide_path = ctx.experiment_dir / StepFiles.BG_SUB_DATA.value
    if original_wide_path.exists():
        original_wide = pd.read_csv(original_wide_path)
        original_cols = original_wide.columns
        final_cols = [col for col in original_cols if col in wide_data.columns]
        wide_data = wide_data[final_cols]
    else:
        logger.warning(
            "Could not find original wide data file to match column order: %s",
            original_wide_path,
        )

    scaled_wide_path = ctx.experiment_dir / StepFiles.MIN_MAX_SCALED_DATA.value
    wide_data.to_csv(scaled_wide_path, index=False)
    logger.info("Min-max scaled wide data saved to %s", scaled_wide_path)
