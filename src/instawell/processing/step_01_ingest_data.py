import json
import logging
from collections import defaultdict

import pandas as pd

from instawell.core.data_models import Condition, Replicate
from instawell.core.exp_context import ExperimentContext
from instawell.core.parser import parse_condition_string
from instawell.core.steps import StepFiles
from instawell.utils.logging_util import setup_experiment_logging

logger = logging.getLogger(__name__)


def _parse_layout(layout_df: pd.DataFrame) -> set[str]:
    """
    Parses the layout to grab the unique conditions
    """
    unique_conditions: set[str] = set()
    for col in layout_df.columns:
        if col.startswith("well") or col.startswith("Well") or col.startswith("WELL"):
            continue
        unique_conditions.update(layout_df[col].unique())
    return unique_conditions


def _validate_layout(layout_df: pd.DataFrame) -> None:
    """
    Validates the layout DataFrame for required structure.
    """
    if layout_df.empty:
        raise ValueError("Layout DataFrame is empty.")
    if layout_df.shape[1] < 2:
        raise ValueError(
            "Layout DataFrame must have at least one condition column besides the well identifier."
        )
    # if it contains any NaN values in condition columns, raise error
    if layout_df.isna().any().any():
        raise ValueError("Layout DataFrame contains NaN values in condition columns.")

    for index, row in layout_df.iterrows():
        for col in layout_df.columns:
            if col.lower().startswith("well"):
                continue
            condition_str = row[col]
            if pd.isna(condition_str):
                raise ValueError(
                    f"Missing condition in layout at row {index}, column {col}. Ensure all conditions are filled, with blanks marked using the empty condition placeholder."
                )


