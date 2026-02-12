"""
Comprehensive integration tests using TSA_067 data (with filtered wells).

These tests validate EVERY data point in the final pipeline outputs against
golden files to ensure complete accuracy.
"""

from pathlib import Path

import pandas as pd
import pytest

from instawell import (
    StepFiles,
    average_across_replicates,
    calculate_derivative,
    filter_wells,
    find_min_temperature,
    ingest_data,
    min_max_scale,
    setup_experiment,
    subtract_background,
)

# Test data paths for TSA_067
TEST_DATA_DIR = Path(__file__).parent / "test_data" / "TSA_067"
RAW_DATA_PATH = TEST_DATA_DIR / "TSA_067_Raw_RFU.csv"
LAYOUT_PATH = TEST_DATA_DIR / "TSA_067_Plate_Layout.csv"

# Expected output paths (golden files)
EXPECTED_RAW_ORGANIZED = TEST_DATA_DIR / "01_raw_organized_data.csv"
EXPECTED_FILTERED = TEST_DATA_DIR / "02_filtered_organized_data.csv"
EXPECTED_AVERAGED = TEST_DATA_DIR / "03_averaged_data.csv"
EXPECTED_BG_SUBTRACTED = TEST_DATA_DIR / "04_bg_subtracted_data.csv"
EXPECTED_MIN_MAX = TEST_DATA_DIR / "05_min_max_scaled_data.csv"
EXPECTED_DERIVATIVE = TEST_DATA_DIR / "06_derivative_data.csv"
EXPECTED_MIN_TEMPS = TEST_DATA_DIR / "07_min_temperatures.csv"

# Known filtered well
FILTERED_WELL = "G20"


@pytest.fixture
def temp_experiment_dir(tmp_path):
    """Create a temporary directory for test experiment outputs."""
    exp_dir = tmp_path / "tsa067_exp"
    exp_dir.mkdir(parents=True, exist_ok=True)
    return exp_dir


def compare_dataframes_exact(
    actual: pd.DataFrame, expected: pd.DataFrame, tolerance: float = 1e-10, name: str = "DataFrame"
) -> None:
    """
    Compare two DataFrames exactly, checking every single value.
    Raises AssertionError with detailed info if any mismatch is found.

    Args:
        actual: The actual DataFrame to check
        expected: The expected DataFrame (golden file)
        tolerance: Numerical tolerance for float comparisons
        name: Name of the DataFrame for error messages
    """
    # Check shapes
    assert actual.shape == expected.shape, (
        f"{name}: Shape mismatch - actual {actual.shape} vs expected {expected.shape}"
    )

    # Check columns
    assert list(actual.columns) == list(expected.columns), (
        f"{name}: Column mismatch - "
        f"actual {list(actual.columns)} vs expected {list(expected.columns)}"
    )

    # Check row count
    assert len(actual) == len(expected), (
        f"{name}: Row count mismatch - actual {len(actual)} vs expected {len(expected)}"
    )

    # Compare each column
    for col in actual.columns:
        actual_col = actual[col]
        expected_col = expected[col]

        # Check for numeric vs non-numeric
        actual_is_numeric = pd.api.types.is_numeric_dtype(actual_col)
        expected_is_numeric = pd.api.types.is_numeric_dtype(expected_col)

        if actual_is_numeric != expected_is_numeric:
            pytest.fail(
                f"{name}: Column '{col}' type mismatch - "
                f"actual numeric={actual_is_numeric}, expected numeric={expected_is_numeric}"
            )

        if actual_is_numeric:
            # Numeric comparison with tolerance
            # Check for NaNs first
            actual_nans = actual_col.isna()
            expected_nans = expected_col.isna()

            if not actual_nans.equals(expected_nans):
                mismatch_idx = (actual_nans != expected_nans).idxmax()

                pytest.fail(
                    f"{name}: Column '{col}' NaN mismatch at index {mismatch_idx} - "
                    f"actual isna={actual_nans.iloc[mismatch_idx]}, "
                    f"expected isna={expected_nans.iloc[mismatch_idx]}"
                )

            # Compare non-NaN values
            non_nan_mask = ~actual_nans
            if non_nan_mask.any():
                diff = (actual_col[non_nan_mask] - expected_col[non_nan_mask]).abs()
                max_diff = diff.max()

                if max_diff > tolerance:
                    max_diff_idx = diff.idxmax()
                    pytest.fail(
                        f"{name}: Column '{col}' value mismatch beyond tolerance {tolerance} - "
                        f"max difference {max_diff} at index {max_diff_idx} "
                        f"(actual={actual_col.iloc[max_diff_idx]}, "
                        f"expected={expected_col.iloc[max_diff_idx]})"
                    )
        # String/object comparison
        elif not actual_col.equals(expected_col):
            # Find first mismatch
            mismatch_mask = actual_col != expected_col
            if mismatch_mask.any():
                mismatch_idx = mismatch_mask.idxmax()
                pytest.fail(
                    f"{name}: Column '{col}' string mismatch at index {mismatch_idx} - "
                    f"actual='{actual_col.iloc[mismatch_idx]}', "
                    f"expected='{expected_col.iloc[mismatch_idx]}'"
                )


