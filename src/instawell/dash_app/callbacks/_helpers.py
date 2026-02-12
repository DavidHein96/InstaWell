"""
Shared helpers for callbacks.
"""

import logging
import uuid

from dash import html, no_update

from ..utils import parse_upload

logger = logging.getLogger("instawell.dash_app.callbacks")

_REFRESH_OUTPUT_COUNT = 16


def _refresh_keep(options, value):
    """Return refresh_experiments output keeping all stores unchanged."""
    return (options, value) + (no_update,) * (_REFRESH_OUTPUT_COUNT - 2)


def _handle_upload(contents, filename, session_id, cache, validator_fn):
    """Generic file upload handler.

    Args:
        contents: Upload contents from dcc.Upload
        filename: Original filename
        session_id: Current session ID
        cache: Flask-Caching cache instance
        validator_fn: Function(df) -> error_message or None

    Returns:
        (status_component, cache_key_or_none)
    """
    if contents is None:
        return "", None

    try:
        if session_id is None:
            session_id = str(uuid.uuid4())

        df = parse_upload(contents, filename)

        error = validator_fn(df)
        if error:
            return html.Span(error, className="text-danger"), None

        cache_key = f"{session_id}_{filename}"
        try:
            cache.set(cache_key, df)
        except Exception as cache_error:
            return (
                html.Span(
                    f"Error caching data: {cache_error!s}", className="text-danger"
                ),
                None,
            )

        logger.info("Uploaded %s (session %s)", filename, session_id[:8])
        return (
            html.Span(
                [html.I(className="fa fa-check-circle me-1"), f"Loaded: {filename}"],
                className="text-success",
            ),
            cache_key,
        )
    except Exception as e:
        logger.exception("Upload failed for %s", filename)
        return html.Span(f"Error: {e!s}", className="text-danger"), None
