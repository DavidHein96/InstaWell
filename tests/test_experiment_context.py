"""
Tests for ExperimentContext and experiment setup/loading.

This module tests:
- ExperimentContext validation and computed fields
- setup_experiment() functionality
- load_experiment_context() functionality
- Custom separators and configuration
- Edge cases and error handling
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from instawell import (
    ExperimentContext,
    StepFiles,
    load_experiment_context,
    setup_experiment,
)


class TestExperimentContextValidation:
    """Tests for ExperimentContext Pydantic validation."""

    @pytest.mark.unit
    def test_create_valid_context(self, tmp_path):
        """Test creating a valid ExperimentContext."""
        raw_path = tmp_path / "raw.csv"
        layout_path = tmp_path / "layout.csv"

        # Create the files
        raw_path.touch()
        layout_path.touch()

        ctx = ExperimentContext(
            experiment_name="test_exp",
            experiments_root=tmp_path,
            raw_data_path=raw_path,
            layout_data_path=layout_path,
        )

        assert ctx.experiment_name == "test_exp"
        assert ctx.experiments_root == tmp_path
        assert ctx.experiment_dir == (tmp_path / "test_exp").resolve()

    @pytest.mark.unit
    def test_computed_experiment_dir(self, tmp_path):
        """Test that experiment_dir is computed correctly."""
        raw_path = tmp_path / "raw.csv"
        layout_path = tmp_path / "layout.csv"
        raw_path.touch()
        layout_path.touch()

        ctx = ExperimentContext(
            experiment_name="my_exp",
            experiments_root=tmp_path / "experiments",
            raw_data_path=raw_path,
            layout_data_path=layout_path,
        )

        expected_dir = (tmp_path / "experiments" / "my_exp").resolve()
        assert ctx.experiment_dir == expected_dir

    @pytest.mark.unit
    def test_default_values(self, tmp_path):
        """Test that default values are set correctly."""
        raw_path = tmp_path / "raw.csv"
        layout_path = tmp_path / "layout.csv"
        raw_path.touch()
        layout_path.touch()

        ctx = ExperimentContext(
            experiment_name="test",
            raw_data_path=raw_path,
            layout_data_path=layout_path,
        )

        # Check defaults
        assert ctx.experiments_root == Path("experiments")
        assert ctx.fields == ("concentration", "ligand", "protein", "buffer")
        assert ctx.well_col_identifier == "Well"
        assert ctx.empty_condition_placeholder == "0"
        assert ctx.condition_separator == "_"
        assert ctx.temperature_column == "Temperature"
        assert ctx.non_protein_control_marker == "NPC"

    @pytest.mark.unit
    def test_separator_validation_single_char(self, tmp_path):
        """Test that separator must be a single character."""
        raw_path = tmp_path / "raw.csv"
        layout_path = tmp_path / "layout.csv"
        raw_path.touch()
        layout_path.touch()

        # Multi-character separator should fail
        with pytest.raises(ValidationError, match="must be exactly one character"):
            ExperimentContext(
                experiment_name="test",
                raw_data_path=raw_path,
                layout_data_path=layout_path,
                condition_separator="__",
            )

    @pytest.mark.unit
    def test_separator_validation_no_whitespace(self, tmp_path):
        """Test that separator cannot be whitespace."""
        raw_path = tmp_path / "raw.csv"
        layout_path = tmp_path / "layout.csv"
        raw_path.touch()
        layout_path.touch()

        with pytest.raises(ValidationError, match="cannot be whitespace"):
            ExperimentContext(
                experiment_name="test",
                raw_data_path=raw_path,
                layout_data_path=layout_path,
                condition_separator=" ",
            )

    @pytest.mark.unit
    def test_separator_validation_no_csv_chars(self, tmp_path):
        """Test that separator cannot be comma or semicolon."""
        raw_path = tmp_path / "raw.csv"
        layout_path = tmp_path / "layout.csv"
        raw_path.touch()
        layout_path.touch()

        # Comma should fail
        with pytest.raises(ValidationError, match="not allowed"):
            ExperimentContext(
                experiment_name="test",
                raw_data_path=raw_path,
                layout_data_path=layout_path,
                condition_separator=",",
            )

        # Semicolon should fail
        with pytest.raises(ValidationError, match="not allowed"):
            ExperimentContext(
                experiment_name="test",
                raw_data_path=raw_path,
                layout_data_path=layout_path,
                condition_separator=";",
            )

    @pytest.mark.unit
    def test_separator_validation_no_alphanumeric(self, tmp_path):
        """Test that separator should not be alphanumeric."""
        raw_path = tmp_path / "raw.csv"
        layout_path = tmp_path / "layout.csv"
        raw_path.touch()
        layout_path.touch()

        with pytest.raises(ValidationError, match="should not be a letter or digit"):
            ExperimentContext(
                experiment_name="test",
                raw_data_path=raw_path,
                layout_data_path=layout_path,
                condition_separator="A",
            )

    @pytest.mark.unit
    def test_placeholder_validation(self, tmp_path):
        """Test empty_condition_placeholder validation."""
        raw_path = tmp_path / "raw.csv"
        layout_path = tmp_path / "layout.csv"
        raw_path.touch()
        layout_path.touch()

        # Multi-character placeholder should fail
        with pytest.raises(ValidationError, match="must be exactly one character"):
            ExperimentContext(
                experiment_name="test",
                raw_data_path=raw_path,
                layout_data_path=layout_path,
                empty_condition_placeholder="00",
            )

        # Alphanumeric placeholder should fail
        # with pytest.raises(ValidationError, match="should not be a letter or digit"):
        #     ExperimentContext(
        #         experiment_name="test",
        #         raw_data_path=raw_path,
        #         layout_data_path=layout_path,
        #         empty_condition_placeholder="0",
        #     )

    @pytest.mark.unit
    def test_separator_and_placeholder_must_differ(self, tmp_path):
        """Test that separator and placeholder cannot be the same."""
        raw_path = tmp_path / "raw.csv"
        layout_path = tmp_path / "layout.csv"
        raw_path.touch()
        layout_path.touch()

        with pytest.raises(ValidationError, match="must be different"):
            ExperimentContext(
                experiment_name="test",
                raw_data_path=raw_path,
                layout_data_path=layout_path,
                condition_separator="|",
                empty_condition_placeholder="|",
            )

    @pytest.mark.unit
    def test_empty_condition_mask(self, tmp_path):
        """Test that empty_condition_mask is computed correctly."""
        raw_path = tmp_path / "raw.csv"
        layout_path = tmp_path / "layout.csv"
        raw_path.touch()
        layout_path.touch()

        ctx = ExperimentContext(
            experiment_name="test",
            raw_data_path=raw_path,
            layout_data_path=layout_path,
            fields=("a", "b", "c", "d"),
            condition_separator="|",
            empty_condition_placeholder="^",
        )

        assert ctx.empty_condition_mask == "^|^|^|^"

    @pytest.mark.unit
    def test_custom_fields_order(self, tmp_path):
        """Test that custom field order is preserved."""
        raw_path = tmp_path / "raw.csv"
        layout_path = tmp_path / "layout.csv"
        raw_path.touch()
        layout_path.touch()

        custom_fields = ("ligand", "protein", "concentration", "buffer")
        ctx = ExperimentContext(
            experiment_name="test",
            raw_data_path=raw_path,
            layout_data_path=layout_path,
            fields=custom_fields,
        )

        assert ctx.fields == custom_fields

    @pytest.mark.unit
    def test_created_at_timestamp(self, tmp_path):
        """Test that created_at timestamp is set."""
        raw_path = tmp_path / "raw.csv"
        layout_path = tmp_path / "layout.csv"
        raw_path.touch()
        layout_path.touch()

        ctx = ExperimentContext(
            experiment_name="test",
            raw_data_path=raw_path,
            layout_data_path=layout_path,
        )

        assert ctx.created_at is not None
        assert ctx.created_at_iso is not None
        assert isinstance(ctx.created_at_iso, str)
        assert "T" in ctx.created_at_iso  # ISO format has T


class TestSetupExperiment:
    """Tests for setup_experiment() function."""

    @pytest.mark.unit
    def test_setup_creates_experiment_dir(self, tmp_path, sample_csv_files):
        """Test that setup_experiment creates the experiment directory."""
        raw_path, layout_path = sample_csv_files

        ctx = setup_experiment(
            experiment_name="test_exp",
            raw_data_path=str(raw_path),
            layout_data_path=str(layout_path),
            experiments_root=str(tmp_path),
        )

        assert ctx.experiment_dir.exists()
        assert ctx.experiment_dir.is_dir()

    @pytest.mark.unit
    def test_setup_saves_metadata(self, tmp_path, sample_csv_files):
        """Test that setup_experiment saves experiment.json metadata."""
        raw_path, layout_path = sample_csv_files

        ctx = setup_experiment(
            experiment_name="test_exp",
            raw_data_path=str(raw_path),
            layout_data_path=str(layout_path),
            experiments_root=str(tmp_path),
        )

        metadata_path = ctx.metadata_path
        assert metadata_path.exists()

        # Load and verify metadata
        import json

        with open(metadata_path) as f:
            metadata = json.load(f)

        assert metadata["experiment_name"] == "test_exp"
        assert "created_at" in metadata

    @pytest.mark.unit
    def test_setup_copies_data_files(self, tmp_path, sample_csv_files):
        """Test that setup_experiment copies raw data files to experiment dir."""
        raw_path, layout_path = sample_csv_files

        ctx = setup_experiment(
            experiment_name="test_exp",
            raw_data_path=str(raw_path),
            layout_data_path=str(layout_path),
            experiments_root=str(tmp_path),
        )

        # Check that files were copied
        assert (ctx.experiment_dir / "raw_data.csv").exists()
        assert (ctx.experiment_dir / "layout.csv").exists()

    @pytest.mark.unit
    def test_setup_with_custom_separator(self, tmp_path, sample_csv_files):
        """Test setup_experiment with custom separator."""
        raw_path, layout_path = sample_csv_files

        ctx = setup_experiment(
            experiment_name="test_exp",
            raw_data_path=str(raw_path),
            layout_data_path=str(layout_path),
            experiments_root=str(tmp_path),
            condition_separator="|",
            empty_condition_placeholder="^",
        )

        assert ctx.condition_separator == "|"
        assert ctx.empty_condition_placeholder == "^"
        assert ctx.empty_condition_mask == "^|^|^|^"


class TestLoadExperimentContext:
    """Tests for load_experiment_context() function."""

    @pytest.mark.unit
    def test_load_existing_experiment(self, tmp_path, sample_csv_files):
        """Test loading an existing experiment context."""
        raw_path, layout_path = sample_csv_files

        # First, create an experiment
        original_ctx = setup_experiment(
            experiment_name="test_exp",
            raw_data_path=str(raw_path),
            layout_data_path=str(layout_path),
            experiments_root=str(tmp_path),
        )

        # Now load it
        loaded_ctx = load_experiment_context("test_exp", experiments_root=str(tmp_path))

        # Verify loaded context matches original
        assert loaded_ctx.experiment_name == original_ctx.experiment_name
        assert loaded_ctx.experiment_dir == original_ctx.experiment_dir
        assert loaded_ctx.fields == original_ctx.fields
        assert loaded_ctx.condition_separator == original_ctx.condition_separator

    @pytest.mark.unit
    def test_load_with_custom_config(self, tmp_path, sample_csv_files):
        """Test that loaded context preserves custom configuration."""
        raw_path, layout_path = sample_csv_files

        # Create with custom config
        original_ctx = setup_experiment(
            experiment_name="test_exp",
            raw_data_path=str(raw_path),
            layout_data_path=str(layout_path),
            experiments_root=str(tmp_path),
            condition_separator="|",
            fields=("ligand", "protein", "concentration", "buffer"),
        )

        # Load it
        loaded_ctx = load_experiment_context("test_exp", experiments_root=str(tmp_path))

        # Verify custom config is preserved
        assert loaded_ctx.condition_separator == "|"
        assert loaded_ctx.fields == ("ligand", "protein", "concentration", "buffer")

    @pytest.mark.unit
    def test_load_nonexistent_experiment_fails(self, tmp_path):
        """Test that loading nonexistent experiment raises error."""
        with pytest.raises(FileNotFoundError):
            load_experiment_context("nonexistent", experiments_root=str(tmp_path))

    @pytest.mark.unit
    def test_setup_and_load_roundtrip(self, tmp_path, sample_csv_files):
        """Test that setup -> load preserves all data."""
        raw_path, layout_path = sample_csv_files

        # Setup with various custom options
        original_ctx = setup_experiment(
            experiment_name="roundtrip_test",
            raw_data_path=str(raw_path),
            layout_data_path=str(layout_path),
            experiments_root=str(tmp_path),
            fields=("protein", "ligand", "buffer", "concentration"),
            condition_separator="|",
            empty_condition_placeholder="~",
            temperature_column="Temp",
            non_protein_control_marker="CTRL",
        )

        # Load it back
        loaded_ctx = load_experiment_context("roundtrip_test", experiments_root=str(tmp_path))

        # Verify all fields match
        assert loaded_ctx.experiment_name == original_ctx.experiment_name
        assert loaded_ctx.fields == original_ctx.fields
        assert loaded_ctx.condition_separator == original_ctx.condition_separator
        assert loaded_ctx.empty_condition_placeholder == original_ctx.empty_condition_placeholder
        assert loaded_ctx.temperature_column == original_ctx.temperature_column
        assert loaded_ctx.non_protein_control_marker == original_ctx.non_protein_control_marker


class TestStepFilesEnum:
    """Tests for StepFiles enum."""

    @pytest.mark.unit
    def test_step_files_values(self):
        """Test that StepFiles enum has expected values."""
        assert StepFiles.INGESTED_DATA == "01_raw_organized_data.csv"
        assert StepFiles.FILTERED_DATA == "02_filtered_organized_data.csv"
        assert StepFiles.AVERAGED_DATA == "03_averaged_data.csv"
        assert StepFiles.BG_SUB_DATA == "04_bg_subtracted_data.csv"
        assert StepFiles.MIN_MAX_SCALED_DATA == "05_min_max_scaled_data.csv"
        assert StepFiles.DERIVATIVE_DATA == "06_derivative_data.csv"
        assert StepFiles.MIN_TEMPERATURES_DATA == "07_min_temperatures.csv"
        assert StepFiles.FILTERED_WELLS == "filtered_wells.txt"

    @pytest.mark.unit
    def test_step_files_are_strings(self):
        """Test that StepFiles enum members are strings."""
        for step_file in StepFiles:
            assert isinstance(step_file.value, str)
            assert len(step_file.value) > 0
