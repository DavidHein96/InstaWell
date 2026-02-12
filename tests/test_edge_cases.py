"""
Tests for edge cases and error handling in the InstaWell pipeline.

This module tests:
- Custom separators in full pipeline
- Missing or malformed data files
- Empty datasets
- Special characters in condition names
- Error handling and recovery
"""

import pandas as pd
import pytest

from instawell import (
    StepFiles,
    filter_wells,
    ingest_data,
    setup_experiment,
)
from instawell.core.parser import parse_condition_string


class TestCustomSeparators:
    """Tests for using custom separators throughout the pipeline."""

    @pytest.mark.integration
    def test_pipeline_with_pipe_separator(self, tmp_path):
        """Test full pipeline with pipe separator."""
        # Create test data with pipe separator in layout
        raw_data = pd.DataFrame(
            {
                "Temperature": [25.0, 30.0, 35.0],
                "A1": [100.0, 105.0, 110.0],
                "A2": [101.0, 106.0, 111.0],
            }
        )

        layout_data = pd.DataFrame(
            {
                "Well": ["A"],
                "1": ["500uM|ATP|Protein1|Buffer1"],
                "2": ["500uM|ATP|Protein1|Buffer1"],
            }
        )

        # Save to files
        raw_path = tmp_path / "raw.csv"
        layout_path = tmp_path / "layout.csv"
        raw_data.to_csv(raw_path, index=False)
        layout_data.to_csv(layout_path, index=False)

        # Setup with pipe separator
        ctx = setup_experiment(
            experiment_name="pipe_test",
            raw_data_path=str(raw_path),
            layout_data_path=str(layout_path),
            experiments_root=str(tmp_path / "experiments"),
            condition_separator="|",
            empty_condition_placeholder="^",
        )

        # Ingest should work
        ingest_data(ctx)

        # Verify the data was parsed correctly
        ingested_df = pd.read_csv(ctx.experiment_dir / StepFiles.INGESTED_DATA.value)
        assert "ligand" in ingested_df.columns
        assert "ATP" in ingested_df["ligand"].values

        # Verify separator is used in well_unqcond
        assert ingested_df["well_unqcond"].str.contains(r"\|").any()

    @pytest.mark.integration
    def test_pipeline_with_colon_separator(self, tmp_path):
        """Test pipeline with colon separator."""
        raw_data = pd.DataFrame(
            {
                "Temperature": [25.0, 30.0],
                "B1": [200.0, 205.0],
            }
        )

        layout_data = pd.DataFrame(
            {
                "Well": ["B"],
                "1": ["1mM:GTP:Protein2:Buffer2"],
            }
        )

        raw_path = tmp_path / "raw.csv"
        layout_path = tmp_path / "layout.csv"
        raw_data.to_csv(raw_path, index=False)
        layout_data.to_csv(layout_path, index=False)

        ctx = setup_experiment(
            experiment_name="colon_test",
            raw_data_path=str(raw_path),
            layout_data_path=str(layout_path),
            experiments_root=str(tmp_path / "experiments"),
            condition_separator=":",
            empty_condition_placeholder="~",
        )

        ingest_data(ctx)

        # Verify parsing worked
        ingested_df = pd.read_csv(ctx.experiment_dir / StepFiles.INGESTED_DATA.value)
        assert "GTP" in ingested_df["ligand"].values
        assert "Protein2" in ingested_df["protein"].values


class TestSpecialCharacters:
    """Tests for handling special characters in condition names."""

    @pytest.mark.unit
    def test_parse_condition_with_hyphens(self):
        """Test parsing conditions with hyphens in names."""
        result = parse_condition_string("500uM_ATP-gamma-S_d104hFic-H363A_Buffer-1")
        assert result.dimensions["concentration"] == "500uM"
        assert result.dimensions["ligand"] == "ATP-gamma-S"
        assert result.dimensions["protein"] == "d104hFic-H363A"
        assert result.dimensions["buffer"] == "Buffer-1"

    @pytest.mark.unit
    def test_parse_condition_with_numbers(self):
        """Test parsing conditions with numbers in names."""
        result = parse_condition_string("100nM_Ligand123_Protein456_Buffer789")
        assert result.dimensions["concentration"] == "100nM"
        assert result.dimensions["ligand"] == "Ligand123"
        assert result.dimensions["protein"] == "Protein456"
        assert result.dimensions["buffer"] == "Buffer789"

    @pytest.mark.unit
    def test_parse_condition_with_greek_letters(self):
        """Test parsing conditions with unicode characters."""
        result = parse_condition_string("50μM_ATP-γ-S_Proteinα_Bufferβ")
        assert result.dimensions["concentration"] == "50μM"
        assert result.dimensions["ligand"] == "ATP-γ-S"
        assert result.dimensions["protein"] == "Proteinα"
        assert result.dimensions["buffer"] == "Bufferβ"



