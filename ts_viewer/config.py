# ts_viewer/config.py
from pathlib import Path

import dash_bootstrap_components as dbc
import plotly.io as pio

TITLE = "Thermal Shift Viewer"
PORT = 8056
THEME = dbc.themes.ZEPHYR
pio.templates.default = "plotly_white"

LAYOUT_CSV_PATH = Path("layout_real.csv")
RAW_READINGS_CSV_PATH = Path("raw_data_real2.csv")

# NEW: where uploaded datasets live (mounted volume in Docker if you like)
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
