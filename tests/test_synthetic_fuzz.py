"""
Integration fuzz tests using deterministically generated synthetic data.

These tests generate synthetic DSF data with known ground-truth parameters,
run the complete pipeline, and verify that the outputs match the expected values.

This approach provides:
1. Complete control over test data
2. Known ground truth for validation
3. Reproducibility (deterministic generation)
4. Coverage of edge cases and parameter combinations
"""

import numpy as np
import pandas as pd
import pytest
from synthetic_data_generator import SyntheticDSFExperiment

from instawell import (
    StepFiles,
    average_across_replicates,
    calculate_curve_params,
    calculate_derivative,
    filter_wells,
    find_min_temperature,
    ingest_data,
    setup_experiment,
    subtract_background,
)


@pytest.fixture
def temp_synthetic_dir(tmp_path):
    """Create a temporary directory for synthetic test experiments."""
    exp_dir = tmp_path / "synthetic_fuzz_exp"
    exp_dir.mkdir(parents=True, exist_ok=True)
    return exp_dir


class TestSyntheticDataGeneration:
    """Test the synthetic data generator itself."""

    def test_generator_creates_valid_data(self, tmp_path):
        """Test that the generator creates valid DSF data."""
        gen = SyntheticDSFExperiment(
            temperature_range=(25.0, 95.0),
            temperature_step=0.5,
            seed=42,
        )

        # Add a simple dose-response series
        gen.add_dose_response_series(
            protein="TestProtein",
            ligand="TestLigand",
            buffer="TestBuffer",
            concentrations=[0, 1, 10, 30, 100, 300, 1000],  # uM
            bottom_tm=45.0,
            top_tm=55.0,
            ec50=100.0,
            hill=1.0,
            n_replicates=3,
        )

        # Add NPC controls
        gen.add_npc_controls(
            ligand="TestLigand",
            buffer="TestBuffer",
            concentrations=[0, 1, 10, 30, 100, 300, 1000],
            n_replicates=2,
        )

        # Generate data
        raw_df, layout_df = gen.generate_plate_data()

        # Validate raw data structure
        assert "Temperature" in raw_df.columns
        assert len(raw_df) == 141  # (95-25)/0.5 + 1 = 141 temperature points
        assert raw_df.shape[1] > 10  # Temperature + well columns

        # Validate layout structure
        assert "Well" in layout_df.columns
        assert layout_df.shape[0] == 10  # 10 rows (A-J)

        # Check that we have the expected number of conditions
        # 7 concentrations * 3 replicates = 21 protein wells
        # 7 concentrations * 2 replicates = 14 NPC wells
        # Total = 35 wells
        total_wells = sum(1 for col in layout_df.columns[1:] for val in layout_df[col] if val != "")
        assert total_wells == 35

    def test_ground_truth_tms_match_4pl(self):
        """Test that generated Tm values follow 4PL model."""
        gen = SyntheticDSFExperiment(seed=42)

        bottom_tm = 45.0
        top_tm = 55.0
        ec50 = 100.0
        hill = 1.0

        gen.add_dose_response_series(
            protein="Protein1",
            ligand="Ligand1",
            buffer="Buffer1",
            concentrations=[0, 1, 10, 30, 100, 300, 1000],
            bottom_tm=bottom_tm,
            top_tm=top_tm,
            ec50=ec50,
            hill=hill,
            n_replicates=2,
        )

        ground_truth = gen.get_ground_truth_tms()

        # Check that Tm at EC50 is approximately (bottom + top) / 2
        ec50_row = ground_truth[ground_truth["concentration"] == "100uM"]
        assert len(ec50_row) == 1
        ec50_tm = ec50_row["min_temperature"].values[0]

        expected_tm = (bottom_tm + top_tm) / 2
        assert abs(ec50_tm - expected_tm) < 0.1  # Within 0.1°C


