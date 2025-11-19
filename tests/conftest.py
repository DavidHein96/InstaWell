"""
Pytest configuration and shared fixtures for InstaWell tests.

This module provides common fixtures used across multiple test modules,
including sample data structures, mock files, and utility functions.
"""

from pathlib import Path
from typing import Dict

import pandas as pd
import pytest

from instawell.core.data_models import Replicate, UniqueCondition


@pytest.fixture
def simple_condition_string() -> str:
    """Simple condition string with no underscores in components."""
    return "500uM_ATP_Protein1_Buffer1"


@pytest.fixture
def complex_condition_string() -> str:
    """Complex condition string with underscores in component names."""
    return "500uM_Geranyl-Monophosphate_d104hFic-H363A_1mM-ATP-5mM-MgCl2"


@pytest.fixture
def sample_replicate() -> Replicate:
    """Create a sample Replicate object."""
    return Replicate(
        well_row="A",
        well_column="1",
        well_name="A1",
    )


@pytest.fixture
def sample_condition() -> UniqueCondition:
    """Create a sample UniqueCondition object."""
    return UniqueCondition(
        full_name="500uM_ATP_Protein1_Buffer1",
        concentration="500uM",
        ligand_name="ATP",
        protein_name="Protein1",
        buffer_condition="Buffer1",
        replicates=[
            Replicate(well_row="A", well_column="1", well_name="A1"),
            Replicate(well_row="A", well_column="2", well_name="A2"),
        ],
    )


@pytest.fixture
def sample_conditions_dict() -> Dict[str, UniqueCondition]:
    """Create a dictionary of sample conditions."""
    return {
        "500uM_ATP_Protein1_Buffer1": UniqueCondition(
            full_name="500uM_ATP_Protein1_Buffer1",
            concentration="500uM",
            ligand_name="ATP",
            protein_name="Protein1",
            buffer_condition="Buffer1",
            replicates=[
                Replicate(well_row="A", well_column="1", well_name="A1"),
                Replicate(well_row="A", well_column="2", well_name="A2"),
            ],
        ),
        "1mM_GTP_Protein2_Buffer2": UniqueCondition(
            full_name="1mM_GTP_Protein2_Buffer2",
            concentration="1mM",
            ligand_name="GTP",
            protein_name="Protein2",
            buffer_condition="Buffer2",
            replicates=[
                Replicate(well_row="B", well_column="1", well_name="B1"),
                Replicate(well_row="B", well_column="2", well_name="B2"),
            ],
        ),
    }


@pytest.fixture
def sample_layout_df() -> pd.DataFrame:
    """Create a sample layout DataFrame."""
    return pd.DataFrame(
        {
            "Well": ["A", "B", "C"],
            "1": ["500uM_ATP_Protein1_Buffer1", "1mM_GTP_Protein2_Buffer2", "0_0_0_0"],
            "2": ["500uM_ATP_Protein1_Buffer1", "1mM_GTP_Protein2_Buffer2", "0_0_0_0"],
            "3": ["apo_DMSO_Protein1_Buffer1", "apo_DMSO_Protein2_Buffer2", "0_0_0_0"],
        }
    )


@pytest.fixture
def sample_raw_data_df() -> pd.DataFrame:
    """Create a sample raw data DataFrame with temperature and well columns."""
    temperatures = [25.0, 30.0, 35.0, 40.0, 45.0]
    data = {
        "Temperature": temperatures,
        "A1": [100.0, 105.0, 110.0, 115.0, 120.0],
        "A2": [101.0, 106.0, 111.0, 116.0, 121.0],
        "B1": [200.0, 205.0, 210.0, 215.0, 220.0],
        "B2": [201.0, 206.0, 211.0, 216.0, 221.0],
    }
    return pd.DataFrame(data)


@pytest.fixture
def temp_experiment_dir(tmp_path: Path) -> Path:
    """Create a temporary experiment directory for testing."""
    experiment_dir = tmp_path / "test_experiment"
    experiment_dir.mkdir(parents=True, exist_ok=True)
    return experiment_dir


@pytest.fixture
def sample_csv_files(tmp_path: Path) -> tuple[Path, Path]:
    """
    Create temporary CSV files for raw data and layout.

    Returns:
        Tuple of (raw_data_path, layout_path)
    """
    # Create raw data CSV
    raw_data = pd.DataFrame(
        {
            "Temperature": [25.0, 30.0, 35.0, 40.0, 45.0],
            "A1": [100.0, 105.0, 110.0, 115.0, 120.0],
            "A2": [101.0, 106.0, 111.0, 116.0, 121.0],
            "B1": [200.0, 205.0, 210.0, 215.0, 220.0],
            "B2": [201.0, 206.0, 211.0, 216.0, 221.0],
        }
    )
    raw_path = tmp_path / "raw_data.csv"
    raw_data.to_csv(raw_path, index=False)

    # Create layout CSV
    layout_data = pd.DataFrame(
        {
            "Well": ["A", "B"],
            "1": ["500uM_ATP_Protein1_Buffer1", "1mM_GTP_Protein2_Buffer2"],
            "2": ["500uM_ATP_Protein1_Buffer1", "1mM_GTP_Protein2_Buffer2"],
        }
    )
    layout_path = tmp_path / "layout.csv"
    layout_data.to_csv(layout_path, index=False)

    return raw_path, layout_path


