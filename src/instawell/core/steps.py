from enum import Enum


class StepFiles(str, Enum):
    INGESTED_DATA = "01_raw_organized_data.csv"
    FILTERED_DATA = "02_filtered_organized_data.csv"
    AVERAGED_DATA = "03_averaged_data.csv"
    BG_SUB_DATA = "04_bg_subtracted_data.csv"
    MIN_MAX_SCALED_DATA = "05_min_max_scaled_data.csv"
    DERIVATIVE_DATA = "06_derivative_data.csv"
    MIN_TEMPERATURES_DATA = "07_min_temperatures.csv"
    FILTERED_WELLS = "filtered_wells.txt"
