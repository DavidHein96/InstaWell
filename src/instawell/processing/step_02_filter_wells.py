import logging

import pandas as pd

from instawell.core.exceptions import PrerequisiteStepError
from instawell.core.exp_context import ExperimentContext
from instawell.core.steps import StepFiles
from instawell.utils.logging_util import setup_experiment_logging

# set logging level to INFO
logger = logging.getLogger(__name__)


def filter_wells(
    ctx: ExperimentContext,
    *,
    wells_to_filter: list[str] | None = None,
) -> None:
    """
    Filters the organized data based on the provided parameters. MUST still be run even if no wells are to be filtered, in order to record that no wells were filtered.
    """
    if ctx.log_to_file:
        setup_experiment_logging(
            experiment_dir=ctx.experiment_dir, filename="experiment.log", level=ctx.log_level
        )

    organized_data_path = ctx.experiment_dir / StepFiles.INGESTED_DATA
    try:
        organized_data = pd.read_csv(organized_data_path)
    except FileNotFoundError as exc:
        raise PrerequisiteStepError(
            f"Missing prerequisite data file: {organized_data_path}\n"
            "This usually means step 1 has not been run yet for this experiment.\n"
            "Please run `step_01_organize_data` (or the equivalent first step) "
            f"for experiment '{ctx.experiment_name}' and try again."
        ) from exc

    filtered_data_path = ctx.experiment_dir / StepFiles.FILTERED_DATA
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
        if col not in organized_data.columns:
            raise ValueError(f"Missing required column: {col} in the data.")
    if not wells_to_filter:
        logger.info("No wells to filter. Returning the original data.")
        # save the organized data to a csv file in the experiment directory
        organized_data.to_csv(filtered_data_path, index=False)
        logger.info(f"Filtered data saved to {filtered_data_path}")
        # save a .txt file with the filtered wells
        with open(ctx.experiment_dir / StepFiles.FILTERED_WELLS, "w") as f:
            f.write("No wells filtered.")
        return

    # first check if each well in wells is in the organized_data
    for well in wells_to_filter:
        if well not in organized_data["well"].unique():
            raise ValueError(
                f"Well {well} not found in organized data. Please check the well names."
            )
    # Filter the organized data to remove the specified wells
    for well in wells_to_filter:
        organized_data = organized_data[organized_data["well"] != well]
        logger.info(f"Filtered out well: {well}")

    # save the filtered data to a csv file in the experiment directory
    organized_data.to_csv(filtered_data_path, index=False)
    logger.info(f"Filtered data saved to {filtered_data_path}")

    # save a .txt file with the filtered wells
    with open(ctx.experiment_dir / StepFiles.FILTERED_WELLS, "w") as f:
        f.write("\n".join(wells_to_filter))
