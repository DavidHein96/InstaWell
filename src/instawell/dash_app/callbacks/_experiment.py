"""
Experiment management callbacks.
"""

import logging

import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback_context, html
from dash.exceptions import PreventUpdate

from ..constants import STEP_ICONS
from ..utils import get_experiment_list, get_experiment_status
from ._helpers import _refresh_keep

logger = logging.getLogger("instawell.dash_app.experiment")


def register_experiment_callbacks(app, cache):
    """Register experiment browsing and management callbacks."""

    @app.callback(
        Output("current-experiment-banner", "children"),
        Input("experiment-dropdown", "value"),
    )
    def show_experiment_banner(experiment_name):
        """Show prominent banner when an experiment is loaded."""
        if not experiment_name:
            return html.Div()

        return dbc.Alert(
            [
                html.I(className="fa fa-flask me-2"),
                html.Strong("Currently Viewing: "),
                html.Span(experiment_name, className="font-monospace"),
                html.Span(" — ", className="mx-2"),
                html.Small(
                    "Click 'Clear' above to create new experiments or layouts",
                    className="text-muted",
                ),
            ],
            color="info",
            className="mb-3",
        )

    @app.callback(
        Output("new-experiment-collapse", "is_open"),
        Output("new-experiment-toggle-btn", "children"),
        Output("new-experiment-toggle-btn", "color"),
        Output("new-experiment-toggle-btn", "outline"),
        Output("new-experiment-toggle-btn", "disabled"),
        Output("designer-toggle-btn", "disabled"),
        Output("designer-toggle-btn", "children", allow_duplicate=True),
        Output("designer-collapse", "is_open", allow_duplicate=True),
        Input("new-experiment-toggle-btn", "n_clicks"),
        Input("experiment-dropdown", "value"),
        State("new-experiment-collapse", "is_open"),
        prevent_initial_call=True,
    )
    def toggle_new_experiment(n_clicks, selected_exp, is_open):
        """Toggle new experiment card and disable when experiment is loaded."""
        triggered = callback_context.triggered_id

        # If an experiment is loaded, collapse and disable both buttons
        if selected_exp:
            return (
                False,
                "Clear loaded experiment to create new",
                "secondary",
                True,
                True,
                True,
                "Clear loaded experiment to use designer",
                False,
            )

        # If no experiment loaded, allow toggling
        if triggered == "new-experiment-toggle-btn" and n_clicks:
            new_state = not is_open
            if new_state:  # Opening
                return (
                    True,
                    "Hide New Experiment",
                    "secondary",
                    True,
                    False,
                    False,
                    "Show Designer",
                    False,
                )
            # Closing
            return (
                False,
                "Show New Experiment",
                "primary",
                False,
                False,
                False,
                "Show Designer",
                False,
            )

        # Default: no experiment loaded, no toggle click — keep new experiment open
        return (
            True,
            "Hide New Experiment",
            "secondary",
            True,
            False,
            False,
            "Show Designer",
            False,
        )

    @app.callback(
        Output("experiment-dropdown", "options"),
        Output("experiment-dropdown", "value"),
        Output("current-experiment-store", "data", allow_duplicate=True),
        Output("raw-data-store", "data", allow_duplicate=True),
        Output("layout-data-store", "data", allow_duplicate=True),
        Output("setup-complete-store", "data", allow_duplicate=True),
        Output("selected-wells-grid", "data", allow_duplicate=True),
        Output("figures-store", "data", allow_duplicate=True),
        Output("current-figure-index", "data", allow_duplicate=True),
        Output("setup-status", "children", allow_duplicate=True),
        Output("pipeline-status", "children", allow_duplicate=True),
        Output("raw-upload-status", "children", allow_duplicate=True),
        Output("layout-upload-status", "children", allow_duplicate=True),
        Output("well-filter-card", "style", allow_duplicate=True),
        Output("experiment-name-input", "value", allow_duplicate=True),
        Output("layout-validation-status", "children", allow_duplicate=True),
        Input("refresh-experiments-btn", "n_clicks"),
        Input("last-pipeline-experiment", "data"),
        Input("clear-experiment-btn", "n_clicks"),
        State("experiment-dropdown", "value"),
        prevent_initial_call="initial_duplicate",
    )
    def refresh_experiments(n_refresh, last_pipeline_exp, n_clear, current_value):
        """Refresh the list of experiments or clear selection."""
        experiments = get_experiment_list(app.experiments_root)
        options = [{"label": name, "value": name} for name in experiments]

        # If triggered by last-pipeline-experiment with None, don't reload
        if (
            callback_context.triggered_id == "last-pipeline-experiment"
            and not last_pipeline_exp
        ):
            raise PreventUpdate

        # If clear button was clicked, clear everything
        if callback_context.triggered_id == "clear-experiment-btn":
            return (
                options,  # Keep experiment options
                None,  # Clear dropdown selection
                None,  # Clear current experiment
                None,  # Clear raw data
                None,  # Clear layout data
                False,  # Reset setup complete
                [],  # Clear selected wells
                None,  # Clear figures
                0,  # Reset figure index
                "",  # Clear setup status
                "",  # Clear pipeline status
                "",  # Clear raw upload status
                "",  # Clear layout upload status
                {"display": "none"},  # Hide well filter card
                "",  # Clear experiment name input
                "",  # Clear layout validation status
            )

        # If pipeline just completed, select the new experiment
        if (
            callback_context.triggered_id == "last-pipeline-experiment"
            and last_pipeline_exp
            and last_pipeline_exp in experiments
        ):
            return _refresh_keep(options, last_pipeline_exp)

        # Keep current selection if it still exists (refresh button)
        if current_value and current_value in experiments:
            return _refresh_keep(options, current_value)

        # Otherwise select first experiment or None
        return _refresh_keep(options, experiments[0] if experiments else None)

    @app.callback(
        Output("experiment-info", "children"),
        Input("experiment-dropdown", "value"),
        Input("last-pipeline-experiment", "data"),
    )
    def update_experiment_info(experiment_name, _last_pipeline):
        """Show info about selected experiment."""
        if not experiment_name:
            return ""

        exp_dir = app.experiments_root / experiment_name
        if not exp_dir.exists():
            return html.Span("Experiment not found", className="text-danger")

        status = get_experiment_status(exp_dir)
        completed_steps = status["completed_steps"]
        total_conditions = status.get("total_conditions", "?")

        if not completed_steps:
            return ""

        badges = [
            html.I(
                className=f"fa {STEP_ICONS.get(step, 'fa-circle')} me-1",
                title=step.title(),
            )
            for step in completed_steps
        ]

        return html.Div(
            [
                html.Span(badges, className="me-2"),
                html.Span(
                    f"{total_conditions} conditions", className="text-muted small"
                ),
            ]
        )
