"""
Tests for the data_models module.

This module tests the Pydantic models for Replicate and UniqueCondition,
ensuring validation, serialization, and proper data handling.
"""

import pytest
from pydantic import ValidationError

from instawell.core.data_models import Replicate, UniqueCondition


class TestReplicate:
    """Tests for the Replicate model."""

    @pytest.mark.unit
    def test_create_replicate(self, sample_replicate):
        """Test creating a valid Replicate."""
        assert sample_replicate.well_row == "A"
        assert sample_replicate.well_column == "1"
        assert sample_replicate.well_name == "A1"

    @pytest.mark.unit
    def test_replicate_with_all_fields(self):
        """Test creating Replicate with all fields."""
        replicate = Replicate(
            well_row="B",
            well_column="12",
            well_name="B12",
        )
        assert replicate.well_row == "B"
        assert replicate.well_column == "12"
        assert replicate.well_name == "B12"

    @pytest.mark.unit
    def test_replicate_serialization(self, sample_replicate):
        """Test serializing Replicate to dict."""
        data = sample_replicate.model_dump()

        assert data["well_row"] == "A"
        assert data["well_column"] == "1"
        assert data["well_name"] == "A1"

    @pytest.mark.unit
    def test_replicate_json_serialization(self, sample_replicate):
        """Test serializing Replicate to JSON."""
        json_str = sample_replicate.model_dump_json()
        assert '"well_row":"A"' in json_str
        assert '"well_column":"1"' in json_str
        assert '"well_name":"A1"' in json_str

    @pytest.mark.unit
    def test_replicate_from_dict(self):
        """Test creating Replicate from dict."""
        data = {
            "well_row": "C",
            "well_column": "5",
            "well_name": "C5",
        }
        replicate = Replicate(**data)

        assert replicate.well_row == "C"
        assert replicate.well_column == "5"
        assert replicate.well_name == "C5"

    @pytest.mark.unit
    def test_replicate_equality(self):
        """Test that two Replicates with same data are equal."""
        rep1 = Replicate(well_row="A", well_column="1", well_name="A1")
        rep2 = Replicate(well_row="A", well_column="1", well_name="A1")
        assert rep1 == rep2

    @pytest.mark.unit
    def test_replicate_inequality(self):
        """Test that Replicates with different data are not equal."""
        rep1 = Replicate(well_row="A", well_column="1", well_name="A1")
        rep2 = Replicate(well_row="B", well_column="2", well_name="B2")
        assert rep1 != rep2

    @pytest.mark.unit
    def test_replicate_missing_field_raises_error(self):
        """Test that missing required field raises ValidationError."""
        with pytest.raises(ValidationError):
            Replicate(well_row="A", well_column="1")  # Missing well_name

    @pytest.mark.unit
    def test_replicate_extra_field_ignored(self):
        """Test that extra fields are ignored (Pydantic default behavior)."""
        replicate = Replicate(
            well_row="A",
            well_column="1",
            well_name="A1",
            extra_field="should_be_ignored",
        )
        assert replicate.well_row == "A"
        # extra_field should not be accessible
        assert not hasattr(replicate, "extra_field")

    @pytest.mark.unit
    def test_replicate_type_validation(self):
        """Test that Pydantic validates type requirements (v2 is stricter)."""
        # Pydantic v2 requires correct types, doesn't auto-coerce int to str
        with pytest.raises(ValidationError):
            Replicate(well_row="A", well_column=1, well_name="A1")

        # Correct usage with string
        replicate = Replicate(well_row="A", well_column="1", well_name="A1")
        assert replicate.well_column == "1"
        assert isinstance(replicate.well_column, str)


