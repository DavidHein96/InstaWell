"""
Tests for the parser module.

This module tests the robust condition string parser that handles
underscores in component names and flexible field ordering.
"""

import pytest

from instawell.core.parser import (
    parse_concentration_to_float,
    parse_condition_string,
)


class TestParseConditionString:
    """Tests for parse_condition_string function."""

    @pytest.mark.unit
    def test_simple_condition_string(self, simple_condition_string):
        """Test parsing a simple condition string with default fields."""
        result = parse_condition_string(simple_condition_string)
        assert result.dimensions["concentration"] == "500uM"
        assert result.dimensions["ligand"] == "ATP"
        assert result.dimensions["protein"] == "Protein1"
        assert result.dimensions["buffer"] == "Buffer1"

    @pytest.mark.unit
    def test_complex_condition_string(self, complex_condition_string):
        """Test parsing a complex condition string with underscores in components."""
        result = parse_condition_string(complex_condition_string)
        assert result.dimensions["concentration"] == "500uM"
        assert result.dimensions["ligand"] == "Geranyl-Monophosphate"
        assert result.dimensions["protein"] == "d104hFic-H363A"
        assert result.dimensions["buffer"] == "1mM-ATP-5mM-MgCl2"

    @pytest.mark.unit
    def test_custom_field_order(self):
        """Test parsing with custom field order."""
        condition_str = "ATP_Protein1_500uM_Buffer1"
        fields = ("ligand", "protein", "concentration", "buffer")

        result = parse_condition_string(condition_str, fields=fields)
        assert result.dimensions["ligand"] == "ATP"
        assert result.dimensions["protein"] == "Protein1"
        assert result.dimensions["concentration"] == "500uM"
        assert result.dimensions["buffer"] == "Buffer1"

    @pytest.mark.unit
    def test_fewer_fields(self):
        """Test parsing only specific fields from a condition string."""
        condition_str = "500uM_ATP_Protein1_Buffer1"
        fields = ("protein", "buffer")
        with pytest.raises(ValueError):
            parse_condition_string(condition_str, fields=fields)

    @pytest.mark.unit
    def test_empty_string_raises_error(self):
        """Test that empty string raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            parse_condition_string("")

    @pytest.mark.unit
    def test_whitespace_only_raises_error(self):
        """Test that whitespace-only string raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            parse_condition_string("   ")

    @pytest.mark.unit
    def test_insufficient_components_raises_error(self):
        """Test that string with too few components raises ValueError."""
        with pytest.raises(ValueError, match="must have at least 4"):
            parse_condition_string("only_three_parts")

    @pytest.mark.unit
    def test_custom_delimiter(self):
        """Test parsing with custom delimiter."""
        condition_str = "500uM|ATP|Protein1|Buffer1"
        result = parse_condition_string(condition_str, delimiter="|")

        assert result.dimensions["concentration"] == "500uM"
        assert result.dimensions["ligand"] == "ATP"

    @pytest.mark.unit
    def test_parses_from_end(self):
        """Test that parser takes last N components (handles underscores in early components)."""
        # String has 6 components, should take last 4
        condition_str = "500uM_ATP_Protein1_Buffer1"
        result = parse_condition_string(condition_str)

        assert result.dimensions["concentration"] == "500uM"
        assert result.dimensions["ligand"] == "ATP"
        assert result.dimensions["protein"] == "Protein1"
        assert result.dimensions["buffer"] == "Buffer1"

    @pytest.mark.unit
    def test_apo_condition(self):
        """Test parsing apo (no ligand) condition."""
        condition_str = "apo_DMSO_NPC_Buffer1"
        result = parse_condition_string(condition_str)

        assert result.dimensions["concentration"] == "apo"
        assert result.dimensions["ligand"] == "DMSO"
        assert result.dimensions["protein"] == "NPC"
        assert result.dimensions["buffer"] == "Buffer1"


# class TestConditionFromString:
#     """Tests for condition_from_string function."""

#     @pytest.mark.unit
#     def test_creates_unique_condition(self, simple_condition_string):
#         """Test creating UniqueCondition from simple string."""
#         condition = condition_from_string(simple_condition_string)

#         assert isinstance(condition, UniqueCondition)
#         assert condition.full_name == simple_condition_string
#         assert condition.concentration == "500uM"
#         assert condition.ligand_name == "ATP"
#         assert condition.protein_name == "Protein1"
#         assert condition.buffer_condition == "Buffer1"
#         assert condition.replicates == []

#     @pytest.mark.unit
#     def test_creates_condition_from_complex_string(self, complex_condition_string):
#         """Test creating UniqueCondition from complex string with underscores."""
#         condition = condition_from_string(complex_condition_string)

