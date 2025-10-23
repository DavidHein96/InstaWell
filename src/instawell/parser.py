"""
Robust parsing utilities for experimental condition strings.

This module provides functions to parse condition strings like:
    '500uM_Geranyl-Monophosphate_d104hFic-H363A_1mM-ATP-5mM-MgCl2'

Into structured components (concentration, ligand, protein, buffer).
"""

import re
from typing import Dict, Optional
from .data_models import UniqueCondition


# Configuration for parsing
CONDITION_DELIMITER = "_"
NUM_REQUIRED_FIELDS = 4
PARSING_STRATEGY = "from_end"  # or "from_start"


def parse_condition_string(
    condition_str: str,
    delimiter: str = CONDITION_DELIMITER,
    num_fields: int = NUM_REQUIRED_FIELDS,
    strategy: str = PARSING_STRATEGY,
) -> Dict[str, str]:
    """
    Parse a condition string into component fields.

    This function handles condition strings where individual components
    (like ligand or protein names) may contain the delimiter character.
    By default, it takes the last N fields to handle this robustly.

    Args:
        condition_str: The full condition string to parse
        delimiter: Character used to separate fields (default: '_')
        num_fields: Number of fields expected (default: 4)
        strategy: Parsing strategy - 'from_end' (default) or 'from_start'

    Returns:
        Dictionary with keys: concentration, ligand, protein, buffer

    Raises:
        ValueError: If the condition string doesn't have enough fields

    Examples:
        >>> parse_condition_string("500uM_ATP_Protein1_Buffer1")
        {'concentration': '500uM', 'ligand': 'ATP', 'protein': 'Protein1', 'buffer': 'Buffer1'}

        >>> # Handles underscores in component names
        >>> parse_condition_string("500uM_Geranyl-Monophosphate_d104hFic-H363A_1mM-ATP-5mM-MgCl2")
        {'concentration': '500uM', 'ligand': 'Geranyl-Monophosphate', ...}
    """
    if not condition_str or condition_str.strip() == "":
        raise ValueError("Condition string cannot be empty")

    parts = condition_str.split(delimiter)

    if len(parts) < num_fields:
        raise ValueError(
            f"Condition '{condition_str}' must have at least {num_fields} "
            f"'{delimiter}'-separated fields, but only found {len(parts)} fields: {parts}"
        )

    # Extract the required fields based on strategy
    if strategy == "from_end":
        # Take last N fields (handles underscores in early components)
        field_values = parts[-num_fields:]
    elif strategy == "from_start":
        # Take first N fields
        field_values = parts[:num_fields]
    else:
        raise ValueError(f"Unknown parsing strategy: {strategy}")

    concentration, ligand, protein, buffer = field_values

    return {
        "concentration": concentration,
        "ligand": ligand,
        "protein": protein,
        "buffer": buffer,
    }


def condition_from_string(
    condition_str: str,
    delimiter: str = CONDITION_DELIMITER,
    num_fields: int = NUM_REQUIRED_FIELDS,
    strategy: str = PARSING_STRATEGY,
) -> UniqueCondition:
    """
    Parse a condition string and return a UniqueCondition object.

    Args:
        condition_str: The full condition string to parse
        delimiter: Character used to separate fields (default: '_')
        num_fields: Number of fields expected (default: 4)
        strategy: Parsing strategy - 'from_end' (default) or 'from_start'

    Returns:
        UniqueCondition object with parsed fields

    Raises:
        ValueError: If the condition string is invalid

    Examples:
        >>> condition = condition_from_string("500uM_ATP_Protein1_Buffer1")
        >>> condition.concentration
        '500uM'
        >>> condition.ligand_name
        'ATP'
    """
    parsed = parse_condition_string(condition_str, delimiter, num_fields, strategy)

    return UniqueCondition(
        full_name=condition_str,
        concentration=parsed["concentration"],
        ligand_name=parsed["ligand"],
        protein_name=parsed["protein"],
        buffer_condition=parsed["buffer"],
    )


def condition_to_string(condition: UniqueCondition, delimiter: str = CONDITION_DELIMITER) -> str:
    """
    Reconstruct a condition string from a UniqueCondition object.

    Args:
        condition: UniqueCondition object to serialize
        delimiter: Character to use for separating fields (default: '_')

    Returns:
        Reconstructed condition string

    Examples:
        >>> condition = UniqueCondition(
        ...     concentration="500uM",
        ...     ligand_name="ATP",
        ...     protein_name="Protein1",
        ...     buffer_condition="Buffer1"
        ... )
        >>> condition_to_string(condition)
        '500uM_ATP_Protein1_Buffer1'
    """
    parts = [
        condition.concentration,
        condition.ligand_name,
        condition.protein_name,
        condition.buffer_condition,
    ]

    # Validate that no component is empty
    if any(not part for part in parts):
        raise ValueError(
            f"Cannot convert condition to string - missing required fields: {condition}"
        )

    return delimiter.join(parts)


def validate_condition_string(condition_str: str) -> bool:
    """
    Check if a condition string is valid without raising exceptions.

    Args:
        condition_str: The condition string to validate

    Returns:
        True if valid, False otherwise

    Examples:
        >>> validate_condition_string("500uM_ATP_Protein1_Buffer1")
        True
        >>> validate_condition_string("invalid")
        False
        >>> validate_condition_string("0_0_0_0")
        True  # Valid format, even if semantically empty
    """
    try:
        parse_condition_string(condition_str)
        return True
    except (ValueError, IndexError):
        return False


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