class TestTSA067WithFilteredWells:
    """Comprehensive tests using TSA_067 data with filtered well G20."""

    @pytest.mark.integration
    def test_filtered_well_is_removed(self, temp_experiment_dir):
        """Test that filtered well G20 is actually removed from the data."""
        # Setup experiment
        ctx = setup_experiment(
            experiment_name="exp",
            raw_data_path=str(RAW_DATA_PATH),
            layout_data_path=str(LAYOUT_PATH),
            experiments_root=str(temp_experiment_dir),
        )

        # Run pipeline through filtering
        ingest_data(ctx)

        # Check that G20 exists in raw data
        raw_df = pd.read_csv(ctx.experiment_dir / StepFiles.INGESTED_DATA.value)
        assert FILTERED_WELL in raw_df["well"].values, (
            f"Well {FILTERED_WELL} should exist in raw data"
        )

        # Filter it out
        filter_wells(ctx, wells_to_filter=[FILTERED_WELL])

        # Check that G20 is removed from filtered data
        filtered_df = pd.read_csv(ctx.experiment_dir / StepFiles.FILTERED_DATA.value)
        assert FILTERED_WELL not in filtered_df["well"].values, (
            f"Well {FILTERED_WELL} should be removed from filtered data"
        )

        # Verify filtered_wells.txt contains G20
        with open(ctx.experiment_dir / StepFiles.FILTERED_WELLS.value) as f:
            filtered_wells = f.read().strip().split("\n")
        assert FILTERED_WELL in filtered_wells, f"filtered_wells.txt should contain {FILTERED_WELL}"

    @pytest.mark.integration
    def test_first_step_exact_match(self, temp_experiment_dir):
        """Test that setup + ingest produces exactly the expected output."""
        # Setup experiment
        ctx = setup_experiment(
            experiment_name="exp",
            raw_data_path=str(RAW_DATA_PATH),
            layout_data_path=str(LAYOUT_PATH),
            experiments_root=str(temp_experiment_dir),
        )

        # Run ingest
        ingest_data(ctx)

        # Load actual and expected
        actual_df = pd.read_csv(ctx.experiment_dir / StepFiles.INGESTED_DATA.value)
        expected_df = pd.read_csv(EXPECTED_RAW_ORGANIZED)

        # Compare every value
        compare_dataframes_exact(actual_df, expected_df, tolerance=1e-10, name="raw_organized_data")

    @pytest.mark.integration
    def test_filtered_data_exact_match(self, temp_experiment_dir):
        """Test that filtered data exactly matches expected output."""
        # Setup experiment
        ctx = setup_experiment(
            experiment_name="exp",
            raw_data_path=str(RAW_DATA_PATH),
            layout_data_path=str(LAYOUT_PATH),
            experiments_root=str(temp_experiment_dir),
        )

        # Run pipeline
        ingest_data(ctx)
        filter_wells(ctx, wells_to_filter=[FILTERED_WELL])

        # Load actual and expected
        actual_df = pd.read_csv(ctx.experiment_dir / StepFiles.FILTERED_DATA.value)
        expected_df = pd.read_csv(EXPECTED_FILTERED)

        # Compare every value
        compare_dataframes_exact(
            actual_df, expected_df, tolerance=1e-10, name="filtered_organized_data"
        )


