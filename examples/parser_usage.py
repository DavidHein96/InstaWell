"""
Example usage of the new parser module.

This demonstrates how to use the robust condition string parser
instead of the old brittle split("_") approach.
"""

from instawell import (
    condition_from_string,
    condition_to_string,
    parse_condition_string,
    parse_concentration_to_float,
    validate_condition_string,
)


def main():
    print("=" * 60)
    print("InstaWell Parser Examples")
    print("=" * 60)

    # Example 1: Parse a simple condition string
    print("\n1. Parsing a simple condition string:")
    simple = "500uM_ATP_Protein1_Buffer1"
    parsed = parse_condition_string(simple)
    print(f"   Input:  {simple}")
    print(f"   Output: {parsed}")

    # Example 2: Parse a complex condition string (with underscores in components)
    print("\n2. Parsing a complex condition string:")
    complex_str = "500uM_Geranyl-Monophosphate_d104hFic-H363A_1mM-ATP-5mM-MgCl2"
    parsed_complex = parse_condition_string(complex_str)
    print(f"   Input:  {complex_str}")
    print(f"   Output: {parsed_complex}")

    # Example 3: Create a UniqueCondition object
    print("\n3. Creating a UniqueCondition object:")
    condition = condition_from_string(complex_str)
    print(f"   Concentration: {condition.concentration}")
    print(f"   Ligand:        {condition.ligand_name}")
    print(f"   Protein:       {condition.protein_name}")
    print(f"   Buffer:        {condition.buffer_condition}")
    print(f"   Full name:     {condition.full_name}")

    # Example 4: Reconstruct condition string
    print("\n4. Reconstructing condition string:")
    reconstructed = condition_to_string(condition)
    print(f"   Original:      {complex_str}")
    print(f"   Reconstructed: {reconstructed}")
    print(f"   Match:         {complex_str == reconstructed}")

    # Example 5: Validate condition strings
    print("\n5. Validating condition strings:")
    test_cases = [
        "500uM_ATP_Protein1_Buffer1",  # Valid
        "invalid",  # Invalid - not enough fields
        "0_0_0_0",  # Valid format (even if semantically empty)
        "a_b_c",  # Invalid - only 3 fields
    ]
    for test in test_cases:
        is_valid = validate_condition_string(test)
        print(f"   '{test}' -> {is_valid}")

    # Example 6: Parse concentration values
    print("\n6. Parsing concentration values to floats:")
    concentrations = ["500uM", "1mM", "0.5nM", "apo", "DMSO", "100uM"]
    for conc in concentrations:
        float_val = parse_concentration_to_float(conc)
        print(f"   '{conc}' -> {float_val}")

    # Example 7: Error handling
    print("\n7. Error handling:")
    try:
        invalid = "not_enough_fields"
        parsed = parse_condition_string(invalid)
    except ValueError as e:
        print(f"   Caught error: {e}")

    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