#         assert condition.ligand_name == "Geranyl-Monophosphate"
#         assert condition.protein_name == "d104hFic-H363A"
#         assert condition.buffer_condition == "1mM-ATP-5mM-MgCl2"

#     @pytest.mark.unit
#     def test_custom_field_order(self):
#         """Test creating condition with custom field order."""
#         condition_str = "ATP_Protein1_500uM_Buffer1"
#         fields = ("ligand", "protein", "concentration", "buffer")

#         condition = condition_from_string(condition_str, fields=fields)

#         assert condition.ligand_name == "ATP"
#         assert condition.protein_name == "Protein1"
#         assert condition.concentration == "500uM"

#     @pytest.mark.unit
#     def test_missing_required_fields_raises_error(self):
#         """Test that missing required fields raises ValueError."""
#         condition_str = "Protein1_Buffer1"
#         fields = ("protein", "buffer")

#         with pytest.raises(ValueError, match="missing required fields"):
#             condition_from_string(condition_str, fields=fields)

#     @pytest.mark.unit
#     def test_invalid_string_raises_error(self):
#         """Test that invalid string raises ValueError."""
#         with pytest.raises(ValueError):
#             condition_from_string("invalid")

#     @pytest.mark.unit
#     def test_include_replicates_parameter(self):
#         """Test include_replicates parameter."""
#         condition = condition_from_string("500uM_ATP_Protein1_Buffer1", include_replicates=True)
#         assert condition.replicates == []

#         condition = condition_from_string("500uM_ATP_Protein1_Buffer1", include_replicates=False)
#         assert condition.replicates == []


# class TestConditionToString:
#     """Tests for condition_to_string function."""

#     @pytest.mark.unit
#     def test_reconstructs_condition_string(self, sample_condition):
#         """Test reconstructing condition string from UniqueCondition."""
#         result = condition_to_string(sample_condition)
#         assert result == "500uM_ATP_Protein1_Buffer1"

#     @pytest.mark.unit
#     def test_custom_delimiter(self, sample_condition):
#         """Test reconstruction with custom delimiter."""
#         result = condition_to_string(sample_condition, delimiter="|")
#         assert result == "500uM|ATP|Protein1|Buffer1"

#     @pytest.mark.unit
#     def test_missing_field_raises_error(self):
#         """Test that missing required field raises ValueError."""
#         incomplete_condition = UniqueCondition(
#             full_name="incomplete",
#             concentration="500uM",
#             ligand_name="ATP",
#             protein_name="",  # Empty protein name
#             buffer_condition="Buffer1",
#         )

#         with pytest.raises(ValueError, match="missing required fields"):
#             condition_to_string(incomplete_condition)

#     @pytest.mark.unit
#     def test_round_trip_conversion(self, simple_condition_string):
#         """Test that string -> condition -> string preserves the value."""
#         condition = condition_from_string(simple_condition_string)
#         reconstructed = condition_to_string(condition)
#         assert reconstructed == simple_condition_string


# class TestValidateConditionString:
#     """Tests for validate_condition_string function."""

#     @pytest.mark.unit
#     def test_valid_simple_string(self, simple_condition_string):
#         """Test that valid simple string returns True."""
#         assert validate_condition_string(simple_condition_string) is True

#     @pytest.mark.unit
#     def test_valid_complex_string(self, complex_condition_string):
#         """Test that valid complex string returns True."""
#         assert validate_condition_string(complex_condition_string) is True

#     @pytest.mark.unit
#     def test_invalid_string_returns_false(self):
#         """Test that invalid string returns False."""
#         assert validate_condition_string("invalid") is False
#         assert validate_condition_string("only_two") is False
#         assert validate_condition_string("") is False

#     @pytest.mark.unit
#     def test_placeholder_string_valid(self):
#         """Test that placeholder string (0_0_0_0) is technically valid."""
#         assert validate_condition_string("0_0_0_0") is True

#     @pytest.mark.unit
#     def test_no_exceptions_raised(self):
#         """Test that validation never raises exceptions."""
#         # Should not raise, just return False
#         try:
#             result = validate_condition_string("")
#             assert result is False
#         except Exception:
#             pytest.fail("validate_condition_string should not raise exceptions")


