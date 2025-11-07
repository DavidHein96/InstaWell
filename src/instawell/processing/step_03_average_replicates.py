import logging

import pandas as pd

from instawell.core.exceptions import PrerequisiteStepError
from instawell.core.exp_context import ExperimentContext
from instawell.core.steps import StepFiles
from instawell.utils.logging_util import setup_experiment_logging
from instawell.utils.utils import convert_concentration_to_float

# set logging level to INFO
logger = logging.getLogger(__name__)


def _avg_across_replicates(
    organized_data: pd.DataFrame,
    sep: str = "|",
) -> pd.DataFrame:
    """
    Averages the data across replicates.
    """
    # Group by the unique condition and temperature, then average the values
    organized_data["unqcond"] = (
        organized_data["concentration"]
        + sep
        + organized_data["ligand"]
        + sep
        + organized_data["protein"]
        + sep
        + organized_data["buffer"]
    )
    # Drop well_unqcond as it is not needed for averaging
    # organized_data = organized_data.drop(columns=["well_unqcond"])
    # Add a column for the unique condition
    # averaged_data = raw_data_long.groupby(['Temperature', 'combination2']).agg({'value': 'mean'}).reset_index()

    averaged_data = (
        organized_data.groupby(["Temperature", "unqcond"]).agg({"value": "mean"}).reset_index()
    )

    averaged_data_pivot = averaged_data.pivot(
        index="Temperature", columns="unqcond", values="value"
    )

    # averaged_data_pivot = split_unqcon_column(averaged_data_pivot)

    return averaged_data_pivot


def average_accross_replicates(ctx: ExperimentContext) -> None:
    """
    The second step of the data processing pipeline.
    It filters the organized data based on the provided parameters.
    """
    if ctx.log_to_file:
        setup_experiment_logging(
            experiment_dir=ctx.experiment_dir, filename="experiment.log", level=ctx.log_level
        )
    filtered_data_path = ctx.experiment_dir / StepFiles.FILTERED_DATA

    if not filtered_data_path.exists():
        raise PrerequisiteStepError(f"Filtered data file not found: {filtered_data_path}")
    # Load the filtered data
    filtered_data = pd.read_csv(filtered_data_path)
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
        if col not in filtered_data.columns:
            raise ValueError(f"Missing required column: {col} in the data.")
    sep = ctx.condition_separator
    averaged_data = _avg_across_replicates(organized_data=filtered_data, sep=sep)

    # in the averaged across replicates data, we need to sort the columns (except for Temperature) by matching ligand, protein, and buffer
    # Sort the columns based on ligand, protein, and buffer. then within each group, sort by increasing concentration
    # get the columns except for Temperature
    columns_to_sort = averaged_data.columns[1:]  # Exclude 'Temperature'

    # field_positions = {field: idx for idx, field in enumerate(ctx.fields)}

    sorted_columns = sorted(
        columns_to_sort,
        key=lambda x: (
            x.split(sep)[1],  # ligand
            x.split(sep)[2],  # protein
            x.split(sep)[3],  # buffer
            convert_concentration_to_float(
                x.split(sep)[0]
            ),  # concentration, convert to float for sorting
        ),
    )
    # print(f"Sorted columns: {sorted_columns}")
    # Reorder the columns in the DataFrame
    averaged_data_sorted = averaged_data[sorted_columns]
    # Reset the index to make Temperature a column again
    averaged_data_sorted.reset_index(inplace=True)
    averaged_data.reset_index(inplace=True)
    # Add the Temperature column back to the front
    # averaged_data_sorted.insert(0, "Temperature", averaged_data["Temperature"])

    # Save the averaged data to a CSV file in the experiment directory
    averaged_data_path = ctx.experiment_dir / StepFiles.AVERAGED_DATA
    averaged_data_sorted.to_csv(averaged_data_path, index=False)
    logger.info(f"Averaged data saved to {averaged_data_path}")
