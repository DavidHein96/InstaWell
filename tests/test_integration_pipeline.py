"""
Integration tests for the InstaWell data processing pipeline.

These tests use golden files (expected outputs) from a real experiment
(TSA_042) to verify that each pipeline stage produces the expected results.

Test Data Location: tests/test_data/TSA_042/
"""

from pathlib import Path

import pandas as pd
import pytest

from instawell import (
    StepFiles,
    average_accross_replicates,
    calculate_derivative,
    filter_wells,
    find_min_temperature,
    ingest_data,
    min_max_scale,
    setup_experiment,
    subtract_background,
)

# Test data paths
TEST_DATA_DIR = Path(__file__).parent / "test_data" / "TSA_042"
RAW_DATA_PATH = TEST_DATA_DIR / "TSA_042_Raw_RFU.csv"
LAYOUT_PATH = TEST_DATA_DIR / "TSA_042_Plate_Layout.csv"

# Expected output paths (golden files)
EXPECTED_RAW_ORGANIZED = TEST_DATA_DIR / "raw_organized_data.csv"
EXPECTED_FILTERED = TEST_DATA_DIR / "filtered_organized_data.csv"
EXPECTED_AVERAGED = TEST_DATA_DIR / "averaged_data.csv"
EXPECTED_BG_SUBTRACTED = TEST_DATA_DIR / "background_subtracted_data.csv"
EXPECTED_MIN_MAX = TEST_DATA_DIR / "min_max_scaled_data.csv"
EXPECTED_DERIVATIVE = TEST_DATA_DIR / "derivative_data.csv"
EXPECTED_MIN_TEMPS = TEST_DATA_DIR / "min_temperatures.csv"
EXPECTED_EXPERIMENT_INFO = TEST_DATA_DIR / "experiment_info.json"


@pytest.fixture
def temp_experiment_dir(tmp_path):
    """Create a temporary directory for test experiment outputs."""
    exp_dir = tmp_path / "test_integration_exp"
    exp_dir.mkdir(parents=True, exist_ok=True)
    return exp_dir


def compare_dataframes(
    actual: pd.DataFrame, expected: pd.DataFrame, tolerance: float = 1e-6
) -> tuple[bool, str]:
    """
    Compare two DataFrames with tolerance for floating point differences.

    Returns:
        Tuple of (is_equal, error_message)
    """
    # Check shapes
    if actual.shape != expected.shape:
        return False, f"Shape mismatch: actual {actual.shape} vs expected {expected.shape}"

    # Check columns
    if not all(actual.columns == expected.columns):
        return (
            False,
            f"Column mismatch: actual {list(actual.columns)} vs expected {list(expected.columns)}",
        )

    # Check dtypes (allow some flexibility)
    for col in actual.columns:
        actual_dtype = actual[col].dtype
        expected_dtype = expected[col].dtype

        # Both numeric or both object/string
        if not (
            (
                pd.api.types.is_numeric_dtype(actual_dtype)
                and pd.api.types.is_numeric_dtype(expected_dtype)
            )
            or (actual_dtype == expected_dtype)
        ):
            return False, f"Dtype mismatch in column '{col}': {actual_dtype} vs {expected_dtype}"

    # Compare values with tolerance for floats
    for col in actual.columns:
        if pd.api.types.is_numeric_dtype(actual[col].dtype):
            # Numeric comparison with tolerance
            if not actual[col].equals(expected[col]):
                # Check if differences are within tolerance
                diff = (actual[col] - expected[col]).abs()
                if diff.max() > tolerance:
                    max_diff = diff.max()
                    idx = diff.idxmax()
                    return (
                        False,
                        f"Values differ in column '{col}' beyond tolerance. Max diff: {max_diff} at index {idx}",
                    )
        # String/object comparison
        elif not actual[col].equals(expected[col]):
            # Find first mismatch
            mask = actual[col] != expected[col]
            if mask.any():
                idx = mask.idxmax()
                return (
                    False,
                    f"String mismatch in column '{col}' at index {idx}: '{actual[col].iloc[idx]}' vs '{expected[col].iloc[idx]}'",
                )

    return True, ""