class TestUniqueCondition:
    """Tests for the UniqueCondition model."""

    @pytest.mark.unit
    def test_create_unique_condition(self, sample_condition):
        """Test creating a valid UniqueCondition."""
        assert sample_condition.full_name == "500uM_ATP_Protein1_Buffer1"
        assert sample_condition.concentration == "500uM"
        assert sample_condition.ligand_name == "ATP"
        assert sample_condition.protein_name == "Protein1"
        assert sample_condition.buffer_condition == "Buffer1"
        assert len(sample_condition.replicates) == 2

    @pytest.mark.unit
    def test_unique_condition_with_no_replicates(self):
        """Test creating UniqueCondition with empty replicates list."""
        condition = UniqueCondition(
            full_name="500uM_ATP_Protein1_Buffer1",
            concentration="500uM",
            ligand_name="ATP",
            protein_name="Protein1",
            buffer_condition="Buffer1",
            replicates=[],
        )
        assert condition.replicates == []

    @pytest.mark.unit
    def test_unique_condition_default_values(self):
        """Test that UniqueCondition has appropriate default values."""
        condition = UniqueCondition(
            full_name="test",
            concentration="500uM",
            ligand_name="ATP",
            protein_name="Protein1",
            buffer_condition="Buffer1",
        )
        assert condition.replicates == []

    @pytest.mark.unit
    def test_unique_condition_serialization(self, sample_condition):
        """Test serializing UniqueCondition to dict."""
        data = sample_condition.model_dump()

        assert data["full_name"] == "500uM_ATP_Protein1_Buffer1"
        assert data["concentration"] == "500uM"
        assert data["ligand_name"] == "ATP"
        assert data["protein_name"] == "Protein1"
        assert data["buffer_condition"] == "Buffer1"
        assert len(data["replicates"]) == 2
        assert isinstance(data["replicates"][0], dict)

    @pytest.mark.unit
    def test_unique_condition_json_serialization(self, sample_condition):
        """Test serializing UniqueCondition to JSON."""
        json_str = sample_condition.model_dump_json()
        assert "500uM_ATP_Protein1_Buffer1" in json_str
        assert '"concentration":"500uM"' in json_str
        assert '"ligand_name":"ATP"' in json_str

    @pytest.mark.unit
    def test_unique_condition_from_dict(self):
        """Test creating UniqueCondition from dict."""
        data = {
            "full_name": "1mM_GTP_Protein2_Buffer2",
            "concentration": "1mM",
            "ligand_name": "GTP",
            "protein_name": "Protein2",
            "buffer_condition": "Buffer2",
            "replicates": [
                {"well_row": "B", "well_column": "1", "well_name": "B1"},
            ],
        }
        condition = UniqueCondition(**data)

        assert condition.ligand_name == "GTP"
        assert len(condition.replicates) == 1
        assert isinstance(condition.replicates[0], Replicate)

    @pytest.mark.unit
    def test_unique_condition_nested_validation(self):
        """Test that nested Replicate objects are validated."""
        with pytest.raises(ValidationError):
            UniqueCondition(
                full_name="test",
                concentration="500uM",
                ligand_name="ATP",
                protein_name="Protein1",
                buffer_condition="Buffer1",
                replicates=[
                    {"well_row": "A", "well_column": "1"}  # Missing well_name
                ],
            )

    @pytest.mark.unit
    def test_unique_condition_with_defaults(self):
        """Test that UniqueCondition allows missing fields (all have defaults)."""
        # All fields have defaults, so missing fields use empty strings
        condition = UniqueCondition(
            full_name="test",
            concentration="500uM",
            ligand_name="ATP",
            # protein_name not provided - will use default ""
            buffer_condition="Buffer1",
        )
        assert condition.protein_name == ""  # Default value

    @pytest.mark.unit
    def test_unique_condition_equality(self):
        """Test that two UniqueConditions with same data are equal."""
        cond1 = UniqueCondition(
            full_name="500uM_ATP_Protein1_Buffer1",
            concentration="500uM",
            ligand_name="ATP",
            protein_name="Protein1",
            buffer_condition="Buffer1",
            replicates=[],
        )
        cond2 = UniqueCondition(
            full_name="500uM_ATP_Protein1_Buffer1",
            concentration="500uM",
            ligand_name="ATP",
            protein_name="Protein1",
            buffer_condition="Buffer1",
            replicates=[],
        )
        assert cond1 == cond2

    @pytest.mark.unit
    def test_unique_condition_with_complex_names(self):
        """Test UniqueCondition with complex names containing hyphens."""
        condition = UniqueCondition(
            full_name="500uM_Geranyl-Monophosphate_d104hFic-H363A_1mM-ATP-5mM-MgCl2",
            concentration="500uM",
            ligand_name="Geranyl-Monophosphate",
            protein_name="d104hFic-H363A",
            buffer_condition="1mM-ATP-5mM-MgCl2",
        )
        assert condition.ligand_name == "Geranyl-Monophosphate"
        assert condition.protein_name == "d104hFic-H363A"
        assert condition.buffer_condition == "1mM-ATP-5mM-MgCl2"

    @pytest.mark.unit
    def test_add_replicate_to_condition(self, sample_condition):
        """Test adding a new replicate to an existing condition."""
        initial_count = len(sample_condition.replicates)
        new_replicate = Replicate(well_row="A", well_column="3", well_name="A3")

        sample_condition.replicates.append(new_replicate)

        assert len(sample_condition.replicates) == initial_count + 1
        assert sample_condition.replicates[-1] == new_replicate

    @pytest.mark.unit
    def test_unique_condition_immutable_after_validation(self):
        """Test that validated UniqueCondition can be modified (Pydantic v2 is mutable by default)."""
        condition = UniqueCondition(
            full_name="test",
            concentration="500uM",
            ligand_name="ATP",
            protein_name="Protein1",
            buffer_condition="Buffer1",
        )

        # In Pydantic v2, models are mutable by default
        condition.concentration = "1mM"
        assert condition.concentration == "1mM"


