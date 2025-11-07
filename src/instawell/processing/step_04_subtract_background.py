import logging

import pandas as pd

from instawell.core.exp_context import ExperimentContext
from instawell.core.steps import StepFiles
from instawell.utils.logging_util import setup_experiment_logging

# set logging level to INFO
logger = logging.getLogger(__name__)


def find_background_column(
    data: pd.DataFrame,
    concentration: str,
    ligand: str,
    protein: str,
    buffer: str,
    sep: str = "|",
    non_protein_control_marker: str = "NPC",
) -> str | None:
    """Helper function to find the background column in the data."""
    if protein == non_protein_control_marker:
        return None  # Dont remove background for NPC
    for col in data.columns:
        if f"{concentration}{sep}{ligand}{sep}{non_protein_control_marker}{sep}{buffer}" in col:
            return col
    return None


def subtract_background(ctx: ExperimentContext) -> None:
    """Finds the background column for each unique condition and subtracts it from the data. The BG col should be in the format 'concentration_ligand_NPC_buffer'."""
    if ctx.log_to_file:
        setup_experiment_logging(
            experiment_dir=ctx.experiment_dir, filename="experiment.log", level=ctx.log_level
        )
    # Build the path to the averaged data
    averaged_data_path = ctx.experiment_dir / StepFiles.AVERAGED_DATA
    if not averaged_data_path.exists():
        raise FileNotFoundError(f"Averaged data file not found: {averaged_data_path}")
    # Load the averaged data
    data = pd.read_csv(averaged_data_path)

    # create a dictionary of the column names
    columns_dict = {}
    for col in data.columns:
        if col == "Temperature":
            continue
        columns_dict[col] = False
    # get number of items in the ctx.fields tuple
    num_fields = len(ctx.fields)
    for col in data.columns:
        parts = col.split(ctx.condition_separator)
        if len(parts) < num_fields:
            continue
        # Note: we create this df so we know the order of fields
        concentration = parts[0]
        ligand = parts[1]
        protein = parts[2]
        buffer = parts[3]

        background_col = find_background_column(
            data,
            concentration,
            ligand,
            protein,
            buffer,
            ctx.condition_separator,
            ctx.non_protein_control_marker,
        )

        if background_col and background_col in data.columns:
            data[col] = data[col] - data[background_col]
            columns_dict[background_col] = True
            columns_dict[col] = True
            logging.info(f"Background subtracted for {col} using {background_col} as background.")

    # ensure that all columns have been marked as True
    for col, marked in columns_dict.items():
        if not marked:
            logging.warning(
                f"Warning: Column {col} was not processed for background subtraction. Check if the background column exists."
            )

    # Remove the background columns
    data = data.loc[:, ~data.columns.str.contains(ctx.non_protein_control_marker)]

    # Save the data with background subtracted
    background_subtracted_path = ctx.experiment_dir / StepFiles.BG_SUB_DATA
    data.to_csv(background_subtracted_path, index=False)
    logger.info(f"Background subtracted data saved to {background_subtracted_path}")