class TestSingleProteinDoseResponse:
    """Test pipeline with a simple single-protein dose-response curve."""

    @pytest.fixture
    def simple_dose_response_data(self, tmp_path):
        """Generate a simple dose-response dataset."""
        gen = SyntheticDSFExperiment(
            temperature_range=(25.0, 95.0),
            temperature_step=0.5,
            seed=42,
        )

        # Single protein with clear dose response
        gen.add_dose_response_series(
            protein="Protein1",
            ligand="ATP",
            buffer="Buffer1",
            concentrations=[0, 1, 10, 30, 100, 300, 1000],  # uM (apo to 10mM)
            bottom_tm=45.0,
            top_tm=60.0,
            ec50=100.0,  # 100 uM
            hill=1.5,  # Positive cooperativity
            n_replicates=3,
            noise_std=5.0,
        )

        # Add NPC controls
        gen.add_npc_controls(
            ligand="ATP",
            buffer="Buffer1",
            concentrations=[0, 1, 10, 30, 100, 300, 1000],
            n_replicates=2,
        )

        # Generate and save data
        raw_df, layout_df = gen.generate_plate_data()

        raw_path = tmp_path / "raw_data.csv"
        layout_path = tmp_path / "layout.csv"

        raw_df.to_csv(raw_path, index=False)
        layout_df.to_csv(layout_path, index=False)

        return {
            "raw_path": raw_path,
            "layout_path": layout_path,
            "generator": gen,
        }

    @pytest.mark.integration
    def test_pipeline_recovers_correct_tms(self, temp_synthetic_dir, simple_dose_response_data):
        """
        Test that the pipeline correctly identifies Tm values from synthetic data.
        """
        data = simple_dose_response_data

        # Setup experiment
        ctx = setup_experiment(
            experiment_name="exp",
            raw_data_path=str(data["raw_path"]),
            layout_data_path=str(data["layout_path"]),
            experiments_root=str(temp_synthetic_dir),
        )

        # Run full pipeline through Step 07
        ingest_data(ctx)
        filter_wells(ctx, wells_to_filter=[])
        average_across_replicates(ctx)
        subtract_background(ctx)
        calculate_derivative(ctx)
        find_min_temperature(ctx)

        # Load pipeline output
        actual_tms = pd.read_csv(ctx.experiment_dir / StepFiles.MIN_TEMPERATURES_DATA.value)

        # Load ground truth
        ground_truth = data["generator"].get_ground_truth_tms()

        # Merge on condition
        merged = actual_tms.merge(
            ground_truth,
            on="unqcond",
            suffixes=("_actual", "_expected"),
        )

        # Check that we recovered all conditions
        assert len(merged) == len(ground_truth), "Should recover all conditions"

        # Check that Tm values are close to ground truth
        tm_diff = (merged["min_temperature_actual"] - merged["min_temperature_expected"]).abs()

        # Print detailed diagnostics
        print("\n📊 Tm Recovery Diagnostics:")
        print("\nCondition-by-condition comparison:")
        for _, row in merged.iterrows():
            diff = abs(row["min_temperature_actual"] - row["min_temperature_expected"])
            print(
                f"  {row['unqcond']:30s} | Expected: {row['min_temperature_expected']:5.1f}°C | "
                f"Actual: {row['min_temperature_actual']:5.1f}°C | Diff: {diff:4.1f}°C"
            )

        max_diff = tm_diff.max()
        mean_diff = tm_diff.mean()
        print(f"\n   Max difference: {max_diff:.3f}°C")
        print(f"   Mean difference: {mean_diff:.3f}°C")
        print(f"   Conditions tested: {len(merged)}")

        # Realistic tolerance accounting for:
        # - Temperature step size (0.5°C discretization → ±0.5°C potential error)
        # - Noise in synthetic data (50 RFU std, ~0.6% of signal)
        # - Derivative calculation using numerical gradient
        # - Background subtraction effects
        # - Averaging across replicates
        # Given these factors, 3-4°C max error is reasonable for synthetic data
        assert max_diff < 3.5, f"Max Tm difference too large: {max_diff:.2f}°C"
        assert mean_diff < 1.5, f"Mean Tm difference too large: {mean_diff:.2f}°C"

    @pytest.mark.integration
    def test_pipeline_recovers_4pl_parameters(self, temp_synthetic_dir, simple_dose_response_data):
        """
        Test that Step 08 correctly recovers 4PL dose-response parameters.
        """
        data = simple_dose_response_data

        # Setup experiment
        ctx = setup_experiment(
            experiment_name="exp",
            raw_data_path=str(data["raw_path"]),
            layout_data_path=str(data["layout_path"]),
            experiments_root=str(temp_synthetic_dir),
        )

        # Run full pipeline through Step 08
        ingest_data(ctx)
        filter_wells(ctx, wells_to_filter=[])
        average_across_replicates(ctx)
        subtract_background(ctx)
        calculate_derivative(ctx)
        find_min_temperature(ctx)
        calculate_curve_params(ctx, weighting="none")

        # Load pipeline output
        actual_params = pd.read_csv(ctx.experiment_dir / StepFiles.CURVE_PARAMS.value)

        # Load ground truth
        ground_truth = data["generator"].get_ground_truth_params()

        # Should have exactly one panel
        assert len(actual_params) == 1, "Should have one dose-response curve"
        assert len(ground_truth) == 1, "Ground truth should have one panel"

        actual = actual_params.iloc[0]
        expected = ground_truth.iloc[0]

        # Validate parameters with appropriate tolerances
        # Bottom Tm: ±1°C tolerance
        bottom_diff = abs(actual["bottom"] - expected["bottom"])
        assert bottom_diff < 1.0, f"Bottom Tm difference too large: {bottom_diff:.2f}°C"

        # Top Tm: ±1°C tolerance
        top_diff = abs(actual["top"] - expected["top"])
        assert top_diff < 1.0, f"Top Tm difference too large: {top_diff:.2f}°C"

        # EC50: compare in log space (±0.3 log units)
        log_ec50_diff = abs(np.log10(actual["EC50"]) - np.log10(expected["EC50"]))
        assert log_ec50_diff < 0.3, f"LogEC50 difference too large: {log_ec50_diff:.2f} log units"

        # Hill: ±0.5 absolute tolerance (Hill coefficients are hard to fit precisely)
        hill_diff = abs(actual["Hill"] - expected["Hill"])
        assert hill_diff < 0.5, f"Hill coefficient difference too large: {hill_diff:.2f}"

        # Print diagnostics
        print("\n📊 4PL Parameter Recovery:")
        print(f"   Bottom: {actual['bottom']:.2f}°C (expected: {expected['bottom']:.2f}°C)")
        print(f"   Top: {actual['top']:.2f}°C (expected: {expected['top']:.2f}°C)")
        print(f"   EC50: {actual['EC50']:.1f} uM (expected: {expected['EC50']:.1f} uM)")
        print(f"   Hill: {actual['Hill']:.2f} (expected: {expected['Hill']:.2f})")


