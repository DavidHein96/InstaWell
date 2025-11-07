import logging

import pandas as pd

from instawell.core.parser import condition_from_string

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


def split_unqcon_column(
    data: pd.DataFrame,
    fields: tuple[str, ...] = ("concentration", "ligand", "protein", "buffer"),
    delimiter: str = "_",
) -> pd.DataFrame:
    """
    Split the 'unqcond' column into its component parts using the robust parser.

    This version handles underscores in component names correctly.

    Args:
        data: DataFrame with an 'unqcond' column containing condition strings
        fields: Ordered tuple of field names to parse from condition strings.
                Default: ("concentration", "ligand", "protein", "buffer")
                The last len(fields) components of each condition string will be parsed in this order.

    Returns:
        DataFrame with added columns corresponding to the field names

    Examples:
        >>> df = pd.DataFrame({"unqcond": ["500uM_ATP_Fic_buffer1"]})
        >>> # Default parsing
        >>> df = split_unqcon_column(df)
        >>> print(df[["concentration", "ligand", "protein", "buffer"]])

        >>> # Custom field order
        >>> df = split_unqcon_column(df, fields=("ligand", "protein", "concentration", "buffer"))
    """
    # Parse each condition string
    parsed_conditions = []
    for condition_str in data["unqcond"]:
        try:
            condition_obj = condition_from_string(
                condition_str, delimiter=delimiter, fields=fields, include_replicates=False
            )
            # Map the parsed fields to their values
            parsed_conditions.append(
                {
                    "concentration": condition_obj.concentration,
                    "ligand": condition_obj.ligand_name,
                    "protein": condition_obj.protein_name,
                    "buffer": condition_obj.buffer_condition,
                }
            )
        except ValueError as e:
            # If parsing fails, use empty strings for all fields
            logging.warning(f"Failed to parse condition '{condition_str}': {e}")
            parsed_conditions.append(
                {
                    "concentration": "",
                    "ligand": "",
                    "protein": "",
                    "buffer": "",
                }
            )

    # Add the parsed columns to the dataframe
    parsed_df = pd.DataFrame(parsed_conditions)
    for field in ["concentration", "ligand", "protein", "buffer"]:
        data[field] = parsed_df[field]

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