class TestFilterWellsEdgeCases:
    """Tests for filter_wells edge cases."""

    @pytest.mark.integration
    def test_filter_all_wells_of_condition(self, tmp_path):
        """Test filtering all wells of a specific condition."""
        # Create data with 2 conditions
        raw_data = pd.DataFrame(
            {
                "Temperature": [25.0, 30.0],
                "A1": [100.0, 105.0],
                "A2": [101.0, 106.0],
                "B1": [200.0, 205.0],
                "B2": [201.0, 206.0],
            }
        )

        layout_data = pd.DataFrame(
            {
                "Well": ["A", "B"],
                "1": ["500uM_ATP_Protein1_Buffer1", "1mM_GTP_Protein2_Buffer2"],
                "2": ["500uM_ATP_Protein1_Buffer1", "1mM_GTP_Protein2_Buffer2"],
            }
        )

        raw_path = tmp_path / "raw.csv"
        layout_path = tmp_path / "layout.csv"
        raw_data.to_csv(raw_path, index=False)
        layout_data.to_csv(layout_path, index=False)

        ctx = setup_experiment(
            experiment_name="filter_test",
            raw_data_path=str(raw_path),
            layout_data_path=str(layout_path),
            experiments_root=str(tmp_path / "experiments"),
        )

        ingest_data(ctx)

        # Filter all wells of first condition
        filter_wells(ctx, wells_to_filter=["A1", "A2"])

        filtered_df = pd.read_csv(ctx.experiment_dir / StepFiles.FILTERED_DATA.value)

        # Should only have B1 and B2 left
        unique_wells = filtered_df["well"].unique()
        assert "A1" not in unique_wells
        assert "A2" not in unique_wells
        assert "B1" in unique_wells
        assert "B2" in unique_wells

    @pytest.mark.integration
    def test_filter_no_wells(self, tmp_path, sample_csv_files):
        """Test filtering with empty wells list."""
        raw_path, layout_path = sample_csv_files

        ctx = setup_experiment(
            experiment_name="no_filter_test",
            raw_data_path=str(raw_path),
            layout_data_path=str(layout_path),
            experiments_root=str(tmp_path / "experiments"),
        )

        ingest_data(ctx)

        # Filter with empty list
        filter_wells(ctx, wells_to_filter=[])

        # Filtered data should have same number of rows as ingested
        ingested_df = pd.read_csv(ctx.experiment_dir / StepFiles.INGESTED_DATA.value)
        filtered_df = pd.read_csv(ctx.experiment_dir / StepFiles.FILTERED_DATA.value)

        assert len(filtered_df) == len(ingested_df)

    @pytest.mark.integration
    def test_filter_nonexistent_well(self, tmp_path, sample_csv_files):
        """Test filtering a well that doesn't exist (should not crash)."""
        raw_path, layout_path = sample_csv_files

        ctx = setup_experiment(
            experiment_name="nonexist_filter_test",
            raw_data_path=str(raw_path),
            layout_data_path=str(layout_path),
            experiments_root=str(tmp_path / "experiments"),
        )

        ingest_data(ctx)

        # Filter a well that doesn't exist - should not crash
        with pytest.raises(ValueError, match="Well Z99 not found in organized data"):
            filter_wells(ctx, wells_to_filter=["Z99"])

        # Should not create a filtered data file
        filtered_data_path = ctx.experiment_dir / StepFiles.FILTERED_DATA.value
        assert not filtered_data_path.exists()


