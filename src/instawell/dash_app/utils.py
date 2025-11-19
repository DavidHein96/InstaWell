"""
Utility functions for the Dash app.
"""

import base64
import io
from pathlib import Path
from typing import Dict, List

import pandas as pd

from instawell import StepFiles


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

    # Decode base64
    content_type, content_string = contents.split(",", 1)
    decoded = base64.b64decode(content_string)

    # Parse CSV
    df = pd.read_csv(io.BytesIO(decoded))
    return df


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

    # Check which pipeline steps are completed (using .value to get actual filenames)
    if (exp_dir / StepFiles.INGESTED_DATA.value).exists():
        status["completed_steps"].append("ingest")

    if (exp_dir / StepFiles.FILTERED_DATA.value).exists():
        status["completed_steps"].append("filter")

    if (exp_dir / StepFiles.AVERAGED_DATA.value).exists():
        status["completed_steps"].append("average")

    if (exp_dir / StepFiles.MIN_TEMPERATURES_DATA.value).exists():
        status["completed_steps"].append("complete")

    # Get number of unique conditions from experiment_info.json
    info_file = exp_dir / "experiment_info.json"
    if info_file.exists():
        import json

        with open(info_file) as f:
            info = json.load(f)
            status["total_conditions"] = len(info)

    return status
