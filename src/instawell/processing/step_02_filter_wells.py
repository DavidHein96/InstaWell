import logging

import pandas as pd

from instawell.core.exceptions import PrerequisiteStepError
from instawell.core.exp_context import ExperimentContext
from instawell.core.steps import StepFiles
from instawell.utils.logging_util import setup_experiment_logging

logger = logging.getLogger(__name__)


def filter_wells(
    ctx: ExperimentContext,
    *,
    wells_to_filter: list[str] | None = None,
) -> None:
    """
    Filters the organized data based on the provided parameters. MUST still be run even if no wells are to be filtered, in order to record that no wells were filtered. To call it with no wells simply run filter_wells(ctx)

    Parameters
    ----------
    ctx : ExperimentContext
    wells_to_filter : list[str] | None, optional
        List of well names to filter out, by default None

    Notes
    -----
    02_filtered_organized_data.csv : CSV file with filtered data
    filtered_wells.txt : Text file listing filtered wells, is "no wells filtered." if none were filtered.

    Raises
    ------
    PrerequisiteStepError
        If data from ingestion step is not found.
    ValueError
        If a well to be filtered is not found in the data, or if a required column is missing (data corruption).
    """
    if wells_to_filter is None:
        logger.info(
            "filter_wells must run even when no wells are provided; continuing with no wells filtered."
        )
        wells_to_filter = []
    if ctx.log_to_file:
        setup_experiment_logging(
            experiment_dir=ctx.experiment_dir, filename="experiment.log", level=ctx.log_level
        )

    organized_data_path = ctx.experiment_dir / StepFiles.INGESTED_DATA.value

    if not organized_data_path.exists():
        raise PrerequisiteStepError(
            f"Data from ingestion step not found: {organized_data_path}, ensure ingestion step has been run."
        )

    organized_data = pd.read_csv(organized_data_path)

    filtered_data_path = ctx.experiment_dir / StepFiles.FILTERED_DATA.value
    # We already know these are there since we made them in step 1, but double check

    # ---- Validate columns ----
    base_required = {"Temperature", "value", "well", "unqcond", "well_unqcond"}
    missing = (base_required | set(ctx.condition_fields)) - set(organized_data.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    # ---- Filter Wells ----
    if not wells_to_filter:
        logger.info("No wells to filter. Returning the original data.")
        organized_data.to_csv(filtered_data_path, index=False)
        logger.info(f"Filtered data saved to {filtered_data_path}")
        # save a .txt file with the filtered wells
        with open(ctx.experiment_dir / StepFiles.FILTERED_WELLS.value, "w") as f:
            f.write("No wells filtered.")
        return

    # first check if each well in wells is in the organized_data
    for well in wells_to_filter:
        if well not in organized_data["well"].unique():
            raise ValueError(
                f"Well {well} not found in organized data. Please check the well names."
            )

    # Filter them out and save back
    for well in wells_to_filter:
        organized_data = organized_data[organized_data["well"] != well]
        logger.info(f"Filtered out well: {well}")

    organized_data.to_csv(filtered_data_path, index=False)
    logger.info(f"Filtered data saved to {filtered_data_path}")

    # ensure captured
    with open(ctx.experiment_dir / StepFiles.FILTERED_WELLS.value, "w") as f:
        f.write("\n".join(wells_to_filter))