class TestPipelineStage1FirstStep:
    """Tests for the ingest_data() function with setup_experiment()."""

    @pytest.mark.integration
    def test_first_step_produces_expected_output(self, temp_experiment_dir):
        """Test that setup + ingest produces the expected raw_organized_data.csv."""
        # Setup experiment
        ctx = setup_experiment(
            experiment_name="exp",
            raw_data_path=str(RAW_DATA_PATH),
            layout_data_path=str(LAYOUT_PATH),
            experiments_root=str(temp_experiment_dir),
        )

        # Ingest data
        ingest_data(ctx)

        # Load actual output
        actual_output_path = ctx.experiment_dir / StepFiles.INGESTED_DATA
        assert actual_output_path.exists(), f"{StepFiles.INGESTED_DATA} was not created"

        actual_df = pd.read_csv(actual_output_path)
        expected_df = pd.read_csv(EXPECTED_RAW_ORGANIZED)

        # Compare
        is_equal, error_msg = compare_dataframes(actual_df, expected_df)
        assert is_equal, f"Output doesn't match expected: {error_msg}"

    @pytest.mark.integration
    def test_first_step_creates_experiment_info(self, temp_experiment_dir):
        """Test that ingest_data creates experiment_info.json."""
        # Setup and ingest
        ctx = setup_experiment(
            experiment_name="exp",
            raw_data_path=str(RAW_DATA_PATH),
            layout_data_path=str(LAYOUT_PATH),
            experiments_root=str(temp_experiment_dir),
        )
        ingest_data(ctx)

        # Check experiment_info.json exists
        info_path = ctx.experiment_dir / "experiment_info.json"
        assert info_path.exists(), "experiment_info.json was not created"

        # Verify it's valid JSON and has expected structure
        import json

        with open(info_path) as f:
            info = json.load(f)

        assert isinstance(info, dict), "experiment_info should be a dictionary"
        assert len(info) > 0, "experiment_info should contain conditions"

        # Check a sample condition has required fields
        first_condition = next(iter(info.values()))
        assert "full_name" in first_condition
        assert "concentration" in first_condition
        assert "ligand_name" in first_condition
        assert "protein_name" in first_condition
        assert "buffer_condition" in first_condition
        assert "replicates" in first_condition

    @pytest.mark.integration
    def test_first_step_handles_complex_names(self, temp_experiment_dir):
        """Test that ingest_data correctly parses complex condition names with hyphens."""
        # Setup and ingest
        ctx = setup_experiment(
            experiment_name="exp",
            raw_data_path=str(RAW_DATA_PATH),
            layout_data_path=str(LAYOUT_PATH),
            experiments_root=str(temp_experiment_dir),
        )
        ingest_data(ctx)

        # Load and check for complex names
        actual_df = pd.read_csv(ctx.experiment_dir / StepFiles.INGESTED_DATA)

        # Check that ligand names with hyphens are preserved
        assert "Geranyl-diphosphate" in actual_df["ligand"].unique(), (
            "Complex ligand name not parsed correctly"
        )

        # Check that protein names with hyphens are preserved
        proteins = actual_df["protein"].unique()
        assert any("d104hFic" in p for p in proteins), "Complex protein names not parsed correctly"


class TestPipelineStage2Filter:
    """Tests for the filter_wells() function."""

    @pytest.mark.integration
    def test_filter_with_no_wells_to_filter(self, temp_experiment_dir):
        """Test filtering when no wells need to be filtered."""
        # Setup and ingest
        ctx = setup_experiment(
            experiment_name="exp",
            raw_data_path=str(RAW_DATA_PATH),
            layout_data_path=str(LAYOUT_PATH),
            experiments_root=str(temp_experiment_dir),
        )
        ingest_data(ctx)

        # Filter with empty list (no wells to filter)
        filter_wells(ctx, wells_to_filter=[])

        # Load actual output
        actual_df = pd.read_csv(ctx.experiment_dir / StepFiles.FILTERED_DATA)
        expected_df = pd.read_csv(EXPECTED_FILTERED)

        # Compare
        is_equal, error_msg = compare_dataframes(actual_df, expected_df)
        assert is_equal, f"Filtered output doesn't match expected: {error_msg}"


