"""
Dash callbacks — coordinator module.
"""

from ._experiment import register_experiment_callbacks
from ._figures import register_figure_callbacks
from ._pipeline import register_pipeline_callbacks
from ._session import register_session_callbacks
from ._upload import register_upload_callbacks
from ._validation import register_validation_callbacks
from ._well_filter import register_well_filter_callbacks


def register_callbacks(app):
    """Register all callbacks for the app."""
    cache = app.cache
    register_session_callbacks(app, cache)
    register_experiment_callbacks(app, cache)
    register_upload_callbacks(app, cache)
    register_well_filter_callbacks(app, cache)
    register_validation_callbacks(app, cache)
    register_pipeline_callbacks(app, cache)
    register_figure_callbacks(app, cache)
