# src/instawell/__init__.py

"""A helpful SDK for interacting with the InstaWell data analysis tools."""

from .main import (
    average_accross_replicates,
    calculate_derivative,
    create_averaged_figures_generator,
    create_bgsub_minmax_figures_generator,
    create_bgsubtracted_figures_generator,
    create_derivative_figures_generator,
    create_figures_generator,
    create_mintemp_figures_generator,
    filter_organized_data,
    find_min_temperature,
    first_step,
    min_max_scale,
    subtract_background,
)

# New data models and parsing utilities
from .data_models import (
    Replicate,
    UniqueCondition,
)

from .parser import (
    condition_from_string,
    condition_to_string,
    parse_condition_string,
    parse_concentration_to_float,
    validate_condition_string,
)

# Define what `from elephant import *` imports, though explicit imports are better.
__all__ = [
    # Main processing functions
    "average_accross_replicates",
    "calculate_derivative",
    "create_averaged_figures_generator",
    "create_bgsub_minmax_figures_generator",
    "create_bgsubtracted_figures_generator",
    "create_derivative_figures_generator",
    "create_figures_generator",
    "create_mintemp_figures_generator",
    "filter_organized_data",
    "find_min_temperature",
    "first_step",
    "min_max_scale",
    "subtract_background",
    # Data models
    "Replicate",
    "UniqueCondition",
    # Parsing utilities
    "condition_from_string",
    "condition_to_string",
    "parse_condition_string",
    "parse_concentration_to_float",
    "validate_condition_string",
]

__version__ = "0.1.0"
