import json
from collections import defaultdict
from typing import List, Optional

import pandas as pd
from pydantic import BaseModel, Field, FilePath

# from validation import (
#     LongData,
#     LongDataRaw,
#     LongDataAvg,
#     WideDataNumeric,
#     WideDataNoBase,
#     WideDataMinMax,
#     LongDataMinMax,
#     LongDataDT,
#     LongDataDTMinMax,
#     MinTempData,
#     LayoutDynamicData,
#     validate_df_dynamic_model,
# )


class Replicate(BaseModel):
    well_row: str
    well_column: str
    well_name: str
    # temp_data: Optional[pd.DataFrame] = None


class UniqueCondition(BaseModel):
    full_name: str = ""
    concentration: str = ""
    ligand_name: str = ""
    protein_name: str = ""
    buffer_condition: str = ""
    replicates: List[Replicate] = Field(default_factory=list)


def get_unique_conditions(
    layout_data: FilePath, print_to_check: Optional[bool] = False
) -> dict[str, UniqueCondition]:
    layout_df = pd.read_csv(layout_data)

    experiment_info = defaultdict(UniqueCondition)
    replicates = set()
    # loop through columns in layout
    for col in layout_df.columns:
        if col.startswith("well") or col.startswith("Well"):
            continue
        replicates.update(layout_df[col].unique())

    for index, row in layout_df.iterrows():
        for col in layout_df.columns:
            if col.startswith("well") or col.startswith("Well"):
                continue
            condition = row[col]

            if pd.isna(condition) or condition == "" or condition == "0_0_0_0":
                continue
            parts = condition.split("_")
            if len(parts) < 4:
                continue
            # print(parts)
            full_name = condition
            # print(full_name)
            concentration = parts[-4]
            ligand_name = parts[-3]
            protein_name = parts[-2]
            buffer_condition = parts[-1]

            replicate = Replicate(
                well_row=row["Well"],
                well_column=str(col),
                well_name=row["Well"] + str(col),
            )
            condition = UniqueCondition(
                full_name=full_name,
                concentration=concentration,
                ligand_name=ligand_name,
                protein_name=protein_name,
                buffer_condition=buffer_condition,
            )
            if full_name in replicates:
                experiment_info[full_name] = condition
                # remove the replacate from the replicates set
                replicates.remove(full_name)
                experiment_info[full_name].replicates.append(replicate)
            else:
                experiment_info[full_name].replicates.append(replicate)
    if print_to_check:
        # Save the experiment info to a JSON file
        # combine the stem of the file with the experiment_info
        info_path = layout_data.stem + "_experiment_info.json"
        with open(info_path, "w") as f:
            # exp_dict = {k: v.model_dump() for k, v in experiment_info.items()}
            json.dump({k: v.model_dump() for k, v in experiment_info.items()}, f, indent=4)
    return experiment_info


def initial_raw_data_organize(
    initial_raw_data: pd.DataFrame,
    experiment_info: dict[str, UniqueCondition],
) -> pd.DataFrame:
    """
    Organizes the raw data based on the layout data.
    """
    # Create a new DataFrame to hold the organized data
    raw_data_long = initial_raw_data.melt(
        id_vars=["Temperature"], var_name="well", value_name="value"
    )
    for condition, info in experiment_info.items():
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
            + "_"
            + raw_data_long["concentration"]
            + "_"
            + raw_data_long["ligand"]
            + "_"
            + raw_data_long["protein"]
            + "_"
            + raw_data_long["buffer"]
        )
    return raw_data_long


def filter_organized_data(
    organized_data: pd.DataFrame,
    wells_to_filter: list[str],
) -> pd.DataFrame:
    """
    Filters the organized data based on the provided parameters.
    """
    # first check if each well in wells is in the organized_data
    for well in wells_to_filter:
        if well not in organized_data["well"].unique():
            print(f"Warning: Well {well} not found in organized data.")
            continue
    # Filter the organized data to remove the specified wells
    for well in wells_to_filter:
        organized_data = organized_data[organized_data["well"] != well]
        print(f"Filtered out well: {well}")

    return organized_data


def split_unqcon_column(data: pd.DataFrame) -> pd.DataFrame:
    parts = data["unqcond"].str.split("_", expand=True)
    data["concentration"] = parts[0]
    data["ligand"] = parts[1]
    data["protein"] = parts[2]
    data["buffer"] = parts[3]
    return data


def avg_across_replicates(
    organized_data: pd.DataFrame,
) -> pd.DataFrame:
    """
    Averages the data across replicates.
    """
    # Group by the unique condition and temperature, then average the values
    organized_data["unqcond"] = (
        organized_data["concentration"]
        + "_"
        + organized_data["ligand"]
        + "_"
        + organized_data["protein"]
        + "_"
        + organized_data["buffer"]
    )

    # Add a column for the unique condition
    averaged_data = (
        organized_data.groupby(["Temperature", "unqcond"]).agg({"value": "mean"}).reset_index()
    )
    averaged_data_pivot = averaged_data.pivot(
        index="Temperature", columns="unqcond", values="value"
    )

    averaged_data_pivot = split_unqcon_column(averaged_data_pivot)

    return averaged_data_pivot


def _find_background_column(
    averaged_data_pivot: pd.DataFrame,
    concentration: str,
    ligand: str,
    protein: str,
    buffer: str,
) -> Optional[str]:
    if protein == "NPC":
        return None  # Dont remove background for NPC
    for col in averaged_data_pivot.columns:
        if f"{concentration}_{ligand}_NPC_{buffer}" in col:
            return col
    return None


def subtract_background(data: pd.DataFrame) -> pd.DataFrame:
    for col in data.columns:
        parts = col.split("_")
        if len(parts) < 4:
            continue
        concentration = parts[0]
        ligand = parts[1]
        protein = parts[2]
        buffer = parts[3]

        background_col = _find_background_column(data, concentration, ligand, protein, buffer)

        if background_col and background_col in data.columns:
            data[col] = data[col] - data[background_col]
    return data


def min_max_scale(data: pd.DataFrame) -> pd.DataFrame:
    for col in data.columns:
        if col.startswith("Temperature"):
            continue
        if data[col].max() - data[col].min() == 0:
            continue  # Avoid division by zero
        data[col] = (data[col] - data[col].min()) / (data[col].max() - data[col].min())
    return data