class TestMultiProteinExperiment:
    """Test pipeline with multiple proteins and conditions."""

    @pytest.fixture
    def multi_protein_data(self, tmp_path):
        """Generate a complex multi-protein dataset."""
        gen = SyntheticDSFExperiment(
            temperature_range=(25.0, 95.0),
            temperature_step=0.5,
            seed=123,
        )

        # Protein 1: Strong stabilization by ATP
        gen.add_dose_response_series(
            protein="Kinase1",
            ligand="ATP",
            buffer="Buffer1",
            concentrations=[0, 1, 3, 10, 30, 100, 300, 1000],
            bottom_tm=42.0,
            top_tm=58.0,
            ec50=150.0,
            hill=1.2,
            n_replicates=3,
            noise_std=5.0,
        )

        # Protein 2: Moderate stabilization by ATP
        gen.add_dose_response_series(
            protein="Kinase2",
            ligand="ATP",
            buffer="Buffer1",
            concentrations=[0, 1, 3, 10, 30, 100, 300, 1000],
            bottom_tm=48.0,
            top_tm=56.0,
            ec50=150.0,
            hill=0.8,
            n_replicates=3,
            noise_std=5.0,
        )

        # Protein 1 with different ligand (GTP)
        gen.add_dose_response_series(
            protein="Kinase1",
            ligand="GTP",
            buffer="Buffer1",
            concentrations=[0, 1, 3, 10, 30, 100, 300, 1000],
            bottom_tm=42.0,
            top_tm=54.0,  # Less stabilization than ATP
            ec50=100.0,
            hill=1.0,
            n_replicates=3,
            noise_std=5.0,
        )

        # Add NPC controls for all conditions
        gen.add_npc_controls(
            ligand="ATP",
            buffer="Buffer1",
            concentrations=[0, 1, 3, 10, 30, 100, 300, 1000],
            n_replicates=2,
        )
        gen.add_npc_controls(
            ligand="GTP",
            buffer="Buffer1",
            concentrations=[0, 1, 3, 10, 30, 100, 300, 1000],
            n_replicates=2,
        )

        # Generate and save data
        raw_df, layout_df = gen.generate_plate_data()

        raw_path = tmp_path / "raw_data.csv"
        layout_path = tmp_path / "layout.csv"

        raw_df.to_csv(raw_path, index=False)
        layout_df.to_csv(layout_path, index=False)

        return {
            "raw_path": raw_path,
            "layout_path": layout_path,
            "generator": gen,
        }

    @pytest.mark.integration
    def test_multi_protein_pipeline_end_to_end(self, temp_synthetic_dir, multi_protein_data):
        """
        Test full pipeline with multiple proteins and ligands.
        """
        data = multi_protein_data

        # Setup experiment
        ctx = setup_experiment(
            experiment_name="exp",
            raw_data_path=str(data["raw_path"]),
            layout_data_path=str(data["layout_path"]),
            experiments_root=str(temp_synthetic_dir),
        )

        # Run full pipeline
        ingest_data(ctx)
        filter_wells(ctx, wells_to_filter=[])
        average_across_replicates(ctx)
        subtract_background(ctx)
        calculate_derivative(ctx)
        find_min_temperature(ctx)
        calculate_curve_params(ctx, weighting="none")

        # Validate Tm values
        actual_tms = pd.read_csv(ctx.experiment_dir / StepFiles.MIN_TEMPERATURES_DATA.value)
        ground_truth_tms = data["generator"].get_ground_truth_tms()

        # Should recover all conditions (3 series * 8 concentrations = 24 conditions)
        assert len(actual_tms) == len(ground_truth_tms) == 24

        # Validate 4PL parameters
        actual_params = pd.read_csv(ctx.experiment_dir / StepFiles.CURVE_PARAMS.value)
        ground_truth_params = data["generator"].get_ground_truth_params()

        # Should have 3 dose-response curves
        assert len(actual_params) == 3
        assert len(ground_truth_params) == 3

        # Validate each curve
        for _, expected_row in ground_truth_params.iterrows():
            # Find matching actual row
            actual_row = actual_params[
                (actual_params["protein"] == expected_row["protein"])
                & (actual_params["ligand"] == expected_row["ligand"])
            ]

            assert len(actual_row) == 1, (
                f"Should find exactly one match for {expected_row['protein']} + {expected_row['ligand']}"
            )

            actual_row = actual_row.iloc[0]

            # Validate parameters
            bottom_diff = abs(actual_row["bottom"] - expected_row["bottom"])
            top_diff = abs(actual_row["top"] - expected_row["top"])
            ec50_rel_diff = abs(actual_row["EC50"] - expected_row["EC50"]) / expected_row["EC50"]

            assert bottom_diff < 2.0, (
                f"{expected_row['protein']}/{expected_row['ligand']}: "
                f"Bottom Tm off by {bottom_diff:.2f}°C"
            )
            assert top_diff < 10.0, (
                f"{expected_row['protein']}/{expected_row['ligand']}: "
                f"Top Tm off by {top_diff:.2f}°C"
            )
            log_ec50_diff = abs(
                np.log10(actual_row["EC50"]) - np.log10(expected_row["EC50"])
            )
            assert log_ec50_diff < 1.5, (
                f"{expected_row['protein']}/{expected_row['ligand']}: "
                f"LogEC50 off by {log_ec50_diff:.2f} log units"
            )

        print(f"\n✅ Successfully validated {len(actual_params)} dose-response curves")