def _parse_conditions(
    layout_df: pd.DataFrame,
    unique_conditions: set[str],
    ctx: ExperimentContext,
) -> dict[str, Condition]:
    """
    Extract unique conditions from the layout DataFrame.
    """
    experiment_info: dict[str, Condition] = defaultdict(Condition)
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
                condition_obj = parse_condition_string(
                    condition_str,
                    delimiter=ctx.condition_separator,
                    fields=ctx.condition_fields,
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

            full_name = condition_obj.full_name

            if full_name in unique_conditions:
                experiment_info[full_name] = condition_obj
                # if its the first time we see it, we remove it from unique_conditions to help keep track of unaccounted
                unique_conditions.remove(full_name)
                experiment_info[full_name].replicates.append(replicate)
            else:
                experiment_info[full_name].replicates.append(replicate)

    # Check for conditions with only one replicate
    for condition, info in experiment_info.items():
        if len(info.replicates) == 1:
            logger.warning(f"Condition {condition} has only one replicate. Check for typos!")

    # Check if all replicates are accounted for
    if len(unique_conditions) == 0 or (
        len(unique_conditions) == 1 and ctx.empty_condition_mask in unique_conditions
    ):
        logger.info("All replicates accounted for in the layout data.")
    else:
        logger.warning(
            f"There may be an error with layout data: The following condition(s) may be causing issues {unique_conditions}. Please check the layout data."
        )
    return experiment_info


def _save_experiment_info(experiment_info: dict[str, Condition], ctx: ExperimentContext) -> None:
    info_path = ctx.experiment_dir / "experiment_info.json"
    info_path.parent.mkdir(parents=True, exist_ok=True)

    # Double check .gitignore
    with open(info_path.parent / ".gitignore", "w") as f:
        f.write("*\n")

    with open(info_path, "w") as f:
        json.dump({k: v.model_dump() for k, v in experiment_info.items()}, f, indent=4)


def _get_unique_conditions(
    layout_df: pd.DataFrame,
    ctx: ExperimentContext,
) -> dict[str, Condition]:
    unq_conditions = _parse_layout(layout_df)
    experiment_info = _parse_conditions(layout_df, unq_conditions, ctx)
    _save_experiment_info(experiment_info, ctx)
    return experiment_info


def _set_temperature_column(
    df: pd.DataFrame,
    ctx: ExperimentContext,
) -> pd.DataFrame:
    """
    Ensures the temperature column is correctly named.
    """
    temp_col = None
    for col in df.columns:
        if col.lower() == ctx.temperature_column.lower():
            temp_col = col
            break
    if temp_col is None:
        raise ValueError(
            f"Temperature column '{ctx.temperature_column}' not found in data columns: {df.columns.tolist()}"
        )
    if temp_col != "Temperature":
        df = df.rename(columns={temp_col: "Temperature"})
    return df


def _initial_raw_data_organize(
    initial_raw_data: pd.DataFrame,
    experiment_info: dict[str, Condition],
    ctx: ExperimentContext,
) -> pd.DataFrame:
    """
    Organizes the raw data based on the layout data.
    """

    # Create a new DataFrame to hold the organized data, hardcode Temperature as the temperature column
    raw_data_long = initial_raw_data.melt(
        id_vars=[ctx.temperature_column], var_name="well", value_name="value"
    )

    # Force temperature column to be named "Temperature"
    if ctx.temperature_column != "Temperature":
        raw_data_long = raw_data_long.rename(columns={ctx.temperature_column: "Temperature"})

    # add the condition columns
    dims_list = list(ctx.condition_fields)
    for dim in dims_list:
        raw_data_long[dim] = ""
    # create empty columns for each condition field
    raw_data_long[dims_list] = raw_data_long[dims_list].astype("string").fillna("")
    raw_data_long["well"] = raw_data_long["well"].astype("string")

    sep = ctx.condition_separator
    for _, info in experiment_info.items():
        # for dim in ctx.condition_fields:
        dims = ctx.condition_fields

        # ligand = info.ligand_name
        # protein = info.protein_name
        # buffer = info.buffer_condition
        # concentration = info.concentration

        replicate_wells = [rep.well_name for rep in info.replicates]

        # create a mask for the rows that have a well that is in replicate_wells
        mask = raw_data_long["well"].isin(replicate_wells)

        # add the columns to the raw data long
        for dim in dims:
            value = info.dimensions[dim]
            raw_data_long.loc[mask, dim] = value

        # raw_data_long.loc[mask, "ligand"] = ligand
        # raw_data_long.loc[mask, "protein"] = protein
        # raw_data_long.loc[mask, "buffer"] = buffer
        # raw_data_long.loc[mask, "concentration"] = concentration

    # raw_data_long["well_unqcond"] = (
    #     raw_data_long["well"]
    #     + sep
    #     + raw_data_long["concentration"]
    #     + sep
    #     + raw_data_long["ligand"]
    #     + sep
    #     + raw_data_long["protein"]
    #     + sep
    #     + raw_data_long["buffer"]
    # )
    # dims = list(ctx.condition_fields)
    raw_data_long["well_unqcond"] = (
        raw_data_long["well"] + sep + raw_data_long[dims_list].agg(sep.join, axis=1)
    )
    raw_data_long["unqcond"] = raw_data_long[dims_list].agg(sep.join, axis=1)
    return raw_data_long


def ingest_data(
    ctx: ExperimentContext,
) -> None:
    """
    Ingests raw data and layout data using the provided experiment context.

    Parameters
    ----------
    ctx : ExperimentContext
        The experiment context containing configuration and paths.

    Notes
    -----
    01_raw_organized_data.csv : A CSV file containing the organized raw data. It is pivoted to a long format so that every row is a single measurement. This is useful for filtering and averaging later.
    experiment_info.json : file containing details about unique conditions and replicates.

    Raises
    ------
    - FileNotFoundError
        If the raw data or layout data files are not found.
    - ValueError
        If the temperature column is not found in the raw data.
    """

    if ctx.log_to_file:
        setup_experiment_logging(
            experiment_dir=ctx.experiment_dir, filename="experiment.log", level=ctx.log_level
        )

    initial_raw_data = pd.read_csv(ctx.raw_data_path)

    layout_data = pd.read_csv(ctx.layout_data_path)

    experiment_info = _get_unique_conditions(layout_data, ctx)

    logger.info(f"Extracted {len(experiment_info)} unique conditions from layout data.")

    initial_raw_data = _set_temperature_column(initial_raw_data, ctx)

    raw_organized_data = _initial_raw_data_organize(initial_raw_data, experiment_info, ctx)

    organized_data_path = ctx.experiment_dir / StepFiles.INGESTED_DATA.value

    raw_organized_data.to_csv(organized_data_path, index=False)

    logger.info(f"Organized data saved to {organized_data_path}")
