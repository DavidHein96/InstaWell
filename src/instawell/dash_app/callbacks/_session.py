"""
Session management callbacks.
"""

import uuid

from dash import Input, Output


def register_session_callbacks(app, cache):
    """Register session-related callbacks."""

    @app.callback(
        Output("session-id", "data"),
        Input("session-id", "data"),
    )
    def assign_session_id(session_id):
        """Assign a unique session ID if one doesn't exist."""
        if session_id is None:
            session_id = str(uuid.uuid4())
        return session_id