class TestEdgeCases:
    """Test pipeline behavior with edge cases and challenging scenarios."""

    def test_high_noise_data(self, temp_synthetic_dir, tmp_path):
        """Test pipeline with very noisy data."""
        gen = SyntheticDSFExperiment(seed=999)

        gen.add_dose_response_series(
            protein="NoisyProtein",
            ligand="Ligand1",
            buffer="Buffer1",
            concentrations=[0, 1, 3, 10, 30, 100, 300, 1000],
            bottom_tm=45.0,
            top_tm=55.0,
            ec50=100.0,
            hill=1.0,
            n_replicates=5,  # More replicates to combat noise
            noise_std=150.0,  # 5x normal noise
        )

        gen.add_npc_controls(
            ligand="Ligand1",
            buffer="Buffer1",
            concentrations=[0, 1, 3, 10, 30, 100, 300, 1000],
            n_replicates=3,
            noise_std=50.0,
        )

        raw_df, layout_df = gen.generate_plate_data()
        raw_path = tmp_path / "raw_data.csv"
        layout_path = tmp_path / "layout.csv"
        raw_df.to_csv(raw_path, index=False)
        layout_df.to_csv(layout_path, index=False)

        # Run pipeline
        ctx = setup_experiment(
            experiment_name="exp",
            raw_data_path=str(raw_path),
            layout_data_path=str(layout_path),
            experiments_root=str(temp_synthetic_dir),
        )

        ingest_data(ctx)
        filter_wells(ctx, wells_to_filter=[])
        average_across_replicates(ctx)
        subtract_background(ctx)
        calculate_derivative(ctx)
        find_min_temperature(ctx)

        # Validate that we still get reasonable results (with relaxed tolerance)
        actual_tms = pd.read_csv(ctx.experiment_dir / StepFiles.MIN_TEMPERATURES_DATA.value)
        ground_truth = gen.get_ground_truth_tms()

        merged = actual_tms.merge(ground_truth, on="unqcond", suffixes=("_actual", "_expected"))
        tm_diff = (merged["min_temperature_actual"] - merged["min_temperature_expected"]).abs()

        # With high noise, allow up to 5°C error
        assert tm_diff.max() < 5.0, "Even with high noise, Tm should be within 5°C"

    def test_shallow_transition(self, temp_synthetic_dir, tmp_path):
        """Test pipeline with shallow thermal transition (hard to detect Tm)."""
        gen = SyntheticDSFExperiment(seed=777)

        # Very shallow transition (small amplitude, gentle slope)
        gen.add_dose_response_series(
            protein="ShallowProtein",
            ligand="Ligand1",
            buffer="Buffer1",
            concentrations=[0, 1, 3, 10, 30, 100, 300, 1000],
            bottom_tm=50.0,
            top_tm=52.0,  # Only 2°C shift
            ec50=100.0,
            hill=0.5,  # Shallow slope
            n_replicates=3,
            amplitude=2000.0,  # Smaller amplitude
            noise_std=10.0,
        )

        gen.add_npc_controls(
            ligand="Ligand1",
            buffer="Buffer1",
            concentrations=[0, 1, 3, 10, 30, 100, 300, 1000],
            n_replicates=2,
        )

        raw_df, layout_df = gen.generate_plate_data()
        raw_path = tmp_path / "raw_data.csv"
        layout_path = tmp_path / "layout.csv"
        raw_df.to_csv(raw_path, index=False)
        layout_df.to_csv(layout_path, index=False)

        # Run pipeline
        ctx = setup_experiment(
            experiment_name="exp",
            raw_data_path=str(raw_path),
            layout_data_path=str(layout_path),
            experiments_root=str(temp_synthetic_dir),
        )

        ingest_data(ctx)
        filter_wells(ctx, wells_to_filter=[])
        average_across_replicates(ctx)
        subtract_background(ctx)
        calculate_derivative(ctx)
        find_min_temperature(ctx)

        # Just verify pipeline completes successfully
        assert (ctx.experiment_dir / StepFiles.MIN_TEMPERATURES_DATA.value).exists()

        # Optionally check that results are reasonable (but with very relaxed tolerance)
        actual_tms = pd.read_csv(ctx.experiment_dir / StepFiles.MIN_TEMPERATURES_DATA.value)
        assert len(actual_tms) == 8  # Should have both conditions
        assert all(6 < tm < 95 for tm in actual_tms["min_temperature"]), (
            "Tm values should be in reasonable range"
        )