@pytest.fixture
def sample_long_data_df() -> pd.DataFrame:
    """Create a sample long-format DataFrame for testing."""
    return pd.DataFrame(
        {
            "Temperature": [25.0, 30.0, 25.0, 30.0],
            "well": ["A1", "A1", "A2", "A2"],
            "value": [100.0, 105.0, 101.0, 106.0],
            "ligand": ["ATP", "ATP", "ATP", "ATP"],
            "protein": ["Protein1", "Protein1", "Protein1", "Protein1"],
            "buffer": ["Buffer1", "Buffer1", "Buffer1", "Buffer1"],
            "concentration": ["500uM", "500uM", "500uM", "500uM"],
            "well_unqcond": [
                "A1_500uM_ATP_Protein1_Buffer1",
                "A1_500uM_ATP_Protein1_Buffer1",
                "A2_500uM_ATP_Protein1_Buffer1",
                "A2_500uM_ATP_Protein1_Buffer1",
            ],
        }
    )


@pytest.fixture
def sample_unqcond_df() -> pd.DataFrame:
    """Create a DataFrame with unqcond column for testing split_unqcon_column."""
    return pd.DataFrame(
        {
            "unqcond": [
                "500uM_ATP_Protein1_Buffer1",
                "1mM_GTP_Protein2_Buffer2",
                "apo_DMSO_NPC_Buffer1",
            ],
            "value": [100.0, 200.0, 50.0],
        }
    )


# Parametrize fixtures for common test scenarios
@pytest.fixture(params=["500uM", "1mM", "10nM", "apo"])
def concentration_strings(request) -> str:
    """Parametrized fixture for different concentration formats."""
    return request.param


@pytest.fixture(
    params=[
        ("500uM_ATP_Protein1_Buffer1", ("concentration", "ligand", "protein", "buffer")),
        ("ATP_Protein1_500uM_Buffer1", ("ligand", "protein", "concentration", "buffer")),
    ]
)
def field_order_scenarios(request) -> tuple[str, tuple[str, ...]]:
    """Parametrized fixture for different field ordering scenarios."""
    return request.param


# ===== NEW API FIXTURES =====


@pytest.fixture
def experiment_context(tmp_path: Path) -> "ExperimentContext":
    """
    Create a sample ExperimentContext for testing.

    Note: This creates a context but does NOT create actual files.
    Use setup_experiment_fixture() for full setup with files.
    """
    from instawell.core.exp_context import ExperimentContext

    raw_path = tmp_path / "raw_data.csv"
    layout_path = tmp_path / "layout.csv"

    return ExperimentContext(
        experiment_name="test_exp",
        experiments_root=tmp_path / "experiments",
        raw_data_path=raw_path,
        layout_data_path=layout_path,
        fields=("concentration", "ligand", "protein", "buffer"),
        condition_separator="_",
        empty_condition_placeholder="0",
        temperature_column="Temperature",
    )


@pytest.fixture
def setup_experiment_fixture(tmp_path: Path, sample_csv_files) -> "ExperimentContext":
    """
    Setup a complete experiment with actual CSV files and initialized directory.

    This fixture:
    1. Creates raw data and layout CSV files
    2. Runs setup_experiment()
    3. Returns the ExperimentContext ready for processing

    Use this for integration tests that need a fully initialized experiment.
    """
    from instawell import setup_experiment

    raw_path, layout_path = sample_csv_files

    ctx = setup_experiment(
        experiment_name="test_exp",
        raw_data_path=str(raw_path),
        layout_data_path=str(layout_path),
        experiments_root=str(tmp_path / "experiments"),
    )

    return ctx


@pytest.fixture
def experiment_context_custom_separator(tmp_path: Path) -> "ExperimentContext":
    """Create an ExperimentContext with custom separator for testing."""
    from instawell.core.exp_context import ExperimentContext

    raw_path = tmp_path / "raw_data.csv"
    layout_path = tmp_path / "layout.csv"

    return ExperimentContext(
        experiment_name="test_exp_custom_sep",
        experiments_root=tmp_path / "experiments",
        raw_data_path=raw_path,
        layout_data_path=layout_path,
        condition_fields=("concentration", "ligand", "protein", "buffer"),
        condition_separator="|",  # Custom separator
        empty_condition_placeholder="^",
        temperature_column="Temperature",
    )