class TestEmptyConditions:
    """Tests for handling empty/placeholder conditions."""

    @pytest.mark.integration
    def test_parse_empty_condition_placeholder(self, tmp_path):
        """Test that empty condition placeholders are handled correctly."""
        raw_data = pd.DataFrame(
            {
                "Temperature": [25.0, 30.0],
                "A1": [100.0, 105.0],
                "C1": [50.0, 55.0],  # Empty well
            }
        )

        layout_data = pd.DataFrame(
            {
                "Well": ["A", "C"],
                "1": ["500uM_ATP_Protein1_Buffer1", "0_0_0_0"],  # C1 is empty
            }
        )

        raw_path = tmp_path / "raw.csv"
        layout_path = tmp_path / "layout.csv"
        raw_data.to_csv(raw_path, index=False)
        layout_data.to_csv(layout_path, index=False)

        ctx = setup_experiment(
            experiment_name="empty_test",
            raw_data_path=str(raw_path),
            layout_data_path=str(layout_path),
            experiments_root=str(tmp_path / "experiments"),
        )

        ingest_data(ctx)

        ingested_df = pd.read_csv(ctx.experiment_dir / StepFiles.INGESTED_DATA.value)

        # Check that C1 was parsed with placeholder values
        c1_data = ingested_df[ingested_df["well"] == "C1"]
        assert len(c1_data) > 0
        # The placeholder values should be present
        assert "0" in c1_data["ligand"].values or c1_data["ligand"].isna().any()


class TestParserEdgeCases:
    """Tests for parser edge cases."""

    @pytest.mark.unit
    def test_parse_very_long_component_names(self):
        """Test parsing with very long component names."""
        long_ligand = "A" * 100
        condition_str = f"500uM_{long_ligand}_Protein1_Buffer1"

        result = parse_condition_string(condition_str)

        assert result.dimensions["ligand"] == long_ligand
        assert len(result.dimensions["ligand"]) == 100

    @pytest.mark.unit
    def test_parse_condition_with_extra_underscores(self):
        """Tests that an error is raised when there are too many components."""
        # This has 6 underscore-separated parts, should take last 4
        with pytest.raises(ValueError):
            parse_condition_string("Extra_Info_500uM_ATP_Protein1_Buffer1")

    @pytest.mark.unit
    def test_parse_minimal_components(self):
        """Test parsing with exactly 4 components (minimal valid input)."""
        result = parse_condition_string("A_B_C_D")
        assert result.dimensions["concentration"] == "A"
        assert result.dimensions["ligand"] == "B"
        assert result.dimensions["protein"] == "C"
        assert result.dimensions["buffer"] == "D"

    @pytest.mark.unit
    def test_parse_condition_invalid_too_few_components(self):
        """Test that too few components raises error."""
        with pytest.raises(ValueError, match="must have at least 4"):
            parse_condition_string("A_B_C")  # Only 3 components

    @pytest.mark.unit
    def test_parse_empty_string(self):
        """Test that empty string raises error."""
        with pytest.raises(ValueError, match="cannot be empty"):
            parse_condition_string("")

    @pytest.mark.unit
    def test_parse_whitespace_only(self):
        """Test that whitespace-only string raises error."""
        with pytest.raises(ValueError, match="cannot be empty"):
            parse_condition_string("   ")


class TestCustomFieldOrder:
    """Tests for custom field ordering."""

    @pytest.mark.integration
    def test_pipeline_with_reversed_field_order(self, tmp_path):
        """Test pipeline with reversed field order."""
        raw_data = pd.DataFrame(
            {
                "Temperature": [25.0, 30.0],
                "A1": [100.0, 105.0],
            }
        )

        # Layout with reversed order: buffer, protein, ligand, concentration
        layout_data = pd.DataFrame(
            {
                "Well": ["A"],
                "1": ["Buffer1_Protein1_ATP_500uM"],
            }
        )

        raw_path = tmp_path / "raw.csv"
        layout_path = tmp_path / "layout.csv"
        raw_data.to_csv(raw_path, index=False)
        layout_data.to_csv(layout_path, index=False)

        ctx = setup_experiment(
            experiment_name="reversed_test",
            raw_data_path=str(raw_path),
            layout_data_path=str(layout_path),
            experiments_root=str(tmp_path / "experiments"),
            condition_fields=("buffer", "protein", "ligand", "concentration"),
        )

        ingest_data(ctx)

        ingested_df = pd.read_csv(ctx.experiment_dir / StepFiles.INGESTED_DATA.value)

        # Verify correct parsing with reversed order
        assert "Buffer1" in ingested_df["buffer"].values
        assert "Protein1" in ingested_df["protein"].values
        assert "ATP" in ingested_df["ligand"].values
        assert "500uM" in ingested_df["concentration"].values