class TestParameterizedFuzz:
    """Parametrized tests to fuzz different parameter combinations."""

    @pytest.mark.parametrize(
        "bottom_tm,top_tm,ec50,hill",
        [
            (40.0, 60.0, 50.0, 1.0),  # Standard parameters
            (45.0, 55.0, 100.0, 1.5),  # Steep Hill slope
            (50.0, 65.0, 500.0, 0.75),  # Shallow Hill slope
            (35.0, 70.0, 10.0, 1.5),  # Low EC50, large Tm shift
        ],
    )
    @pytest.mark.integration
    def test_various_4pl_parameters(
        self, temp_synthetic_dir, tmp_path, bottom_tm, top_tm, ec50, hill
    ):
        """
        Parametrized fuzz test: validate pipeline with various 4PL parameter combinations.
        """
        gen = SyntheticDSFExperiment(seed=42)

        gen.add_dose_response_series(
            protein="Protein1",
            ligand="Ligand1",
            buffer="Buffer1",
            concentrations=[0, 1, 3, 10, 30, 100, 300, 1000, 3000, 10000],
            bottom_tm=bottom_tm,
            top_tm=top_tm,
            ec50=ec50,
            hill=hill,
            n_replicates=3,
            noise_std=5.0,
        )

        gen.add_npc_controls(
            ligand="Ligand1",
            buffer="Buffer1",
            concentrations=[0, 1, 3, 10, 30, 100, 300, 1000, 3000, 10000],
            n_replicates=2,
            noise_std=2.0,
        )

        raw_df, layout_df = gen.generate_plate_data()
        raw_path = tmp_path / "raw_data.csv"
        layout_path = tmp_path / "layout.csv"
        raw_df.to_csv(raw_path, index=False)
        layout_df.to_csv(layout_path, index=False)

        # Run full pipeline
        ctx = setup_experiment(
            experiment_name="exp",
            raw_data_path=str(raw_path),
            layout_data_path=str(layout_path),
            experiments_root=str(temp_synthetic_dir),
        )

        ingest_data(ctx)
        filter_wells(ctx, wells_to_filter=[])
        average_across_replicates(ctx)
        subtract_background(ctx)
        calculate_derivative(ctx)
        find_min_temperature(ctx)
        calculate_curve_params(ctx, weighting="none")

        # Validate curve parameters
        actual_params = pd.read_csv(ctx.experiment_dir / StepFiles.CURVE_PARAMS.value)
        assert len(actual_params) == 1

        actual = actual_params.iloc[0]

        # Validate with reasonable tolerances
        assert abs(actual["bottom"] - bottom_tm) < 3.0
        assert abs(actual["top"] - top_tm) < 3.0
        assert abs(np.log10(actual["EC50"]) - np.log10(ec50)) < 0.3
        # Hill is hardest to recover precisely, especially for extreme values
        assert abs(actual["Hill"] - hill) < 1.0
