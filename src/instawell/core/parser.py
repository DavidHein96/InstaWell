"""
Robust parsing utilities for experimental condition strings.

This module provides functions to parse condition strings like:
    '500uM_Geranyl-Monophosphate_d104hFic-H363A_1mM-ATP-5mM-MgCl2'

Into structured components (concentration, ligand, protein, buffer).
"""

import re
from typing import Optional, Tuple

from instawell.core.data_models import Condition


def parse_condition_string(
    condition_str: str,
    delimiter: str = "_",
    fields: Tuple[str, ...] = ("concentration", "ligand", "protein", "buffer"),
) -> Condition:
    if not condition_str or condition_str.strip() == "":
        raise ValueError("Condition string cannot be empty")

    parts = condition_str.split(delimiter)
    num_fields = len(fields)

    if len(parts) < num_fields:
        raise ValueError(
            f"Condition '{condition_str}' must have at least {num_fields} "
            f"'{delimiter}'-separated components for fields {fields}, "
            f"but only found {len(parts)} components: {parts}"
        )
    if len(parts) > num_fields:
        raise ValueError(
            f"Condition '{condition_str}' has more components ({len(parts)}) "
            f"than expected for fields {fields} ({num_fields}). "
            f"Please ensure that component names do not contain the delimiter '{delimiter}'. "
            f"You may need to switch to a different delimiter or adjust the condition strings accordingly."
        )

    # Create dictionary mapping field names to values
    dimensions = {field: part for field, part in zip(fields, parts, strict=True)}
    return Condition(dimensions=dimensions, full_name=condition_str)


def parse_concentration_to_float(concentration: str) -> Optional[float]:
    """
    Convert a concentration string to a float value.

    Handles common concentration formats like:
        - '500uM' -> 500.0
        - '1mM' -> 1.0
        - '0.5nM' -> 0.5
        - 'apo' -> 0.0
        - 'DMSO' -> 0.0

    Args:
        concentration: Concentration string to parse

    Returns:
        Float value, or None if parsing fails

    Examples:
        >>> parse_concentration_to_float("500uM")
        500.0
        >>> parse_concentration_to_float("apo")
        0.0
        >>> parse_concentration_to_float("DMSO")
        0.0
    """
    # Handle special cases
    if concentration.lower() in ["apo", "dmso", "control", "baseline"]:
        return 0.0

    # Try to extract numeric value using regex
    # Matches patterns like: 500uM, 1.5mM, 0.1nM, etc.
    match = re.match(r"^([\d.]+)", concentration)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None

    return None
