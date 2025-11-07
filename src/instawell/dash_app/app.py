"""
Main Dash application setup.
"""

from pathlib import Path

import dash_bootstrap_components as dbc
from dash import Dash

from .callbacks import register_callbacks
from .designer_callbacks import register_designer_callbacks
from .layout import create_layout


def create_app(experiments_root: str = "experiments", debug: bool = False) -> Dash:
    """
    Create and configure the Dash application.

    Args:
        experiments_root: Root directory containing experiments
        debug: Enable debug mode

    Returns:
        Configured Dash app instance
    """
    app = Dash(
        __name__,
        external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME],
        suppress_callback_exceptions=True,
        title="InstaWell - DSF Data Analysis",
    )

    # Store experiments root in app config
    app.experiments_root = Path(experiments_root)
    app.experiments_root.mkdir(parents=True, exist_ok=True)

    # Create layout
    app.layout = create_layout()

    # Register callbacks
    register_callbacks(app)
    register_designer_callbacks(app)

    return app


def main():
    """Entry point for running the Dash app standalone."""
    app = create_app(debug=True)
    app.run(host="127.0.0.1", port=8050, debug=True)


if __name__ == "__main__":
    main()