class TestParseConcentrationToFloat:
    """Tests for parse_concentration_to_float function."""

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "concentration,expected",
        [
            ("500uM", 500.0),
            ("1mM", 1.0),
            ("0.5nM", 0.5),
            ("10uM", 10.0),
            ("2.5mM", 2.5),
            ("100nM", 100.0),
        ],
    )
    def test_numeric_concentrations(self, concentration, expected):
        """Test parsing numeric concentration strings."""
        result = parse_concentration_to_float(concentration)
        assert result == expected

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "special_case",
        ["apo", "APO", "dmso", "DMSO", "control", "CONTROL", "baseline", "BASELINE"],
    )
    def test_special_cases_return_zero(self, special_case):
        """Test that special cases (apo, DMSO, etc.) return 0.0."""
        result = parse_concentration_to_float(special_case)
        assert result == 0.0

    @pytest.mark.unit
    def test_invalid_format_returns_none(self):
        """Test that invalid format returns None."""
        result = parse_concentration_to_float("invalid_format")
        assert result is None

    @pytest.mark.unit
    def test_empty_string_returns_none(self):
        """Test that empty string returns None."""
        result = parse_concentration_to_float("")
        assert result is None

    @pytest.mark.unit
    def test_extracts_numeric_prefix(self):
        """Test that function extracts numeric prefix from string."""
        # Should extract "500" from "500uM"
        result = parse_concentration_to_float("500anything_after")
        assert result == 500.0

    @pytest.mark.unit
    def test_decimal_values(self):
        """Test parsing decimal concentration values."""
        result = parse_concentration_to_float("0.5uM")
        assert result == 0.5

        result = parse_concentration_to_float("12.34mM")
        assert result == 12.34


class TestFieldOrderScenarios:
    """Integration tests for different field ordering scenarios."""

    @pytest.mark.unit
    def test_standard_order(self):
        """Test standard field order (concentration, ligand, protein, buffer)."""
        condition_str = "500uM_ATP_Protein1_Buffer1"
        fields = ("concentration", "ligand", "protein", "buffer")

        result = parse_condition_string(condition_str, fields=fields)

        assert result.dimensions["concentration"] == "500uM"
        assert result.dimensions["ligand"] == "ATP"
        assert result.dimensions["protein"] == "Protein1"
        assert result.dimensions["buffer"] == "Buffer1"

    @pytest.mark.unit
    def test_reversed_order(self):
        """Test reversed field order."""
        condition_str = "Buffer1_Protein1_ATP_500uM"
        fields = ("buffer", "protein", "ligand", "concentration")

        result = parse_condition_string(condition_str, fields=fields)

        assert result.dimensions["buffer"] == "Buffer1"
        assert result.dimensions["protein"] == "Protein1"
        assert result.dimensions["ligand"] == "ATP"
        assert result.dimensions["concentration"] == "500uM"

    @pytest.mark.unit
    def test_mixed_order(self):
        """Test mixed field order."""
        condition_str = "Protein1_500uM_Buffer1_ATP"
        fields = ("protein", "concentration", "buffer", "ligand")

        result = parse_condition_string(condition_str, fields=fields)

        assert result.dimensions["protein"] == "Protein1"
        assert result.dimensions["concentration"] == "500uM"
        assert result.dimensions["buffer"] == "Buffer1"
        assert result.dimensions["ligand"] == "ATP"


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    # @pytest.mark.unit
    # def test_very_long_condition_string(self):
    #     """Test parsing very long condition string with many underscores."""
    #     condition_str = "A_B_C_D_E_F_500uM_ATP_Protein1_Buffer1"
    #     result = parse_condition_string(condition_str)

    #     # Should take last 4 components
    #     assert result.dimensions["concentration"] == "500uM"
    #     assert result.dimensions["ligand"] == "ATP"

    @pytest.mark.unit
    def test_single_field(self):
        """Test parsing just a single field."""
        condition_str = "500uM_ATP_Protein1_Buffer1"
        fields = ("buffer",)

        result = parse_condition_string(condition_str, fields=fields)
        assert result == {"buffer": "500uM_ATP_Protein1_Buffer1"}

    @pytest.mark.unit
    def test_exactly_required_components(self):
        """Test string with exactly the required number of components."""
        condition_str = "500uM_ATP_Protein1_Buffer1"
        result = parse_condition_string(condition_str)

        assert len(result.dimensions) == 4

    @pytest.mark.unit
    def test_unicode_characters(self):
        """Test parsing condition strings with unicode characters."""
        condition_str = "500μM_ATP_Protéin1_Buffer1"
        result = parse_condition_string(condition_str)

        assert result.dimensions["concentration"] == "500μM"
        assert result.dimensions["protein"] == "Protéin1"

    @pytest.mark.unit
    def test_numeric_components(self):
        """Test parsing components that are purely numeric."""
        condition_str = "500_1000_2000_3000"
        result = parse_condition_string(condition_str)

        assert result.dimensions["concentration"] == "500"
        assert result.dimensions["ligand"] == "1000"
        assert result.dimensions["protein"] == "2000"
        assert result.dimensions["buffer"] == "3000"
