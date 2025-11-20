"""
Main Dash application setup.
"""

from pathlib import Path

from .callbacks import register_callbacks
from .designer_callbacks import register_designer_callbacks
from .layout import create_layout


def create_app(experiments_root: str = "experiments", debug: bool = False):
    """
    Create and configure the Dash application.

    Args:
        experiments_root: Root directory containing experiments
        debug: Enable debug mode

    Returns:
        Configured Dash app instance
    """
    try:
        import dash_bootstrap_components as dbc
        from dash import Dash
    except ImportError as exc:
        message = (
            "The Instawell Dash app requires the 'dash' extra.\n"
            "Install it with:\n\n"
            "    pip install 'instawell[dash]'\n"
        )
        raise SystemExit(message) from exc

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
    import argparse

    parser = argparse.ArgumentParser(description="Launch the InstaWell Dash app.")
    parser.add_argument(
        "--experiments-root",
        default="experiments",
        help="Directory where experiments are stored (default: %(default)s)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host interface for the Dash server (default: %(default)s)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8050,
        help="Port for the Dash server (default: %(default)s)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable Dash debug/reload mode",
    )
    args = parser.parse_args()

    app = create_app(experiments_root=args.experiments_root, debug=args.debug)
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
