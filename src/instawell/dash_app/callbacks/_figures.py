"""
Figure loading and navigation callbacks.
"""

import logging

from dash import Input, Output, State, callback_context, dcc, html
from dash.exceptions import PreventUpdate

from instawell import load_experiment_context
from instawell.figures.min_temp_fig import min_temp_figure_generator
from instawell.figures.processed_data_fig import processed_figure_generator
from instawell.figures.raw_data_fig import raw_figure_generator

from ..constants import FIGURE_BUTTON_MAP, FIGURE_STEP_FILES

logger = logging.getLogger("instawell.dash_app.figures")

# Figure generators keyed by figure type
_GENERATORS = {
    "raw": raw_figure_generator,
    "averaged": lambda c: processed_figure_generator(c, data_source="averaged_data"),
    "bgsub": lambda c: processed_figure_generator(c, data_source="bg_subtracted_data"),
    "minmax": lambda c: processed_figure_generator(
        c, data_source="min_max_scaled_data"
    ),
    "derivative": lambda c: processed_figure_generator(
        c, data_source="derivative_data"
    ),
    "tm": min_temp_figure_generator,
}


def register_figure_callbacks(app, cache):
    """Register figure loading and navigation callbacks."""

    @app.callback(
        Output("figures-store", "data"),
        Output("current-figure-index", "data"),
        Output("fig-btn-averaged", "style"),
        Output("fig-btn-bgsub", "style"),
        Output("fig-btn-minmax", "style"),
        Output("fig-btn-deriv", "style"),
        Output("fig-btn-tm", "style"),
        Input("experiment-dropdown", "value"),
        Input("current-experiment-store", "data"),
        Input("setup-complete-store", "data"),
        Input("fig-btn-raw", "n_clicks"),
        Input("fig-btn-averaged", "n_clicks"),
        Input("fig-btn-bgsub", "n_clicks"),
        Input("fig-btn-minmax", "n_clicks"),
        Input("fig-btn-deriv", "n_clicks"),
        Input("fig-btn-tm", "n_clicks"),
        prevent_initial_call=False,
    )
    def load_figures(
        selected_exp,
        new_exp,
        setup_complete,
        n_raw,
        n_avg,
        n_bgsub,
        n_minmax,
        n_deriv,
        n_tm,
    ):
        """Load figures and store them for navigation."""
        # Determine which experiment to show
        experiment_name = new_exp if new_exp else selected_exp
        hidden = {"display": "none"}

        if not experiment_name:
            return None, 0, hidden, hidden, hidden, hidden, hidden

        # Determine which figure type to show
        triggered = callback_context.triggered_id or "fig-btn-raw"
        figure_type = FIGURE_BUTTON_MAP.get(triggered, "raw")

        try:
            ctx = load_experiment_context(
                experiment_name, experiments_root=str(app.experiments_root)
            )

            # Check which data files exist
            visibility = {
                key: {
                    "display": "inline-block"
                    if (ctx.experiment_dir / step.value).exists()
                    else "none"
                }
                for key, step in FIGURE_STEP_FILES.items()
                if key != "raw"
            }

            required_file = ctx.experiment_dir / FIGURE_STEP_FILES[figure_type].value
            if not required_file.exists():
                return (
                    None,
                    0,
                    visibility["averaged"],
                    visibility["bgsub"],
                    visibility["minmax"],
                    visibility["derivative"],
                    visibility["tm"],
                )

            # Generate figures
            logger.info("Loading %s figures for '%s'", figure_type, experiment_name)
            figures = list(_GENERATORS[figure_type](ctx))

            if not figures:
                return (
                    None,
                    0,
                    visibility["averaged"],
                    visibility["bgsub"],
                    visibility["minmax"],
                    visibility["derivative"],
                    visibility["tm"],
                )

            # Extract titles and serialize figures
            figures_data = []
            for i, fig in enumerate(figures, start=1):
                title = f"Figure {i}"
                try:
                    layout_dict = fig.layout.to_plotly_json()
                    if "title" in layout_dict:
                        title_data = layout_dict["title"]
                        if isinstance(title_data, dict) and "text" in title_data:
                            title = title_data["text"]
                        elif isinstance(title_data, str):
                            title = title_data
                except Exception:
                    logger.exception("Failed to extract title from figure %d", i)

                figures_data.append({"title": title, "figure": fig.to_dict()})

            return (
                figures_data,
                0,
                visibility["averaged"],
                visibility["bgsub"],
                visibility["minmax"],
                visibility["derivative"],
                visibility["tm"],
            )

        except Exception:
            logger.exception(
                "Failed to load %s figures for '%s'", figure_type, experiment_name
            )
            return None, 0, hidden, hidden, hidden, hidden, hidden

    @app.callback(
        Output("figures-container", "children"),
        Output("figure-nav-controls", "style"),
        Output("figure-selector-dropdown", "options"),
        Output("figure-selector-dropdown", "value"),
        Output("figure-counter", "children"),
        Input("figures-store", "data"),
        Input("current-figure-index", "data"),
    )
    def display_current_figure(figures_data, current_index):
        """Display the current figure based on stored data and index."""
        if not figures_data or not isinstance(figures_data, list):
            return (
                html.Div(
                    [
                        html.I(
                            className="fa fa-info-circle fa-3x text-muted mb-3"
                        ),
                        html.P(
                            "Select an experiment or upload data to view figures",
                            className="text-muted",
                        ),
                    ],
                    className="text-center py-5",
                ),
                {"display": "none"},  # Hide navigation controls
                [],  # No dropdown options
                None,  # No dropdown value
                "",  # No counter text
            )

        # Ensure index is within bounds
        if current_index < 0 or current_index >= len(figures_data):
            current_index = 0

        # Get current figure
        current_fig_data = figures_data[current_index]
        fig_dict = current_fig_data["figure"]

        # Create dropdown options
        dropdown_options = [
            {"label": fig_data["title"], "value": i}
            for i, fig_data in enumerate(figures_data)
        ]

        # Create counter text
        counter_text = f"Figure {current_index + 1} of {len(figures_data)}"

        return (
            dcc.Graph(figure=fig_dict),
            {"display": "block"},  # Show navigation controls
            dropdown_options,
            current_index,
            counter_text,
        )

    @app.callback(
        Output("current-figure-index", "data", allow_duplicate=True),
        Input("fig-prev-btn", "n_clicks"),
        State("current-figure-index", "data"),
        State("figures-store", "data"),
        prevent_initial_call=True,
    )
    def navigate_previous(n_clicks, current_index, figures_data):
        """Navigate to previous figure."""
        if not n_clicks or not figures_data:
            raise PreventUpdate

        new_index = max(0, current_index - 1)
        return new_index

    @app.callback(
        Output("current-figure-index", "data", allow_duplicate=True),
        Input("fig-next-btn", "n_clicks"),
        State("current-figure-index", "data"),
        State("figures-store", "data"),
        prevent_initial_call=True,
    )
    def navigate_next(n_clicks, current_index, figures_data):
        """Navigate to next figure."""
        if not n_clicks or not figures_data:
            raise PreventUpdate

        new_index = min(len(figures_data) - 1, current_index + 1)
        return new_index

    @app.callback(
        Output("current-figure-index", "data", allow_duplicate=True),
        Input("figure-selector-dropdown", "value"),
        State("figures-store", "data"),
        prevent_initial_call=True,
    )
    def select_figure_from_dropdown(selected_index, figures_data):
        """Update current figure when dropdown selection changes."""
        if selected_index is None or not figures_data:
            raise PreventUpdate

        return selected_index