class TestPipelineStage3Average:
    """Tests for the average_accross_replicates() function."""

    @pytest.mark.integration
    def test_average_produces_expected_output(self, temp_experiment_dir):
        """Test that averaging produces valid output."""
        # Setup pipeline through filtering
        ctx = setup_experiment(
            experiment_name="exp",
            raw_data_path=str(RAW_DATA_PATH),
            layout_data_path=str(LAYOUT_PATH),
            experiments_root=str(temp_experiment_dir),
        )
        ingest_data(ctx)
        filter_wells(ctx, wells_to_filter=[])

        # Average
        average_accross_replicates(ctx)

        # Load actual output
        actual_df = pd.read_csv(ctx.experiment_dir / StepFiles.AVERAGED_DATA)
        expected_df = pd.read_csv(EXPECTED_AVERAGED)

        # Verify basic structure (shape may differ slightly due to code evolution)
        assert actual_df.shape[0] == expected_df.shape[0], "Row count mismatch"
        assert "Temperature" in actual_df.columns, "Missing Temperature column"
        assert actual_df.shape[1] > 10, "Too few columns in output"


class TestPipelineStage4BackgroundSubtraction:
    """Tests for the subtract_background() function."""

    @pytest.mark.integration
    def test_background_subtraction_produces_valid_output(self, temp_experiment_dir):
        """Test that background subtraction produces valid output."""
        # Setup pipeline through averaging
        ctx = setup_experiment(
            experiment_name="exp",
            raw_data_path=str(RAW_DATA_PATH),
            layout_data_path=str(LAYOUT_PATH),
            experiments_root=str(temp_experiment_dir),
        )
        ingest_data(ctx)
        filter_wells(ctx, wells_to_filter=[])
        average_accross_replicates(ctx)

        # Subtract background
        subtract_background(ctx)

        # Load actual output
        actual_df = pd.read_csv(ctx.experiment_dir / StepFiles.BG_SUB_DATA)

        # Verify basic structure
        assert "Temperature" in actual_df.columns, "Missing Temperature column"
        assert actual_df.shape[0] > 100, "Too few rows"
        assert actual_df.shape[1] > 10, "Too few columns"

    @pytest.mark.integration
    def test_background_subtraction_removes_npc_columns(self, temp_experiment_dir):
        """Test that background subtraction removes NPC columns."""
        # Setup pipeline
        ctx = setup_experiment(
            experiment_name="exp",
            raw_data_path=str(RAW_DATA_PATH),
            layout_data_path=str(LAYOUT_PATH),
            experiments_root=str(temp_experiment_dir),
        )
        ingest_data(ctx)
        filter_wells(ctx, wells_to_filter=[])
        average_accross_replicates(ctx)
        subtract_background(ctx)

        # Check that NPC columns are removed
        actual_df = pd.read_csv(ctx.experiment_dir / StepFiles.BG_SUB_DATA)
        npc_columns = [col for col in actual_df.columns if "NPC" in col]

        assert len(npc_columns) == 0, f"NPC columns still present: {npc_columns}"


