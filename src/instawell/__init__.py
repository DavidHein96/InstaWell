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

# Define what `from elephant import *` imports, though explicit imports are better.
__all__ = [
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
]

__version__ = "0.1.0"