class TestModelIntegration:
    """Integration tests for data models working together."""

    @pytest.mark.unit
    def test_condition_with_multiple_replicates(self):
        """Test condition with multiple replicates."""
        replicates = [
            Replicate(well_row="A", well_column="1", well_name="A1"),
            Replicate(well_row="A", well_column="2", well_name="A2"),
            Replicate(well_row="A", well_column="3", well_name="A3"),
        ]

        condition = UniqueCondition(
            full_name="500uM_ATP_Protein1_Buffer1",
            concentration="500uM",
            ligand_name="ATP",
            protein_name="Protein1",
            buffer_condition="Buffer1",
            replicates=replicates,
        )

        assert len(condition.replicates) == 3
        assert all(isinstance(rep, Replicate) for rep in condition.replicates)

    @pytest.mark.unit
    def test_round_trip_serialization(self, sample_condition):
        """Test that serialization and deserialization preserves data."""
        # Serialize to dict
        data = sample_condition.model_dump()

        # Deserialize back to object
        reconstructed = UniqueCondition(**data)

        assert reconstructed == sample_condition
        assert reconstructed.model_dump() == data

    @pytest.mark.unit
    def test_json_round_trip(self, sample_condition):
        """Test that JSON serialization round-trip preserves data."""
        # Serialize to JSON
        json_str = sample_condition.model_dump_json()

        # Deserialize from JSON
        reconstructed = UniqueCondition.model_validate_json(json_str)

        assert reconstructed.full_name == sample_condition.full_name
        assert reconstructed.concentration == sample_condition.concentration
        assert len(reconstructed.replicates) == len(sample_condition.replicates)

    @pytest.mark.unit
    def test_conditions_dict_structure(self, sample_conditions_dict):
        """Test working with dictionary of conditions."""
        assert len(sample_conditions_dict) == 2

        atp_condition = sample_conditions_dict["500uM_ATP_Protein1_Buffer1"]
        assert atp_condition.ligand_name == "ATP"
        assert len(atp_condition.replicates) == 2

        gtp_condition = sample_conditions_dict["1mM_GTP_Protein2_Buffer2"]
        assert gtp_condition.ligand_name == "GTP"
        assert len(gtp_condition.replicates) == 2


class TestEdgeCases:
    """Tests for edge cases in data models."""

    @pytest.mark.unit
    def test_empty_strings_in_condition(self):
        """Test that empty strings in required fields are accepted (validation at application level)."""
        # Pydantic will accept empty strings unless we add custom validators
        condition = UniqueCondition(
            full_name="",
            concentration="",
            ligand_name="",
            protein_name="",
            buffer_condition="",
        )
        assert condition.full_name == ""

    @pytest.mark.unit
    def test_very_long_field_values(self):
        """Test handling of very long field values."""
        long_name = "A" * 1000
        condition = UniqueCondition(
            full_name=long_name,
            concentration="500uM",
            ligand_name="ATP",
            protein_name="Protein1",
            buffer_condition="Buffer1",
        )
        assert len(condition.full_name) == 1000

    @pytest.mark.unit
    def test_special_characters_in_fields(self):
        """Test handling of special characters."""
        condition = UniqueCondition(
            full_name="500uM_ATP-γ-S_Protein1_Buffer1",
            concentration="500uM",
            ligand_name="ATP-γ-S",
            protein_name="Protein1",
            buffer_condition="Buffer1",
        )
        assert "γ" in condition.ligand_name

    @pytest.mark.unit
    def test_numeric_strings_in_fields(self):
        """Test handling of purely numeric strings."""
        condition = UniqueCondition(
            full_name="500_1000_2000_3000",
            concentration="500",
            ligand_name="1000",
            protein_name="2000",
            buffer_condition="3000",
        )
        assert condition.concentration == "500"
        assert condition.ligand_name == "1000"
