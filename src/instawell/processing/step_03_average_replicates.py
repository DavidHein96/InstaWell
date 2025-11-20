import logging

import pandas as pd

from instawell.core.exceptions import PrerequisiteStepError
from instawell.core.exp_context import ExperimentContext
from instawell.core.steps import StepFiles
from instawell.utils.logging_util import setup_experiment_logging
from instawell.utils.utils import convert_concentration_to_float

logger = logging.getLogger(__name__)


def _avg_across_replicates(
    organized_data: pd.DataFrame,
    sep: str = "|",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Groups by the unique condition and temperature, then average the values.
    It also pivots the data so that each unique condition is a column.
    """

    cols_to_carry = [
        c for c in organized_data.columns if c not in {"value", "well", "well_unqcond"}
    ]
    # Build aggregation: mean for value; 'first' for everything else we want to carry along
    agg_dict = {"value": "mean"}
    for c in cols_to_carry:
        # 'unqcond' and 'Temperature' will be in the groupby keys; including them in agg is harmless
        agg_dict[c] = "first"
    averaged_data_long = organized_data.groupby(["Temperature", "unqcond"], as_index=False).agg(
        agg_dict
    )

    # Make the wide pivot
    averaged_data_pivot = averaged_data_long.pivot(
        index="Temperature", columns="unqcond", values="value"
    )

    return averaged_data_pivot, averaged_data_long


def average_across_replicates(ctx: ExperimentContext) -> None:
    """
    Group the filtered long-form data by temperature/condition and compute the
    replicate means, producing both wide and long tables.

    Parameters
    ----------
    ctx : ExperimentContext
        Experiment context pointing at the output of :func:`filter_wells`.

    Side Effects
    ------------
    - Reads ``02_filtered_organized_data.csv``.
    - Writes ``03_averaged_data.csv`` (wide matrix) and
      ``03_averaged_data_long.csv`` (long table with condition metadata).

    Raises
    ------
    PrerequisiteStepError
        If the filtered data file is missing (step 02 not executed).
    ValueError
        If expected columns are missing, indicating corrupted inputs.
    """
    if ctx.log_to_file:
        setup_experiment_logging(
            experiment_dir=ctx.experiment_dir, filename="experiment.log", level=ctx.log_level
        )
    filtered_data_path = ctx.experiment_dir / StepFiles.FILTERED_DATA.value

    if not filtered_data_path.exists():
        raise PrerequisiteStepError(
            f"Filtered data file not found: {filtered_data_path}, ensure filtering step has been run."
            "The filtering step must be run even if no wells are to be filtered, in order to record that no wells were filtered."
        )
    filtered_data = pd.read_csv(filtered_data_path)

    # ---- Validate columns ----
    base_required = {"Temperature", "value", "well", "unqcond", "well_unqcond"}
    missing = (base_required | set(ctx.condition_fields)) - set(filtered_data.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    sep = ctx.condition_separator
    averaged_data_pivot, averaged_data_long = _avg_across_replicates(
        organized_data=filtered_data, sep=sep
    )

    condition_columns = list(averaged_data_pivot.columns)

    if ctx.condition_fields != ("concentration", "ligand", "protein", "buffer"):
        logger.warning(
            "Custom condition fields detected, but sorting of averaged data columns only supports"
            "the standard fields (concentration, ligand, protein, buffer). Columns will not be sorted."
        )
        sorted_columns = condition_columns
    else:
        sorted_columns = sorted(
            condition_columns,
            key=lambda x: (
                x.split(sep)[1],  # ligand
                x.split(sep)[2],  # protein
                x.split(sep)[3],  # buffer
                convert_concentration_to_float(
                    x.split(sep)[0]
                ),  # concentration, convert to float for sorting
            ),
        )

    averaged_data_sorted = averaged_data_pivot[
        sorted_columns
    ].reset_index()  # brings Temperature back as a column

    averaged_data_path = ctx.experiment_dir / StepFiles.AVERAGED_DATA.value
    averaged_data_sorted.to_csv(averaged_data_path, index=False)

    averaged_data_long_path = ctx.experiment_dir / StepFiles.AVERAGED_DATA_LONG.value
    averaged_data_long.to_csv(averaged_data_long_path, index=False)
    logger.info(f"Averaged data saved to {averaged_data_path}")
    logger.info(f"Averaged long data saved to {averaged_data_long_path}")