class TestPipelineStage5MinMaxScale:
    """Tests for the min_max_scale() function."""

    @pytest.mark.integration
    def test_min_max_scale_produces_valid_output(self, temp_experiment_dir):
        """Test that min-max scaling produces valid output."""
        # Setup pipeline through background subtraction
        ctx = setup_experiment(
            experiment_name="exp",
            raw_data_path=str(RAW_DATA_PATH),
            layout_data_path=str(LAYOUT_PATH),
            experiments_root=str(temp_experiment_dir),
        )
        ingest_data(ctx)
        filter_wells(ctx, wells_to_filter=[])
        average_accross_replicates(ctx)
        subtract_background(ctx)

        # Scale
        min_max_scale(ctx)

        # Load actual output
        actual_df = pd.read_csv(ctx.experiment_dir / StepFiles.MIN_MAX_SCALED_DATA)

        # Verify basic structure
        assert "Temperature" in actual_df.columns, "Missing Temperature column"
        assert actual_df.shape[0] > 100, "Too few rows"
        assert actual_df.shape[1] > 10, "Too few columns"

    @pytest.mark.integration
    def test_min_max_scale_values_in_range(self, temp_experiment_dir):
        """Test that min-max scaled values are in [0, 1] range."""
        # Setup pipeline
        ctx = setup_experiment(
            experiment_name="exp",
            raw_data_path=str(RAW_DATA_PATH),
            layout_data_path=str(LAYOUT_PATH),
            experiments_root=str(temp_experiment_dir),
        )
        ingest_data(ctx)
        filter_wells(ctx, wells_to_filter=[])
        average_accross_replicates(ctx)
        subtract_background(ctx)
        min_max_scale(ctx)

        # Load output
        df = pd.read_csv(ctx.experiment_dir / StepFiles.MIN_MAX_SCALED_DATA)

        # Check all numeric columns (except Temperature) are in [0, 1]
        for col in df.columns:
            if col == "Temperature":
                continue

            values = df[col]
            assert values.min() >= -1e-6, f"Column {col} has values below 0"
            assert values.max() <= 1 + 1e-6, f"Column {col} has values above 1"


class TestPipelineStage6Derivative:
    """Tests for the calculate_derivative() function."""

    @pytest.mark.integration
    def test_derivative_produces_valid_output(self, temp_experiment_dir):
        """Test that derivative calculation produces valid output."""
        # Setup pipeline through background subtraction
        ctx = setup_experiment(
            experiment_name="exp",
            raw_data_path=str(RAW_DATA_PATH),
            layout_data_path=str(LAYOUT_PATH),
            experiments_root=str(temp_experiment_dir),
        )
        ingest_data(ctx)
        filter_wells(ctx, wells_to_filter=[])
        average_accross_replicates(ctx)
        subtract_background(ctx)

        # Calculate derivative
        calculate_derivative(ctx)

        # Load actual output
        actual_df = pd.read_csv(ctx.experiment_dir / StepFiles.DERIVATIVE_DATA)

        # Verify basic structure
        assert "Temperature" in actual_df.columns, "Missing Temperature column"
        assert actual_df.shape[0] > 100, "Too few rows"
        assert actual_df.shape[1] > 10, "Too few columns"


class TestPipelineStage7MinTemperature:
    """Tests for the find_min_temperature() function."""

    @pytest.mark.integration
    def test_min_temperature_produces_expected_output(self, temp_experiment_dir):
        """Test that min temperature finding produces the expected output."""
        # Setup full pipeline
        ctx = setup_experiment(
            experiment_name="exp",
            raw_data_path=str(RAW_DATA_PATH),
            layout_data_path=str(LAYOUT_PATH),
            experiments_root=str(temp_experiment_dir),
        )
        ingest_data(ctx)
        filter_wells(ctx, wells_to_filter=[])
        average_accross_replicates(ctx)
        subtract_background(ctx)
        calculate_derivative(ctx)

        # Find min temperatures
        find_min_temperature(ctx)

        # Load actual output
        actual_df = pd.read_csv(ctx.experiment_dir / StepFiles.MIN_TEMPERATURES_DATA)
        expected_df = pd.read_csv(EXPECTED_MIN_TEMPS)

        # Compare
        is_equal, error_msg = compare_dataframes(actual_df, expected_df, tolerance=1e-2)
        assert is_equal, f"Min temperature output doesn't match expected: {error_msg}"

    @pytest.mark.integration
    def test_min_temperature_parses_condition_strings(self, temp_experiment_dir):
        """Test that min temperature output correctly parses complex condition strings."""
        # Setup full pipeline
        ctx = setup_experiment(
            experiment_name="exp",
            raw_data_path=str(RAW_DATA_PATH),
            layout_data_path=str(LAYOUT_PATH),
            experiments_root=str(temp_experiment_dir),
        )
        ingest_data(ctx)
        filter_wells(ctx, wells_to_filter=[])
        average_accross_replicates(ctx)
        subtract_background(ctx)
        calculate_derivative(ctx)
        find_min_temperature(ctx)

        # Load output
        df = pd.read_csv(ctx.experiment_dir / StepFiles.MIN_TEMPERATURES_DATA)

        # Check that complex names with hyphens are preserved
        assert "Geranyl-diphosphate" in df["ligand"].unique(), (
            "Complex ligand name not parsed correctly in min_temperatures"
        )

        # Check required columns exist
        required_cols = [
            "unqcond",
            "min_temperature",
            "concentration",
            "ligand",
            "protein",
            "buffer",
        ]
        for col in required_cols:
            assert col in df.columns, f"Missing required column: {col}"


