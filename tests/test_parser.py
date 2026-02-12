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