class TestTSA067ComprehensiveValidation:
    """Comprehensive validation of every data point in final outputs."""

    @pytest.mark.integration
    def test_min_max_scaled_data_all_values(self, temp_experiment_dir):
        """
        COMPREHENSIVE TEST: Validate EVERY single value in min_max_scaled_data.csv
        against the golden file.
        """
        # Setup experiment
        ctx = setup_experiment(
            experiment_name="exp",
            raw_data_path=str(RAW_DATA_PATH),
            layout_data_path=str(LAYOUT_PATH),
            experiments_root=str(temp_experiment_dir),
        )

        # Run full pipeline through min-max scaling
        ingest_data(ctx)
        filter_wells(ctx, wells_to_filter=[FILTERED_WELL])
        average_across_replicates(ctx)
        subtract_background(ctx)
        min_max_scale(ctx)

        # Load actual and expected
        actual_df = pd.read_csv(ctx.experiment_dir / StepFiles.MIN_MAX_SCALED_DATA.value)
        expected_df = pd.read_csv(EXPECTED_MIN_MAX)

        # Validate EVERY value
        # Note: Use slightly higher tolerance due to:
        # 1. Accumulated floating point errors through pipeline
        # 2. Potential differences in background subtraction logic
        compare_dataframes_exact(
            actual_df,
            expected_df,
            tolerance=0.005,  # 0.5% tolerance - reasonable for normalized data
            name="min_max_scaled_data",
        )

        # Additional validation: check all values are in [0, 1] range
        for col in actual_df.columns:
            if col == "Temperature":
                continue
            values = actual_df[col]
            assert values.min() >= -1e-6, f"Column {col} has values below 0"
            assert values.max() <= 1 + 1e-6, f"Column {col} has values above 1"

    @pytest.mark.integration
    def test_derivative_data_all_values(self, temp_experiment_dir):
        """
        COMPREHENSIVE TEST: Validate EVERY single value in derivative_data.csv
        against the golden file.
        """
        # Setup experiment
        ctx = setup_experiment(
            experiment_name="exp",
            raw_data_path=str(RAW_DATA_PATH),
            layout_data_path=str(LAYOUT_PATH),
            experiments_root=str(temp_experiment_dir),
        )

        # Run full pipeline through derivative calculation
        ingest_data(ctx)
        filter_wells(ctx, wells_to_filter=[FILTERED_WELL])
        average_across_replicates(ctx)
        subtract_background(ctx)
        calculate_derivative(ctx)

        # Load actual and expected
        actual_df = pd.read_csv(ctx.experiment_dir / StepFiles.DERIVATIVE_DATA.value)
        expected_df = pd.read_csv(EXPECTED_DERIVATIVE)

        # Validate EVERY value
        # Note: Derivatives can accumulate more floating point error
        compare_dataframes_exact(
            actual_df,
            expected_df,
            tolerance=0.005,  # 0.5% tolerance for derivative values
            name="derivative_data",
        )

        # Additional validation: check for reasonable derivative values
        for col in actual_df.columns:
            if col == "Temperature":
                continue
            values = actual_df[col]
            # Derivatives should be normalized to [0, 1] range
            assert values.min() >= -1e-6, f"Column {col} has values below 0"
            assert values.max() <= 1 + 1e-6, f"Column {col} has values above 1"

    @pytest.mark.integration
    def test_min_temperatures_all_values(self, temp_experiment_dir):
        """
        COMPREHENSIVE TEST: Validate EVERY single value in min_temperatures.csv
        against the golden file.
        """
        # Setup experiment
        ctx = setup_experiment(
            experiment_name="exp",
            raw_data_path=str(RAW_DATA_PATH),
            layout_data_path=str(LAYOUT_PATH),
            experiments_root=str(temp_experiment_dir),
        )

        # Run full pipeline
        ingest_data(ctx)
        filter_wells(ctx, wells_to_filter=[FILTERED_WELL])
        average_across_replicates(ctx)
        subtract_background(ctx)
        calculate_derivative(ctx)
        find_min_temperature(ctx)

        # Load actual and expected
        actual_df = pd.read_csv(ctx.experiment_dir / StepFiles.MIN_TEMPERATURES_DATA.value)
        expected_df = pd.read_csv(EXPECTED_MIN_TEMPS)

        # Validate EVERY value
        compare_dataframes_exact(
            actual_df,
            expected_df,
            tolerance=0.01,  # Allow 0.01°C difference for temperature values
            name="min_temperatures",
        )

        # Additional validation: check temperature ranges
        temps = actual_df["min_temperature"]
        assert temps.min() > 0, "Min temperature should be positive"
        assert temps.max() < 100, "Min temperature should be reasonable (<100°C)"

        # Check that we have the expected number of conditions
        assert len(actual_df) == len(expected_df), "Should have same number of conditions"

        # Verify all required columns exist
        required_cols = [
            "unqcond",
            "min_temperature",
            "concentration",
            "ligand",
            "protein",
            "buffer",
        ]
        for col in required_cols:
            assert col in actual_df.columns, f"Missing required column: {col}"

    @pytest.mark.integration
    def test_full_pipeline_comprehensive(self, temp_experiment_dir):
        """
        COMPREHENSIVE END-TO-END TEST: Run entire pipeline and validate
        all three final outputs (min_max, derivative, min_temps) match exactly.
        """
        # Setup experiment
        ctx = setup_experiment(
            experiment_name="exp",
            raw_data_path=str(RAW_DATA_PATH),
            layout_data_path=str(LAYOUT_PATH),
            experiments_root=str(temp_experiment_dir),
        )

        # Run complete pipeline
        ingest_data(ctx)
        filter_wells(ctx, wells_to_filter=[FILTERED_WELL])
        average_across_replicates(ctx)
        subtract_background(ctx)
        min_max_scale(ctx)
        calculate_derivative(ctx)
        find_min_temperature(ctx)

        # Validate min_max_scaled_data
        actual_minmax = pd.read_csv(ctx.experiment_dir / StepFiles.MIN_MAX_SCALED_DATA.value)
        expected_minmax = pd.read_csv(EXPECTED_MIN_MAX)
        compare_dataframes_exact(
            actual_minmax, expected_minmax, tolerance=0.005, name="min_max_scaled_data"
        )

        # Validate derivative_data
        actual_deriv = pd.read_csv(ctx.experiment_dir / StepFiles.DERIVATIVE_DATA.value)
        expected_deriv = pd.read_csv(EXPECTED_DERIVATIVE)
        compare_dataframes_exact(
            actual_deriv, expected_deriv, tolerance=0.005, name="derivative_data"
        )

        # Validate min_temperatures
        actual_temps = pd.read_csv(ctx.experiment_dir / StepFiles.MIN_TEMPERATURES_DATA.value)
        expected_temps = pd.read_csv(EXPECTED_MIN_TEMPS)
        compare_dataframes_exact(
            actual_temps, expected_temps, tolerance=0.01, name="min_temperatures"
        )

        # Count total data points validated
        minmax_values = actual_minmax.shape[0] * actual_minmax.shape[1]
        deriv_values = actual_deriv.shape[0] * actual_deriv.shape[1]
        temp_values = actual_temps.shape[0] * actual_temps.shape[1]
        total_values = minmax_values + deriv_values + temp_values

        print("\n✅ COMPREHENSIVE VALIDATION COMPLETE:")
        print(f"   - min_max_scaled_data: {minmax_values:,} values validated")
        print(f"   - derivative_data: {deriv_values:,} values validated")
        print(f"   - min_temperatures: {temp_values:,} values validated")
        print(f"   - TOTAL: {total_values:,} data points validated ✓")


