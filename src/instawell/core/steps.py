from enum import Enum


class StepFiles(str, Enum):
    """Standard filenames for data files at each processing step."""

    # main data files
    INGESTED_DATA = "01_raw_organized_data.csv"
    FILTERED_DATA = "02_filtered_organized_data.csv"
    AVERAGED_DATA = "03_averaged_data.csv"
    BG_SUB_DATA = "04_bg_subtracted_data.csv"
    MIN_MAX_SCALED_DATA = "05_min_max_scaled_data.csv"
    DERIVATIVE_DATA = "06_derivative_data.csv"
    MIN_TEMPERATURES_DATA = "07_min_temperatures.csv"
    CURVE_PARAMS = "08_curve_params.csv"
    CURVE_DIAGNOSTICS = "08_curve_diagnostics.csv"

    # long format data files
    AVERAGED_DATA_LONG = "03_averaged_data_long.csv"
    BG_SUB_DATA_LONG = "04_bg_subtracted_data_long.csv"
    MIN_MAX_SCALED_DATA_LONG = "05_min_max_scaled_data_long.csv"
    DERIVATIVE_DATA_LONG = "06_derivative_data_long.csv"

    # aux files
    EXPERIMENT_CONTEXT = "experiment.json"
    FILTERED_WELLS = "filtered_wells.txt"
    UNIQUE_CONDITIONS = "unique_conditions.json"
    EXPERIMENT_LOG = "experiment.log"

    # Plot folders
    PLOTS_DIR = "plots"
    RAW_PLOTS = "01_raw_plots"
    FILTERED_PLOTS = "02_filtered_plots"
    AVERAGED_PLOTS = "03_averaged_plots"
    BG_SUB_PLOTS = "04_bg_subtracted_plots"
    MIN_MAX_SCALED_PLOTS = "05_min_max_scaled_plots"
    DERIVATIVE_PLOTS = "06_derivative_plots"
    MIN_TEMPERATURES_PLOTS = "07_min_temperatures_plots"
    MIN_TEMPERATURES_WITH_CURVES_PLOTS = "08_min_temperatures_with_curves_plots"
