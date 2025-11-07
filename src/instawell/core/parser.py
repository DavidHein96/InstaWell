"""
Robust parsing utilities for experimental condition strings.

This module provides functions to parse condition strings like:
    '500uM_Geranyl-Monophosphate_d104hFic-H363A_1mM-ATP-5mM-MgCl2'

Into structured components (concentration, ligand, protein, buffer).
"""

import re
from typing import Dict, Optional, Tuple

from .data_models import UniqueCondition

# Configuration for parsing
# CONDITION_DELIMITER = "_"
# DEFAULT_FIELDS = ("concentration", "ligand", "protein", "buffer")


def parse_condition_string(
    condition_str: str,
    delimiter: str = "_",
    fields: Tuple[str, ...] = ("concentration", "ligand", "protein", "buffer"),
) -> Dict[str, str]:
    """
    Parse a condition string into component fields.

    This function handles condition strings where individual components
    (like ligand or protein names) may contain the delimiter character.
    It parses from the end of the string, taking the last N components
    where N is the number of fields specified.

    Args:
        condition_str: The full condition string to parse
        delimiter: Character used to separate fields (default: '_')
        fields: Ordered tuple of field names to parse (default: ('concentration', 'ligand', 'protein', 'buffer'))
                The last len(fields) components will be extracted in this order.

    Returns:
        Dictionary mapping field names to their values

    Raises:
        ValueError: If the condition string doesn't have enough components

    Examples:
        >>> # Default: parse concentration, ligand, protein, buffer from end
        >>> parse_condition_string("500uM_ATP_Protein1_Buffer1")
        {'concentration': '500uM', 'ligand': 'ATP', 'protein': 'Protein1', 'buffer': 'Buffer1'}

        >>> # Handles underscores in component names (takes last 4 components)
        >>> parse_condition_string("500uM_Geranyl-Monophosphate_d104hFic-H363A_1mM-ATP-5mM-MgCl2")
        {'concentration': '500uM', 'ligand': 'Geranyl-Monophosphate', 'protein': 'd104hFic-H363A', 'buffer': '1mM-ATP-5mM-MgCl2'}

        >>> # Custom field order
        >>> parse_condition_string("ATP_Protein1_500uM_Buffer1", fields=("ligand", "protein", "concentration", "buffer"))
        {'ligand': 'ATP', 'protein': 'Protein1', 'concentration': '500uM', 'buffer': 'Buffer1'}

        >>> # Parse fewer fields (last 2 components only)
        >>> parse_condition_string("500uM_ATP_Protein1_Buffer1", fields=("protein", "buffer"))
        {'protein': 'Protein1', 'buffer': 'Buffer1'}
    """
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

    # Take last N components where N = len(fields)
    # This handles underscores in earlier components
    field_values = parts[-num_fields:]

    # Create dictionary mapping field names to values
    return dict(zip(fields, field_values))


def condition_from_string(
    condition_str: str,
    delimiter: str = "_",
    fields: Tuple[str, ...] = ("concentration", "ligand", "protein", "buffer"),
    include_replicates: bool = False,
) -> UniqueCondition:
    """
    Parse a condition string and return a UniqueCondition object.

    Args:
        condition_str: The full condition string to parse
        delimiter: Character used to separate fields (default: '_')
        fields: Ordered tuple of field names to parse (default: ('concentration', 'ligand', 'protein', 'buffer'))
        include_replicates: Whether to include an empty replicates list (default: False)

    Returns:
        UniqueCondition object with parsed fields

    Raises:
        ValueError: If the condition string is invalid or required fields are missing

    Examples:
        >>> condition = condition_from_string("500uM_ATP_Protein1_Buffer1")
        >>> condition.concentration
        '500uM'
        >>> condition.ligand_name
        'ATP'

        >>> # Custom field order
        >>> condition = condition_from_string("ATP_Protein1_500uM_Buffer1",
        ...                                    fields=("ligand", "protein", "concentration", "buffer"))
        >>> condition.ligand_name
        'ATP'
    """
    parsed = parse_condition_string(condition_str, delimiter, fields)

    # Ensure all required fields for UniqueCondition are present
    required = {"concentration", "ligand", "protein", "buffer"}
    missing = required - set(parsed.keys())
    if missing:
        raise ValueError(
            f"Cannot create UniqueCondition: missing required fields {missing}. "
            f"Parsed fields: {list(parsed.keys())}"
        )

    return UniqueCondition(
        full_name=condition_str,
        concentration=parsed["concentration"],
        ligand_name=parsed["ligand"],
        protein_name=parsed["protein"],
        buffer_condition=parsed["buffer"],
        replicates=[] if include_replicates else [],
    )


def condition_to_string(condition: UniqueCondition, delimiter: str = "_") -> str:
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
