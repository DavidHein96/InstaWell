"""
Utility functions for the Dash app.
"""

import base64
import io
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

from instawell import StepFiles

logger = logging.getLogger("instawell.dash_app.utils")

WELL_PATTERN = re.compile(r"^\s*([A-Za-z]+)\s*0*([0-9]+)\s*$")


def normalize_well(well_str: str) -> str:
    """Normalize well name like 'A01' -> 'A1'."""
    match = WELL_PATTERN.match(str(well_str))
    if not match:
        return str(well_str).strip()
    return f"{match.group(1).upper()}{int(match.group(2))}"


def parse_well_name(well_name: str) -> Tuple[str | None, int | None]:
    """Parse well name like 'A1' into (row_letter, column_number)."""
    match = re.match(r"([A-Z]+)(\d+)", well_name.strip())
    if match:
        return match.group(1), int(match.group(2))
    return None, None


def get_well_grid_dimensions(well_names: List[str]) -> Tuple[List[str], List[int]]:
    """Determine grid dimensions from well names."""
    rows = set()
    cols = set()

    for well in well_names:
        row, col = parse_well_name(well)
        if row and col:
            rows.add(row)
            cols.add(col)

    if not rows or not cols:
        return [], []

    return sorted(rows), sorted(cols)


def validate_separator_placeholder(separator: str, placeholder: str) -> Tuple[str, str]:
    """Validate and normalize separator and placeholder characters.

    Returns:
        (separator, placeholder) tuple

    Raises:
        ValueError: If inputs are invalid
    """
    if not separator or len(separator) != 1:
        raise ValueError("Condition separator must be exactly one character.")
    if not placeholder or len(placeholder) != 1:
        raise ValueError(
            "Missing condition placeholder must be exactly one character."
        )
    if separator == placeholder:
        raise ValueError("Separator and placeholder must be different characters.")
    return separator, placeholder


def parse_upload(contents: str, filename: str) -> pd.DataFrame:
    """
    Parse uploaded CSV file from Dash upload component.

    Args:
        contents: Base64 encoded file contents from dcc.Upload
        filename: Original filename

    Returns:
        Parsed DataFrame

    Raises:
        ValueError: If file format is not supported
    """
    if not filename.endswith(".csv"):
        raise ValueError("Only CSV files are supported")

    _content_type, content_string = contents.split(",", 1)
    decoded = base64.b64decode(content_string)

    return pd.read_csv(io.BytesIO(decoded))


def get_experiment_list(experiments_root: Path) -> List[str]:
    """
    Get list of existing experiments.

    Args:
        experiments_root: Root directory containing experiments

    Returns:
        Sorted list of experiment names
    """
    if not experiments_root.exists():
        return []

    experiments = []
    for item in experiments_root.iterdir():
        if item.is_dir() and (item / "experiment.json").exists():
            experiments.append(item.name)

    return sorted(experiments)


def get_experiment_status(exp_dir: Path) -> Dict:
    """
    Get status information about an experiment.

    Args:
        exp_dir: Experiment directory path

    Returns:
        Dictionary with status information:
        - completed_steps: List of completed pipeline steps
        - total_conditions: Number of unique conditions
    """
    status = {"completed_steps": [], "total_conditions": 0}

    if (exp_dir / StepFiles.INGESTED_DATA.value).exists():
        status["completed_steps"].append("ingest")

    if (exp_dir / StepFiles.FILTERED_DATA.value).exists():
        status["completed_steps"].append("filter")

    if (exp_dir / StepFiles.AVERAGED_DATA.value).exists():
        status["completed_steps"].append("average")

    if (exp_dir / StepFiles.MIN_TEMPERATURES_DATA.value).exists():
        status["completed_steps"].append("complete")

    info_file = exp_dir / "experiment_info.json"
    if info_file.exists():
        with open(info_file) as f:
            info = json.load(f)
            status["total_conditions"] = len(info)

    return status
