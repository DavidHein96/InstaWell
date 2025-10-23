import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd
import plotly.express as px
from pydantic import BaseModel, Field, FilePath

# set logging level to INFO
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


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
    layout_df: pd.DataFrame, experiment_name: str
) -> dict[str, UniqueCondition]:
    # layout_df = pd.read_csv(layout_data)

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
                logging.warning(
                    f"Condition '{condition}' in row {index}, column {col} does not have enough parts to be valid. Check for typos!"
                )
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

    # loop through the experiment info and see if any conditions have only one replicate
    for condition, info in experiment_info.items():
        if len(info.replicates) == 1:
            # if there is only one replicate, we can remove the condition
            logging.warning(f"Condition {condition} has only one replicate. Check for Typos!")

    # check if replicates set is empty or only includes "0_0_0_0"
    if len(replicates) == 0 or (len(replicates) == 1 and "0_0_0_0" in replicates):
        logging.info("All replicates accounted for in the layout data.")
    else:
        logging.warning(
            f"There may be an error with layout data: {replicates}. Please check the layout data."
        )

    # save the experiment info to a json file in the experiment directory
    info_path = Path(experiment_name) / "experiment_info.json"
    info_path.parent.mkdir(parents=True, exist_ok=True)
    # put a .gitignore file in the experiment directory to ignore all files
    with open(info_path.parent / ".gitignore", "w") as f:
        f.write("*\n")
    # save the experiment info to a json file
    with open(info_path, "w") as f:
        # exp_dict = {k: v.model_dump() for k, v in experiment_info.items()}
        json.dump({k: v.model_dump() for k, v in experiment_info.items()}, f, indent=4)
    logging.info(f"Experiment info saved to {info_path}")
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


def first_step(
    raw_data_path: FilePath,
    layout_data_path: FilePath,
    experiment_name: str = "experiment_1",
) -> None:
    """
    The first step of the data processing pipeline.
    It reads the raw data and layout data, gets the unique conditions,
    and organizes the raw data based on the layout data.
    """
    # ensure that the input files are valid paths

    # Read the initial raw data
    try:
        initial_raw_data = pd.read_csv(raw_data_path)
        layout_data = pd.read_csv(layout_data_path)
    except FileNotFoundError as e:
        raise FileNotFoundError(f"File not found: {e.filename}. Please check the file path.")

    # create the experiment directory
    experiment_dir = Path(experiment_name)
    experiment_dir.mkdir(parents=True, exist_ok=True)
    with open(experiment_dir / ".gitignore", "w") as f:
        f.write("*\n")

    # Get unique conditions from the layout data
    experiment_info = get_unique_conditions(layout_data, experiment_name)

    # Organize the raw data based on the layout data
    raw_organized_data = initial_raw_data_organize(initial_raw_data, experiment_info)

    # write the organized data to a csv file in the experiment directory
    organized_data_path = experiment_dir / "raw_organized_data.csv"
    raw_organized_data.to_csv(organized_data_path, index=False)
    logging.info(f"Organized data saved to {organized_data_path}")


def create_figures_generator(experiment_name: str):
    """
    Generates Plotly figures from grouped data.

    This function groups the input DataFrame by 'ligand', 'protein', and
    'buffer', then yields a line plot figure for each group.

    Args:
        data_df: A pandas DataFrame containing the data to plot.
                 It must include 'ligand', 'protein', 'buffer',
                 'Temperature', 'value', and 'well_unqcond' columns.

    Yields:
        A Plotly figure object for each group.
    """
    # Load the organized data
    organized_data_path = Path(experiment_name) / "raw_organized_data.csv"
    try:
        data_df = pd.read_csv(organized_data_path)
    except FileNotFoundError:
        raise FileNotFoundError(f"Organized data file not found: {organized_data_path}")

    # ensure the necessary columns are present
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
        if col not in data_df.columns:
            raise ValueError(f"Missing required column: {col} in the data.")
    grouped_data = data_df.groupby(["ligand", "protein", "buffer"])

    for (ligand, protein, buffer), group in grouped_data:
        fig = px.line(
            group,
            x="Temperature",
            y="value",
            color="well_unqcond",
            title=f"Raw Data for {ligand} and {protein} in {buffer} Buffer",
        )
        yield fig


