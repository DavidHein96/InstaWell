"""
InstaWell: A powerful toolkit for analyzing Thermal Shift Assay data

This package provides a complete pipeline for processing thermal shift assay experiments,
from raw data ingestion through melting temperature identification. It is designed to be
highly friendly for Jupyter Notebook users, with interactive figure widgets and easy-to-use
functions.

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
    4. average_across_replicates() - Average technical replicates
    5. subtract_background() - Remove background signal (NPC controls)
    6. min_max_scale() - Normalize to 0-1 range
    7. calculate_derivative() - Compute -dY/dT for Tm identification
    8. find_min_temperature() - Extract melting temperatures
    9. calculate_curve_params() - Fit dose-response curves to Tm data

Figures:
    - The figures are set up to work really well in Jupyter Notebooks.
    - The base generators return iterators of Plotly figures for easy display or saving.
        - raw_figure_generator() - Visualize raw data for each well
        - processed_figure_generator() - Visualize processed data at each step (groups replicates)
        - min_temp_figure_generator() - Visualize melting temperatures across conditions and show 4PL fits
    - When working in notebooks, use the widget helpers to get interactive figure browsers.
        - raw_figures_widget() - Interactive browser for raw data figures
        - processed_figures_widget() - Interactive browser for processed data figures
        - min_temp_figures_widget() - Interactive browser for melting temperature figures
"""

import logging
from importlib.metadata import PackageNotFoundError, version

logging.getLogger(__name__).addHandler(logging.NullHandler())
from .core.exp_context import ExperimentContext
from .core.steps import StepFiles
from .figures.notebook_helpers import (
    min_temp_figures_widget,
    processed_figures_widget,
    raw_figures_widget,
)
from .processing.step_00_setup_experiment import (
    load_experiment_context,
    setup_experiment,
)
from .processing.step_01_ingest_data import ingest_data
from .processing.step_02_filter_wells import filter_wells
from .processing.step_03_average_replicates import average_across_replicates
from .processing.step_04_subtract_background import subtract_background
from .processing.step_05_minmax_scale import min_max_scale
from .processing.step_06_calc_derivative import calculate_derivative
from .processing.step_07_find_min_temp import find_min_temperature
from .processing.step_08_calc_curves import calculate_curve_params

__all__ = [
    # ===== Experiment Setup =====
    "ExperimentContext",
    "setup_experiment",
    "load_experiment_context",
    # ===== Data Processing Steps =====
    "ingest_data",
    "filter_wells",
    "average_across_replicates",
    "subtract_background",
    "min_max_scale",
    "calculate_derivative",
    "find_min_temperature",
    "calculate_curve_params",
    # ===== Figure Widgets =====
    "raw_figures_widget",
    "processed_figures_widget",
    "min_temp_figures_widget",
    "StepFiles",
]

try:
    __version__ = version("instawell")
except PackageNotFoundError:
    # Fallback for dev environments where the package isn't installed yet
    __version__ = "0.0.0+dev"
