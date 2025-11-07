import json
import logging
from collections import defaultdict

import pandas as pd

from instawell.core.data_models import Replicate, UniqueCondition
from instawell.core.exp_context import ExperimentContext
from instawell.core.parser import condition_from_string
from instawell.core.steps import StepFiles
from instawell.utils.logging_util import setup_experiment_logging

logger = logging.getLogger(__name__)


def _parse_layout(layout_df: pd.DataFrame, replicates: set[str]) -> None:
    """
    Modifies replicates in place
    """
    for col in layout_df.columns:
        if col.startswith("well") or col.startswith("Well"):
            continue
        replicates.update(layout_df[col].unique())


def _parse_conditions(
    layout_df: pd.DataFrame,
    replicates: set[str],
    experiment_info: dict[str, UniqueCondition],
    ctx: ExperimentContext,
) -> None:
    """
    Extract unique conditions from the layout DataFrame.
    Currently a placeholder for any future condition extraction steps.
    """
    _well_identifier = ctx.well_col_identifier.strip().lower()
    for index, row in layout_df.iterrows():
        for col in layout_df.columns:
            if col.lower().startswith(_well_identifier):
                continue
            condition_str = row[col]

            # Skip empty or placeholder conditions
            if condition_str in {ctx.empty_condition_mask, ""}:
                continue
            if pd.isna(condition_str):
                continue
            # Use the new parser to extract components
            try:
                condition_obj = condition_from_string(
                    condition_str,
                    delimiter=ctx.condition_separator,
                    fields=ctx.fields,
                    include_replicates=False,  # We'll add replicates manually
                )
            except ValueError as e:
                logger.warning(
                    f"Failed to parse condition '{condition_str}' in row {index}, column {col}: {e}"
                )
                continue

            # Create a replicate for this well
            replicate = Replicate(
                well_row=row[ctx.well_col_identifier],
                well_column=str(col),
                well_name=row[ctx.well_col_identifier] + str(col),
            )

            # Get the full condition name
            full_name = condition_obj.full_name

            # Add to experiment info
            if full_name in replicates:
                experiment_info[full_name] = condition_obj
                replicates.remove(full_name)
                experiment_info[full_name].replicates.append(replicate)
            else:
                experiment_info[full_name].replicates.append(replicate)

    # Check for conditions with only one replicate
    for condition, info in experiment_info.items():
        if len(info.replicates) == 1:
            logger.warning(f"Condition {condition} has only one replicate. Check for typos!")

    # Check if all replicates are accounted for
    if len(replicates) == 0 or (
        len(replicates) == 1 and ctx.empty_condition_placeholder in replicates
    ):
        logger.info("All replicates accounted for in the layout data.")
    else:
        logger.warning(
            f"There may be an error with layout data: {replicates}. Please check the layout data."
        )


def _save_experiment_info(
    experiment_info: dict[str, UniqueCondition], ctx: ExperimentContext
) -> None:
    # Save experiment info to JSON
    info_path = ctx.experiment_dir / "experiment_info.json"
    info_path.parent.mkdir(parents=True, exist_ok=True)

    # Create .gitignore in experiment directory
    with open(info_path.parent / ".gitignore", "w") as f:
        f.write("*\n")

    # Save the experiment info
    with open(info_path, "w") as f:
        json.dump({k: v.model_dump() for k, v in experiment_info.items()}, f, indent=4)


def _get_unique_conditions(
    layout_df: pd.DataFrame,
    ctx: ExperimentContext,
) -> dict[str, UniqueCondition]:
    experiment_info = defaultdict(UniqueCondition)
    replicates: set[str] = set()
    _parse_layout(layout_df, replicates)
    _parse_conditions(layout_df, replicates, experiment_info, ctx)
    _save_experiment_info(experiment_info, ctx)
    return experiment_info


def _initial_raw_data_organize(
    initial_raw_data: pd.DataFrame,
    experiment_info: dict[str, UniqueCondition],
    ctx: ExperimentContext,
) -> pd.DataFrame:
    """
    Organizes the raw data based on the layout data.
    """
    # Create a new DataFrame to hold the organized data, hardcode Temperature as the temperature column
    raw_data_long = initial_raw_data.melt(
        id_vars=[ctx.temperature_column], var_name="well", value_name="value"
    )
    if ctx.temperature_column != "Temperature":
        raw_data_long = raw_data_long.rename(columns={ctx.temperature_column: "Temperature"})

    # Initialize field columns to ensure they exist (regardless of whether loop runs)
    # raw_data_long["ligand"] = ""
    # raw_data_long["protein"] = ""
    # raw_data_long["buffer"] = ""
    # raw_data_long["concentration"] = ""

    sep = ctx.condition_separator
    for _, info in experiment_info.items():
        ligand = info.ligand_name
        protein = info.protein_name
        buffer = info.buffer_condition
        concentration = info.concentration

        replicate_wells = [rep.well_name for rep in info.replicates]

        # create a mask for the rows that have a well that is in replicate_wells
        mask = raw_data_long["well"].isin(replicate_wells)

        # add the columns to the raw data long

        raw_data_long.loc[mask, "ligand"] = ligand
        raw_data_long.loc[mask, "protein"] = protein
        raw_data_long.loc[mask, "buffer"] = buffer
        raw_data_long.loc[mask, "concentration"] = concentration
    raw_data_long["well_unqcond"] = (
        raw_data_long["well"]
        + sep
        + raw_data_long["concentration"]
        + sep
        + raw_data_long["ligand"]
        + sep
        + raw_data_long["protein"]
        + sep
        + raw_data_long["buffer"]
    )
    return raw_data_long


def ingest_data(
    ctx: ExperimentContext,
) -> None:
    """
    The first step of the data processing pipeline.
    It reads the raw data and layout data, gets the unique conditions,
    and organizes the raw data based on the layout data.

    Args:
        ctx: ExperimentContext containing experiment configuration, can be from setup_experiment() or from load_experiment_context()

    Examples:
        >>> # Default field order
        >>> first_step("raw.csv", "layout.csv", "exp1")
        >>> # Custom field order
        >>> first_step("raw.csv", "layout.csv", "exp1",
        ...            fields=("ligand", "protein", "concentration", "buffer"))
    """

    if ctx.log_to_file:
        setup_experiment_logging(
            experiment_dir=ctx.experiment_dir, filename="experiment.log", level=ctx.log_level
        )
    initial_raw_data = pd.read_csv(ctx.raw_data_path)
    layout_data = pd.read_csv(ctx.layout_data_path)
    # Copy the raw data and layout data to the experiment directory

    # Get unique conditions from the layout data
    experiment_info = _get_unique_conditions(layout_data, ctx)

    # Organize the raw data based on the layout data
    raw_organized_data = _initial_raw_data_organize(initial_raw_data, experiment_info, ctx)

    # write the organized data to a csv file in the experiment directory
    organized_data_path = ctx.experiment_dir / StepFiles.INGESTED_DATA
    raw_organized_data.to_csv(organized_data_path, index=False)

    # write to an experiment log file
    logger.info(f"Organized data saved to {organized_data_path}")