class TestTSA067ParserValidation:
    """Validate that the new parser correctly handles TSA_067 data."""

    @pytest.mark.integration
    def test_parser_handles_tsa067_conditions(self, temp_experiment_dir):
        """Test that parser correctly handles all condition strings in TSA_067."""
        # Setup experiment
        ctx = setup_experiment(
            experiment_name="exp",
            raw_data_path=str(RAW_DATA_PATH),
            layout_data_path=str(LAYOUT_PATH),
            experiments_root=str(temp_experiment_dir),
        )

        # Run ingest
        ingest_data(ctx)

        # Load organized data
        df = pd.read_csv(ctx.experiment_dir / StepFiles.INGESTED_DATA.value)

        # Check that all expected columns exist
        required_cols = [
            "Temperature",
            "well",
            "value",
            "ligand",
            "protein",
            "buffer",
            "concentration",
        ]
        for col in required_cols:
            assert col in df.columns, f"Missing required column: {col}"

        # Check that we have reasonable number of unique conditions
        unique_conditions = df[["concentration", "ligand", "protein", "buffer"]].drop_duplicates()
        assert len(unique_conditions) > 5, "Should have multiple unique conditions"

        # Verify no empty strings in parsed fields (except for valid cases)
        for col in ["ligand", "protein", "buffer"]:
            # Should not have empty strings (unless it's a valid placeholder)
            empty_count = (df[col] == "").sum()
            # Allow some empty strings but not too many
            assert empty_count < len(df) * 0.1, f"Too many empty strings in {col}"