def filter_organized_data(
    experiment_name: str,
    wells_to_filter: list[str],
) -> None:
    """
    Filters the organized data based on the provided parameters.
    """
    organized_data_path = Path(experiment_name) / "raw_organized_data.csv"
    try:
        organized_data = pd.read_csv(organized_data_path)
    except FileNotFoundError:
        raise FileNotFoundError(f"Organized data file not found: {organized_data_path}")
    filtered_data_path = Path(experiment_name) / "filtered_organized_data.csv"
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
    if len(wells_to_filter) == 0:
        logging.info("No wells to filter. Returning the original data.")
        # save the organized data to a csv file in the experiment directory
        organized_data.to_csv(filtered_data_path, index=False)
        logging.info(f"Filtered data saved to {filtered_data_path}")
        # save a .txt file with the filtered wells
        with open(Path(experiment_name) / "filtered_wells.txt", "w") as f:
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
        logging.info(f"Filtered out well: {well}")

    # save the filtered data to a csv file in the experiment directory
    organized_data.to_csv(filtered_data_path, index=False)
    logging.info(f"Filtered data saved to {filtered_data_path}")

    # save a .txt file with the filtered wells
    with open(Path(experiment_name) / "filtered_wells.txt", "w") as f:
        f.write("\n".join(wells_to_filter))


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


def convert_concentration_to_float(concentration: str) -> float:
    if "uM" in concentration:
        return float(concentration.replace("uM", "").strip())
    elif "mM" in concentration:
        return float(concentration.replace("mM", "").strip()) * 1000  # Convert mM to uM
    elif "nM" in concentration:
        # check if it is zero
        c = concentration.replace("nM", "").strip()
        if c == "0":
            return float(c)
        return float(c) / 1000
    else:
        return float(concentration.strip())


