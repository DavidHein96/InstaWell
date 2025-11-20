import logging

import numpy as np
import pandas as pd

from instawell.core.parser import parse_condition_string

# set logging level to INFO
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


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


def convert_concentration_to_float_log(concentration: str) -> float:
    if "uM" in concentration:
        return np.log1p(float(concentration.replace("uM", "").strip()))
    elif "mM" in concentration:
        return np.log1p(float(concentration.replace("mM", "").strip()) * 1000)  # Convert mM to uM
    elif "nM" in concentration:
        # check if it is zero
        c = concentration.replace("nM", "").strip()
        if c == "0":
            return np.log1p(float(c))
        return np.log1p(float(c) / 1000)
    else:
        return np.log1p(float(concentration.strip()))


def split_unqcon_column(
    data: pd.DataFrame,
    fields: tuple[str, ...],
    delimiter: str,
) -> pd.DataFrame:
    """
    Splits the 'unqcond' column into its component parts based on the provided fields.

    Args:
        data: DataFrame with an 'unqcond' column.
        fields: Ordered tuple of field names to parse from the 'unqcond' strings.
        delimiter: Character used to separate fields in the 'unqcond' string.

    Returns:
        DataFrame with new columns corresponding to the specified fields.
    """
    if "unqcond" not in data.columns:
        raise ValueError("Input DataFrame must have a 'unqcond' column.")

    parsed_rows = []
    for condition_str in data["unqcond"]:
        try:
            condition_obj = parse_condition_string(
                condition_str, delimiter=delimiter, fields=fields
            )
            parsed_rows.append(condition_obj.dimensions)
        except ValueError as e:
            logging.warning(f"Failed to parse condition '{condition_str}': {e}")
            # Append a dictionary with null values for all fields
            parsed_rows.append({field: None for field in fields})

    # Create a new DataFrame from the parsed data
    parsed_df = pd.DataFrame(parsed_rows, index=data.index)

    # Assign the new columns to the original DataFrame
    data[list(fields)] = parsed_df[list(fields)]

    return data


def slugify(s: str) -> str:
    """
    Very small, local slugify to keep filenames safe.

    Replaces problematic characters with '_' and strips whitespace.
    """
    keep = []
    for ch in s.strip():
        if ch.isalnum() or ch in ("-", "_"):
            keep.append(ch)
        else:
            keep.append("_")
    return "".join(keep).strip("_")
