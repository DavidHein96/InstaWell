"""
Upload handling callbacks.
"""

from dash import Input, Output, State

from ._helpers import _handle_upload


def register_upload_callbacks(app, cache):
    """Register file upload callbacks."""

    def _validate_raw(df):
        if "Temperature" not in df.columns:
            return "Error: Missing 'Temperature' column"
        return None

    def _validate_layout(df):
        if not any("well" in col.lower() for col in df.columns):
            return "Error: Missing well column"
        return None

    @app.callback(
        Output("raw-upload-status", "children", allow_duplicate=True),
        Output("raw-data-store", "data", allow_duplicate=True),
        Input("upload-raw", "contents"),
        State("upload-raw", "filename"),
        State("session-id", "data"),
        prevent_initial_call="initial_duplicate",
    )
    def handle_raw_upload(contents, filename, session_id):
        """Handle raw data CSV upload and cache it."""
        return _handle_upload(contents, filename, session_id, cache, _validate_raw)

    @app.callback(
        Output("layout-upload-status", "children", allow_duplicate=True),
        Output("layout-data-store", "data", allow_duplicate=True),
        Input("upload-layout", "contents"),
        State("upload-layout", "filename"),
        State("session-id", "data"),
        prevent_initial_call="initial_duplicate",
    )
    def handle_layout_upload(contents, filename, session_id):
        """Handle layout CSV upload and cache it."""
        return _handle_upload(contents, filename, session_id, cache, _validate_layout)