def average_accross_replicates(experiment_name: str) -> None:
    """
    The second step of the data processing pipeline.
    It filters the organized data based on the provided parameters.
    """
    filtered_data_path = Path(experiment_name) / "filtered_organized_data.csv"
    if not filtered_data_path.exists():
        raise FileNotFoundError(f"Filtered data file not found: {filtered_data_path}")
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

    averaged_data = avg_across_replicates(organized_data=filtered_data)

    # in the averaged across replicates data, we need to sort the columns (except for Temperature) by matching ligand, protein, and buffer
    # Sort the columns based on ligand, protein, and buffer. then within each group, sort by increasing concentration
    # get the columns except for Temperature
    columns_to_sort = averaged_data.columns[1:]  # Exclude 'Temperature'
    sorted_columns = sorted(
        columns_to_sort,
        key=lambda x: (
            x.split("_")[1],  # ligand
            x.split("_")[2],  # protein
            x.split("_")[3],  # buffer
            convert_concentration_to_float(
                x.split("_")[0]
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
    averaged_data_path = Path(experiment_name) / "averaged_data.csv"
    averaged_data_sorted.to_csv(averaged_data_path, index=False)
    logging.info(f"Averaged data saved to {averaged_data_path}")


def create_averaged_figures_generator(experiment_name: str):
    """
    Generates Plotly figures from grouped data.

    This function groups the input DataFrame by 'ligand', 'protein', and
    'buffer', then yields a line plot figure for each group.

    Args:
        data_df: A pandas DataFrame containing the data to plot.
                 It must include 'ligand', 'protein', 'buffer',
                 'Temperature', 'value', and 'well_unqcond' columns.

    Yields:
        A Plotly figure object for each group.
    """
    # Load the organized data
    averaged_data_path = Path(experiment_name) / "averaged_data.csv"
    try:
        data_df = pd.read_csv(averaged_data_path)
    except FileNotFoundError:
        raise FileNotFoundError(f"Averaged data file not found: {averaged_data_path}")

    # ensire the first column is 'Temperature'
    if data_df.columns[0] != "Temperature":
        raise ValueError("The first column must be 'Temperature'.")

    plotting_df = data_df.melt(id_vars=["Temperature"], var_name="unqcond", value_name="value")
    # ensure the necessary columns are present
    plotting_df = split_unqcon_column(plotting_df)
    required_columns = [
        "Temperature",
        "unqcond",
        "value",
        "concentration",
        "ligand",
        "protein",
        "buffer",
    ]

    for col in required_columns:
        if col not in plotting_df.columns:
            raise ValueError(f"Missing required column: {col} in the data.")
    grouped_data = plotting_df.groupby(["ligand", "protein", "buffer"])

    for (ligand, protein, buffer), group in grouped_data:
        fig = px.line(
            group,
            x="Temperature",
            y="value",
            color="unqcond",
            title=f"Avg Raw Data for {ligand} and {protein} in {buffer} Buffer",
        )
        yield fig


def find_background_column(
    data: pd.DataFrame, concentration: str, ligand: str, protein: str, buffer: str
) -> Optional[str]:
    """Helper function to find the background column in the data."""
    if protein == "NPC":
        return None  # Dont remove background for NPC
    for col in data.columns:
        if f"{concentration}_{ligand}_NPC_{buffer}" in col:
            return col
    return None


def subtract_background(experiment_name: str) -> None:
    """Finds the background column for each unique condition and subtracts it from the data. The BG col should be in the format 'concentration_ligand_NPC_buffer'."""
    # Build the path to the averaged data
    averaged_data_path = Path(experiment_name) / "averaged_data.csv"
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

    for col in data.columns:
        parts = col.split("_")
        if len(parts) < 4:
            continue
        concentration = parts[0]
        ligand = parts[1]
        protein = parts[2]
        buffer = parts[3]

        background_col = find_background_column(data, concentration, ligand, protein, buffer)

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
    data = data.loc[:, ~data.columns.str.contains("NPC")]

    # Save the data with background subtracted
    background_subtracted_path = Path(experiment_name) / "background_subtracted_data.csv"
    data.to_csv(background_subtracted_path, index=False)
    logging.info(f"Background subtracted data saved to {background_subtracted_path}")


def create_bgsubtracted_figures_generator(experiment_name: str):
    """
    Generates Plotly figures from grouped data.

    This function groups the input DataFrame by 'ligand', 'protein', and
    'buffer', then yields a line plot figure for each group.

    Args:
        data_df: A pandas DataFrame containing the data to plot.
                 It must include 'ligand', 'protein', 'buffer',
                 'Temperature', 'value', and 'well_unqcond' columns.

    Yields:
        A Plotly figure object for each group.
    """
    # Load the organized data
    bg_data_path = Path(experiment_name) / "background_subtracted_data.csv"
    try:
        data_df = pd.read_csv(bg_data_path)
    except FileNotFoundError:
        raise FileNotFoundError(f"BG subtracted data file not found: {bg_data_path}")

    # ensire the first column is 'Temperature'
    if data_df.columns[0] != "Temperature":
        raise ValueError("The first column must be 'Temperature'.")

    plotting_df = data_df.melt(id_vars=["Temperature"], var_name="unqcond", value_name="value")
    # ensure the necessary columns are present
    plotting_df = split_unqcon_column(plotting_df)
    required_columns = [
        "Temperature",
        "unqcond",
        "value",
        "concentration",
        "ligand",
        "protein",
        "buffer",
    ]

    for col in required_columns:
        if col not in plotting_df.columns:
            raise ValueError(f"Missing required column: {col} in the data.")
    grouped_data = plotting_df.groupby(["ligand", "protein", "buffer"])

    for (ligand, protein, buffer), group in grouped_data:
        fig = px.line(
            group,
            x="Temperature",
            y="value",
            color="unqcond",
            title=f"BG subtracted Data for {ligand} and {protein} in {buffer} Buffer",
        )
        yield fig


def min_max_scale(experiment_name: str) -> None:
    """Min-max scales the background subtracted data."""
    # Build the path to the background subtracted data
    bg_data_path = Path(experiment_name) / "background_subtracted_data.csv"
    if not bg_data_path.exists():
        raise FileNotFoundError(f"BG subtracted data file not found: {bg_data_path}")
    # Load the background subtracted data
    data = pd.read_csv(bg_data_path)
    # ensure the first column is 'Temperature'
    if data.columns[0] != "Temperature":
        raise ValueError("The first column must be 'Temperature'.")
    for col in data.columns:
        if col.startswith("Temperature"):
            continue
        if data[col].max() - data[col].min() == 0:
            continue  # Avoid division by zero
        data[col] = (data[col] - data[col].min()) / (data[col].max() - data[col].min())
    # Save the min-max scaled data
    scaled_data_path = Path(experiment_name) / "min_max_scaled_data.csv"
    data.to_csv(scaled_data_path, index=False)
    logging.info(f"Min-max scaled data saved to {scaled_data_path}")


def create_bgsub_minmax_figures_generator(experiment_name: str):
    """
    Generates Plotly figures from grouped data.

    This function groups the input DataFrame by 'ligand', 'protein', and
    'buffer', then yields a line plot figure for each group.

    Args:
        data_df: A pandas DataFrame containing the data to plot.
                 It must include 'ligand', 'protein', 'buffer',
                 'Temperature', 'value', and 'well_unqcond' columns.

    Yields:
        A Plotly figure object for each group.
    """
    # Load the organized data
    bg_min_max_data_path = Path(experiment_name) / "min_max_scaled_data.csv"
    try:
        data_df = pd.read_csv(bg_min_max_data_path)
    except FileNotFoundError:
        raise FileNotFoundError(f"BG subtracted data file not found: {bg_min_max_data_path}")

    # ensire the first column is 'Temperature'
    if data_df.columns[0] != "Temperature":
        raise ValueError("The first column must be 'Temperature'.")

    plotting_df = data_df.melt(id_vars=["Temperature"], var_name="unqcond", value_name="value")
    # ensure the necessary columns are present
    plotting_df = split_unqcon_column(plotting_df)
    required_columns = [
        "Temperature",
        "unqcond",
        "value",
        "concentration",
        "ligand",
        "protein",
        "buffer",
    ]

    for col in required_columns:
        if col not in plotting_df.columns:
            raise ValueError(f"Missing required column: {col} in the data.")
    grouped_data = plotting_df.groupby(["ligand", "protein", "buffer"])

    for (ligand, protein, buffer), group in grouped_data:
        fig = px.line(
            group,
            x="Temperature",
            y="value",
            color="unqcond",
            title=f"BG subtracted min-max Data for {ligand} and {protein} in {buffer} Buffer",
        )
        yield fig


def calculate_derivative(experiment_name: str) -> None:
    """Calclulates the derivative of the background subtracted data with respect to Temperature. And Min-Max scales the data afterwards."""
    # build a path the the bg subtracted data
    bg_data_path = Path(experiment_name) / "background_subtracted_data.csv"
    if not bg_data_path.exists():
        raise FileNotFoundError(f"BG subtracted data file not found: {bg_data_path}")
    # Load the background subtracted data
    data = pd.read_csv(bg_data_path)
    # ensure the first column is 'Temperature'
    if data.columns[0] != "Temperature":
        raise ValueError("The first column must be 'Temperature'.")

    # Calculate the derivative with respect to Temperature
    data_derivative = data.copy()
    for col in data.columns[1:]:  # Skip the first column (Temperature)
        data_derivative[col] = np.gradient(data[col], data["Temperature"])
        # multiply by -1 to flip the sign
        data_derivative[col] *= -1

    for col in data_derivative.columns:
        if col.startswith("Temperature"):
            continue
        if data_derivative[col].max() - data_derivative[col].min() == 0:
            continue  # Avoid division by zero
        data_derivative[col] = (data_derivative[col] - data_derivative[col].min()) / (
            data_derivative[col].max() - data_derivative[col].min()
        )

    # Save the derivative data
    derivative_data_path = Path(experiment_name) / "derivative_data.csv"
    data_derivative.to_csv(derivative_data_path, index=False)
    logging.info(f"Derivative data saved to {derivative_data_path}")


def create_derivative_figures_generator(experiment_name: str):
    """
    Generates Plotly figures from grouped data.

    This function groups the input DataFrame by 'ligand', 'protein', and
    'buffer', then yields a line plot figure for each group.

    Args:
        data_df: A pandas DataFrame containing the data to plot.
                 It must include 'ligand', 'protein', 'buffer',
                 'Temperature', 'value', and 'well_unqcond' columns.

    Yields:
        A Plotly figure object for each group.
    """
    # Load the organized data
    derivative_data_path = Path(experiment_name) / "derivative_data.csv"
    try:
        data_df = pd.read_csv(derivative_data_path)
    except FileNotFoundError:
        raise FileNotFoundError(f"BG subtracted data file not found: {derivative_data_path}")

    # ensire the first column is 'Temperature'
    if data_df.columns[0] != "Temperature":
        raise ValueError("The first column must be 'Temperature'.")

    plotting_df = data_df.melt(id_vars=["Temperature"], var_name="unqcond", value_name="value")
    # ensure the necessary columns are present
    plotting_df = split_unqcon_column(plotting_df)
    required_columns = [
        "Temperature",
        "unqcond",
        "value",
        "concentration",
        "ligand",
        "protein",
        "buffer",
    ]

    for col in required_columns:
        if col not in plotting_df.columns:
            raise ValueError(f"Missing required column: {col} in the data.")
    grouped_data = plotting_df.groupby(["ligand", "protein", "buffer"])

    for (ligand, protein, buffer), group in grouped_data:
        fig = px.line(
            group,
            x="Temperature",
            y="value",
            color="unqcond",
            title=f"Derivative Data for {ligand} and {protein} in {buffer} Buffer",
        )
        yield fig


def find_min_temperature(experiment_name: str) -> None:
    """Finds the minimum temperature for each unique condition in the derivative data."""
    # Build the path to the derivative data
    derivative_data_path = Path(experiment_name) / "derivative_data.csv"
    if not derivative_data_path.exists():
        raise FileNotFoundError(f"Derivative data file not found: {derivative_data_path}")
    # Load the derivative data
    data = pd.read_csv(derivative_data_path)
    # ensure the first column is 'Temperature'
    if data.columns[0] != "Temperature":
        raise ValueError("The first column must be 'Temperature'.")
    min_temps = {}
    for col in data.columns:  # Skip the first column (Temperature)
        if col == "Temperature" or col == "index":
            continue
        min_index = data[col].idxmin()
        min_temp = data["Temperature"].iloc[min_index]
        min_temps[col] = min_temp
    # need to convert the min_temps dictionary to a DataFrame
    min_temps_df = pd.DataFrame(list(min_temps.items()), columns=["unqcond", "min_temperature"])
    # Save the min temperatures to a CSV file
    min_temps_df = split_unqcon_column(min_temps_df)
    min_temps_path = Path(experiment_name) / "min_temperatures.csv"
    min_temps_df.to_csv(min_temps_path, index=False)
    logging.info(f"Min temperatures saved to {min_temps_path}")


def create_mintemp_figures_generator(experiment_name: str):
    """
    Generates Plotly figures from grouped data.

    This function groups the input DataFrame by 'ligand', 'protein', and
    'buffer', then yields a line plot figure for each group.

    Args:
        data_df: A pandas DataFrame containing the data to plot.
                 It must include 'ligand', 'protein', 'buffer',
                 'Temperature', 'value', and 'well_unqcond' columns.

    Yields:
        A Plotly figure object for each group.
    """
    # Load the organized data
    min_temperatures_data_path = Path(experiment_name) / "min_temperatures.csv"
    try:
        data_df = pd.read_csv(min_temperatures_data_path)
    except FileNotFoundError:
        raise FileNotFoundError(f"BG subtracted data file not found: {min_temperatures_data_path}")

    # ensure the necessary columns are present
    required_columns = [
        "unqcond",
        "min_temperature",
        "concentration",
        "ligand",
        "protein",
        "buffer",
    ]

    for col in required_columns:
        if col not in data_df.columns:
            raise ValueError(f"Missing required column: {col} in the data.")

    data_df["concentration2"] = data_df["concentration"].apply(convert_concentration_to_float)
    grouped_data = data_df.groupby(["ligand", "protein", "buffer"])

    for (ligand, protein, buffer), group in grouped_data:
        fig = px.scatter(
            group,
            x="concentration2",
            y="min_temperature",
            color="ligand",
            title=f"Min Temperature for {ligand} and {protein} in {buffer} Buffer",
        )
        yield fig