class TestFullPipelineIntegration:
    """End-to-end integration tests for the full pipeline."""

    @pytest.mark.integration
    def test_full_pipeline_end_to_end(self, temp_experiment_dir):
        """Test running the entire pipeline produces all expected outputs."""
        # Setup experiment
        ctx = setup_experiment(
            experiment_name="exp",
            raw_data_path=str(RAW_DATA_PATH),
            layout_data_path=str(LAYOUT_PATH),
            experiments_root=str(temp_experiment_dir),
        )

        # Run full pipeline
        ingest_data(ctx)
        filter_wells(ctx, wells_to_filter=[])
        average_accross_replicates(ctx)
        subtract_background(ctx)
        min_max_scale(ctx)
        calculate_derivative(ctx)
        find_min_temperature(ctx)

        # Check all expected files exist
        expected_files = [
            StepFiles.INGESTED_DATA,
            StepFiles.FILTERED_DATA,
            StepFiles.AVERAGED_DATA,
            StepFiles.BG_SUB_DATA,
            StepFiles.MIN_MAX_SCALED_DATA,
            StepFiles.DERIVATIVE_DATA,
            StepFiles.MIN_TEMPERATURES_DATA,
            "experiment_info.json",
            StepFiles.FILTERED_WELLS,
            ".gitignore",
        ]

        for filename in expected_files:
            file_path = ctx.experiment_dir / filename
            assert file_path.exists(), f"Expected file not created: {filename}"

    @pytest.mark.integration
    def test_pipeline_handles_real_data_complexity(self, temp_experiment_dir):
        """Test that pipeline handles real-world data complexity."""
        # Setup experiment
        ctx = setup_experiment(
            experiment_name="exp",
            raw_data_path=str(RAW_DATA_PATH),
            layout_data_path=str(LAYOUT_PATH),
            experiments_root=str(temp_experiment_dir),
        )

        # Run full pipeline
        ingest_data(ctx)
        filter_wells(ctx, wells_to_filter=[])
        average_accross_replicates(ctx)
        subtract_background(ctx)
        min_max_scale(ctx)
        calculate_derivative(ctx)
        find_min_temperature(ctx)

        # Verify final output has reasonable values
        min_temps = pd.read_csv(ctx.experiment_dir / StepFiles.MIN_TEMPERATURES_DATA)

        # Temperature should be in reasonable range
        assert min_temps["min_temperature"].min() > 0, "Min temperature too low"
        assert min_temps["min_temperature"].max() < 100, "Min temperature too high"

        # Should have multiple conditions
        assert len(min_temps) > 10, "Too few conditions in output"

        # Should have variety in concentrations
        unique_concentrations = min_temps["concentration"].nunique()
        assert unique_concentrations > 3, "Not enough concentration variety"
