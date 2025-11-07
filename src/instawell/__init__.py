"""
InstaWell: A powerful toolkit for analyzing Differential Scanning Fluorimetry (DSF) data.

This package provides a complete pipeline for processing thermal shift assay experiments,
from raw data ingestion through melting temperature identification.

Basic Usage:
    >>> from instawell import setup_experiment, ingest_data, filter_wells
    >>>
    >>> # Setup experiment
    >>> ctx = setup_experiment(
    ...     experiment_name="my_experiment",
    ...     raw_data_path="raw.csv",
    ...     layout_data_path="layout.csv"
    ... )
    >>>
    >>> # Process data
    >>> ingest_data(ctx)
    >>> filter_wells(ctx, wells_to_filter=["A1"])
    >>> # ... continue pipeline

Pipeline Steps (in order):
    1. setup_experiment() - Initialize experiment directory and context
    2. ingest_data() - Parse layout and organize raw data
    3. filter_wells() - Remove problematic wells
    4. average_accross_replicates() - Average technical replicates
    5. subtract_background() - Remove background signal (NPC controls)
    6. min_max_scale() - Normalize to 0-1 range
    7. calculate_derivative() - Compute -dY/dT for Tm identification
    8. find_min_temperature() - Extract melting temperatures
"""

import logging

logging.getLogger(__name__).addHandler(logging.NullHandler())

# Core context and configuration
# Data models
from .core.data_models import Replicate, UniqueCondition
from .core.exp_context import ExperimentContext

# Parsing utilities
from .core.parser import (
    condition_from_string,
    condition_to_string,
    parse_concentration_to_float,
    parse_condition_string,
    validate_condition_string,
)
from .core.steps import StepFiles

# Figures
from .figures.fig_01_raw import raw_figure_generator
from .figures.fig_02_averaged import averaged_figure_generator
from .figures.fig_03_bgsub_raw import bgsub_figure_generator
from .figures.fig_04_bgsub_minmax import bgsub_minmax_figure_generator
from .figures.fig_05_derivative import derivative_figure_generator
from .figures.fig_06_min_temp import min_temp_figure_generator

# Processing pipeline steps
from .processing.step_00_setup_experiment import (
    load_experiment_context,
    setup_experiment,
)
from .processing.step_01_ingest_data import ingest_data
from .processing.step_02_filter_wells import filter_wells
from .processing.step_03_average_replicates import average_accross_replicates
from .processing.step_04_subtract_background import subtract_background
from .processing.step_05_minmax_scale import min_max_scale
from .processing.step_06_calc_derivative import calculate_derivative
from .processing.step_07_find_min_temp import find_min_temperature

# Utility functions
from .utils.utils import split_unqcon_column

__all__ = [
    # ===== Experiment Setup =====
    "setup_experiment",
    "load_experiment_context",
    "ExperimentContext",
    "StepFiles",
    # ===== Processing Pipeline =====
    "ingest_data",
    "filter_wells",
    "average_accross_replicates",
    "subtract_background",
    "min_max_scale",
    "calculate_derivative",
    "find_min_temperature",
    # ===== Data Models =====
    "Replicate",
    "UniqueCondition",
    # ===== Parsing Utilities =====
    "condition_from_string",
    "condition_to_string",
    "parse_condition_string",
    "parse_concentration_to_float",
    "validate_condition_string",
    # ===== Utilities =====
    "split_unqcon_column",
    # ===== Figure Generators =====
    "raw_figure_generator",
    "averaged_figure_generator",
    "bgsub_figure_generator",
    "bgsub_minmax_figure_generator",
    "derivative_figure_generator",
    "min_temp_figure_generator",
]

__version__ = "0.2.0"  # Bumped for new API
