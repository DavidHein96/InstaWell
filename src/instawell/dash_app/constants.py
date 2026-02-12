"""
Constants for the InstaWell Dash app.
"""

from instawell import StepFiles

# Button ID -> figure type mapping
FIGURE_BUTTON_MAP = {
    "fig-btn-raw": "raw",
    "fig-btn-averaged": "averaged",
    "fig-btn-bgsub": "bgsub",
    "fig-btn-minmax": "minmax",
    "fig-btn-deriv": "derivative",
    "fig-btn-tm": "tm",
}

# Figure type -> StepFiles enum mapping
FIGURE_STEP_FILES = {
    "raw": StepFiles.INGESTED_DATA,
    "averaged": StepFiles.AVERAGED_DATA,
    "bgsub": StepFiles.BG_SUB_DATA,
    "minmax": StepFiles.MIN_MAX_SCALED_DATA,
    "derivative": StepFiles.DERIVATIVE_DATA,
    "tm": StepFiles.MIN_TEMPERATURES_DATA,
}

# Pipeline step -> FontAwesome icon class
STEP_ICONS = {
    "ingest": "fa-inbox",
    "filter": "fa-filter",
    "average": "fa-compress",
    "complete": "fa-check-circle",
}

# Default parsing settings
DEFAULT_SEPARATOR = "|"
DEFAULT_PLACEHOLDER = "^"
DEFAULT_NPC_MARKER = "NPC"
DEFAULT_TEMPERATURE_COLUMN = "Temperature"

# Cache key format
CACHE_KEY_FORMAT = "{session_id}_{filename}"
