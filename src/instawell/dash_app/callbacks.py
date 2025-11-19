"""
Dash callbacks for user interactions.
"""

import traceback
from pathlib import Path

import dash_bootstrap_components as dbc
import pandas as pd
from dash import Input, Output, State, callback_context, dcc, html
from dash.exceptions import PreventUpdate

from instawell import (
    StepFiles,
    average_accross_replicates,
    calculate_derivative,
    filter_wells,
    find_min_temperature,
    ingest_data,
    load_experiment_context,
    min_max_scale,
    setup_experiment,
    subtract_background,
)
from instawell.figures.fig_03_bgsub_raw import bgsub_figure_generator
from instawell.figures.fig_04_bgsub_minmax import bgsub_minmax_figure_generator
from instawell.figures.fig_05_derivative import derivative_figure_generator
from instawell.figures.min_temp_fig import min_temp_figure_generator
from instawell.figures.processed_data_fig import averaged_figure_generator
from instawell.figures.raw_data_fig import raw_figure_generator

from .utils import get_experiment_list, get_experiment_status, parse_upload


def register_callbacks(app):
    """Register all callbacks for the app."""

    @app.callback(
        Output("experiment-dropdown", "options"),
        Output("experiment-dropdown", "value"),
        Input("refresh-experiments-btn", "n_clicks"),
        Input("pipeline-status", "children"),
        State("experiment-dropdown", "value"),
    )
    def refresh_experiments(n_clicks, pipeline_status, current_value):
        """Refresh the list of experiments."""
        experiments = get_experiment_list(app.experiments_root)
        options = [{"label": name, "value": name} for name in experiments]

        # If pipeline just completed successfully, select the new experiment
        if callback_context.triggered_id == "pipeline-status" and pipeline_status:
            if isinstance(pipeline_status, dict) and "props" in pipeline_status:
                children = pipeline_status["props"].get("children", [])
                if children and "Successfully created experiment" in str(children):
                    # Extract experiment name from success message
                    for child in children:
                        if isinstance(child, str) and "'" in child:
                            exp_name = child.split("'")[1]
                            if exp_name in experiments:
                                return options, exp_name

        # Keep current selection if it still exists
        if current_value and current_value in experiments:
            return options, current_value

        # Otherwise select first experiment or None
        return options, experiments[0] if experiments else None

    @app.callback(
        Output("experiment-info", "children"),
        Input("experiment-dropdown", "value"),
    )
    def update_experiment_info(experiment_name):
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
            return html.Span("Not yet processed", className="text-warning")

        step_icons = {
            "ingest": "fa-inbox",
            "filter": "fa-filter",
            "average": "fa-compress",
            "complete": "fa-check-circle",
        }

        badges = [
            html.I(
                className=f"fa {step_icons.get(step, 'fa-circle')} me-1",
                title=step.title(),
            )
            for step in completed_steps
        ]

        return html.Div(
            [
                html.Span(badges, className="me-2"),
                html.Span(f"{total_conditions} conditions", className="text-muted small"),
            ]
        )

    @app.callback(
        Output("raw-upload-status", "children"),
        Output("raw-data-store", "data"),
        Input("upload-raw", "contents"),
        State("upload-raw", "filename"),
    )
    def handle_raw_upload(contents, filename):
        """Handle raw data CSV upload."""
        if contents is None:
            return "", None

        try:
            df = parse_upload(contents, filename)
            if "Temperature" not in df.columns:
                return html.Span(
                    "Error: Missing 'Temperature' column", className="text-danger"
                ), None

            return html.Span(
                [html.I(className="fa fa-check-circle me-1"), f"Loaded: {filename}"],
                className="text-success",
            ), df.to_dict("records")
        except Exception as e:
            return html.Span(f"Error: {e!s}", className="text-danger"), None

    @app.callback(
        Output("layout-upload-status", "children"),
        Output("layout-data-store", "data"),
        Input("upload-layout", "contents"),
        State("upload-layout", "filename"),
    )
    def handle_layout_upload(contents, filename):
        """Handle layout CSV upload."""
        if contents is None:
            return "", None

        try:
            df = parse_upload(contents, filename)
            # Basic validation - should have well column and numeric columns
            has_well_col = any(col.lower().startswith("well") for col in df.columns)
            if not has_well_col:
                return html.Span("Error: Missing well column", className="text-danger"), None

            return html.Span(
                [html.I(className="fa fa-check-circle me-1"), f"Loaded: {filename}"],
                className="text-success",
            ), df.to_dict("records")
        except Exception as e:
            return html.Span(f"Error: {e!s}", className="text-danger"), None

    @app.callback(
        Output("well-filter-card", "style"),
        Output("well-filter-content", "children"),
        Input("raw-data-store", "data"),
        Input("layout-data-store", "data"),
    )
    def show_well_filter(raw_data, layout_data):
        """Show well filter card and populate with available wells."""
        if not raw_data or not layout_data:
            return {"display": "none"}, html.Div(
                [
                    html.I(className="fa fa-info-circle fa-2x text-muted mb-2"),
                    html.P(
                        "Upload data files to see available wells",
                        className="text-muted",
                    ),
                ],
                className="text-center py-4",
            )

        # Extract well names from raw data
        raw_df = pd.DataFrame(raw_data)
        well_columns = [col for col in raw_df.columns if col != "Temperature"]

        if not well_columns:
            return {"display": "none"}, html.Div()

        # Create checklist for wells
        well_options = [{"label": well, "value": well} for well in sorted(well_columns)]

        content = html.Div(
            [
                html.Div(
                    [
                        html.Div(
                            [
                                dbc.Button(
                                    "Select All",
                                    id="select-all-wells-btn",
                                    size="sm",
                                    color="secondary",
                                    outline=True,
                                    className="me-2",
                                ),
                                dbc.Button(
                                    "Deselect All",
                                    id="deselect-all-wells-btn",
                                    size="sm",
                                    color="secondary",
                                    outline=True,
                                ),
                            ],
                            className="mb-2",
                        ),
                        html.Small(
                            f"{len(well_columns)} wells available",
                            className="text-muted",
                        ),
                    ],
                    className="well-filter-header",
                ),
                dbc.Checklist(
                    id="wells-to-filter-checklist",
                    options=well_options,
                    value=[],  # None selected by default
                    inline=False,
                    className="mt-2",
                ),
            ],
            className="well-filter-container",
        )

        return {"display": "block"}, content

    @app.callback(
        Output("wells-to-filter-checklist", "value", allow_duplicate=True),
        Input("select-all-wells-btn", "n_clicks"),
        State("wells-to-filter-checklist", "options"),
        prevent_initial_call=True,
    )
    def select_all_wells(n_clicks, options):
        """Select all wells for filtering."""
        if not n_clicks or not options:
            raise PreventUpdate
        return [opt["value"] for opt in options]

    @app.callback(
        Output("wells-to-filter-checklist", "value", allow_duplicate=True),
        Input("deselect-all-wells-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def deselect_all_wells(n_clicks):
        """Deselect all wells."""
        if not n_clicks:
            raise PreventUpdate
        return []

    @app.callback(
        Output("filter-summary", "children"),
        Output("filtered-wells-store", "data"),
        Input("wells-to-filter-checklist", "value"),
    )
    def update_filter_summary(selected_wells):
        """Update summary of filtered wells."""
        if not selected_wells:
            return html.Span(
                [
                    html.I(className="fa fa-check-circle text-success me-2"),
                    "No wells will be filtered - all wells will be included in analysis",
                ],
                className="text-success",
            ), []

        wells_str = ", ".join(sorted(selected_wells))
        return html.Span(
            [
                html.I(className="fa fa-exclamation-triangle text-warning me-2"),
                html.Strong(f"{len(selected_wells)} wells will be excluded: "),
                html.Span(wells_str, className="font-monospace"),
            ],
            className="text-warning",
        ), selected_wells

    @app.callback(
        Output("run-pipeline-btn", "disabled"),
        Input("raw-data-store", "data"),
        Input("layout-data-store", "data"),
        Input("experiment-name-input", "value"),
    )
    def enable_run_button(raw_data, layout_data, exp_name):
        """Enable run button when all required inputs are present."""
        if raw_data and layout_data and exp_name and exp_name.strip():
            return False
        return True

    @app.callback(
        Output("pipeline-status", "children"),
        Output("current-experiment-store", "data"),
        Input("run-pipeline-btn", "n_clicks"),
        State("raw-data-store", "data"),
        State("layout-data-store", "data"),
        State("experiment-name-input", "value"),
        State("separator-input", "value"),
        State("fields-input", "value"),
        State("temp-col-input", "value"),
        State("filtered-wells-store", "data"),
        prevent_initial_call=True,
    )
    def run_pipeline(
        n_clicks, raw_data, layout_data, exp_name, separator, fields_str, temp_col, wells_to_filter
    ):
        """Run the full InstaWell pipeline."""
        if not n_clicks:
            raise PreventUpdate

        try:
            # Parse fields
            fields = tuple(f.strip() for f in fields_str.split(","))

            # Save data to temp files
            temp_dir = Path("/tmp") / "instawell_uploads"
            temp_dir.mkdir(exist_ok=True)

            raw_df = pd.DataFrame(raw_data)
            layout_df = pd.DataFrame(layout_data)

            raw_path = temp_dir / f"{exp_name}_raw.csv"
            layout_path = temp_dir / f"{exp_name}_layout.csv"

            raw_df.to_csv(raw_path, index=False)
            layout_df.to_csv(layout_path, index=False)

            # Run pipeline
            status_messages = []

            # Step 1: Setup
            status_messages.append("Setting up experiment...")
            ctx = setup_experiment(
                experiment_name=exp_name,
                raw_data_path=str(raw_path),
                layout_data_path=str(layout_path),
                experiments_root=str(app.experiments_root),
                condition_separator=separator,
                fields=fields,
                temperature_column=temp_col,
            )

            # Step 2: Ingest
            status_messages.append("Ingesting data...")
            ingest_data(ctx)

            # Step 3: Filter wells (use selected wells from UI)
            if wells_to_filter:
                status_messages.append(f"Filtering {len(wells_to_filter)} wells...")
            else:
                status_messages.append("No wells filtered...")
            filter_wells(ctx, wells_to_filter=wells_to_filter or [])

            # Step 4: Average
            status_messages.append("Averaging replicates...")
            average_accross_replicates(ctx)

            # Step 5: Background subtraction
            status_messages.append("Subtracting background...")
            subtract_background(ctx)

            # Step 6: Min-max scaling
            status_messages.append("Normalizing data...")
            min_max_scale(ctx)

            # Step 7: Derivative
            status_messages.append("Calculating derivative...")
            calculate_derivative(ctx)

            # Step 8: Find Tm
            status_messages.append("Finding melting temperatures...")
            find_min_temperature(ctx)

            return html.Div(
                [
                    html.Div(
                        [
                            html.I(className="fa fa-check-circle me-2"),
                            f"Successfully created experiment '{exp_name}'!",
                        ],
                        className="alert alert-success",
                    ),
                ],
            ), exp_name

        except Exception as e:
            error_msg = str(e)
            stack_trace = traceback.format_exc()
            return html.Div(
                [
                    html.Div(
                        [
                            html.I(className="fa fa-exclamation-triangle me-2"),
                            f"Error: {error_msg}",
                        ],
                        className="alert alert-danger",
                    ),
                    html.Details(
                        [
                            html.Summary("Show details"),
                            html.Pre(stack_trace, className="small mt-2"),
                        ]
                    ),
                ],
            ), None

    @app.callback(
        Output("figures-container", "children"),
        Input("experiment-dropdown", "value"),
        Input("current-experiment-store", "data"),
        Input("fig-btn-raw", "n_clicks"),
        Input("fig-btn-averaged", "n_clicks"),
        Input("fig-btn-bgsub", "n_clicks"),
        Input("fig-btn-minmax", "n_clicks"),
        Input("fig-btn-deriv", "n_clicks"),
        Input("fig-btn-tm", "n_clicks"),
        prevent_initial_call=False,
    )
    def display_figures(
        selected_exp,
        new_exp,
        n_raw,
        n_avg,
        n_bgsub,
        n_minmax,
        n_deriv,
        n_tm,
    ):
        """Display figures for selected experiment."""
        # Determine which experiment to show
        experiment_name = new_exp if new_exp else selected_exp

        if not experiment_name:
            return html.Div(
                [
                    html.I(className="fa fa-info-circle fa-3x text-muted mb-3"),
                    html.P(
                        "Select an experiment or upload data to view figures",
                        className="text-muted",
                    ),
                ],
                className="text-center py-5",
            )

        # Determine which figure type to show
        triggered = callback_context.triggered_id
        figure_type = "averaged"  # default

        if triggered == "fig-btn-raw":
            figure_type = "raw"
        elif triggered == "fig-btn-averaged":
            figure_type = "averaged"
        elif triggered == "fig-btn-bgsub":
            figure_type = "bgsub"
        elif triggered == "fig-btn-minmax":
            figure_type = "minmax"
        elif triggered == "fig-btn-deriv":
            figure_type = "derivative"
        elif triggered == "fig-btn-tm":
            figure_type = "tm"

        try:
            # Load experiment context
            ctx = load_experiment_context(
                experiment_name, experiments_root=str(app.experiments_root)
            )

            # Check which data files exist
            required_files = {
                "raw": StepFiles.INGESTED_DATA,
                "averaged": StepFiles.AVERAGED_DATA,
                "bgsub": StepFiles.BG_SUB_DATA,
                "minmax": StepFiles.MIN_MAX_SCALED_DATA,
                "derivative": StepFiles.DERIVATIVE_DATA,
                "tm": StepFiles.MIN_TEMPERATURES_DATA,
            }

            if not (ctx.experiment_dir / required_files[figure_type]).exists():
                return html.Div(
                    [
                        html.I(className="fa fa-exclamation-triangle fa-2x text-warning mb-3"),
                        html.P(
                            f"Pipeline step '{figure_type}' not yet completed for this experiment",
                            className="text-muted",
                        ),
                        html.P(
                            "Run the full pipeline to generate all figures",
                            className="small text-muted",
                        ),
                    ],
                    className="text-center py-5",
                )

            # Generate figures using tested generators
            generators = {
                "raw": raw_figure_generator,
                "averaged": averaged_figure_generator,
                "bgsub": bgsub_figure_generator,
                "minmax": bgsub_minmax_figure_generator,
                "derivative": derivative_figure_generator,
                "tm": min_temp_figure_generator,
            }

            generator = generators[figure_type]
            figures = list(generator(ctx))

            if not figures:
                return html.Div(
                    [
                        html.I(className="fa fa-chart-line fa-2x text-muted mb-3"),
                        html.P("No figures generated", className="text-muted"),
                    ],
                    className="text-center py-5",
                )

            # Display all figures
            figure_components = []
            for i, fig in enumerate(figures):
                figure_components.append(
                    html.Div(
                        [
                            dcc.Graph(figure=fig, config={"displayModeBar": True}),
                        ],
                        className="mb-4",
                    )
                )

            return html.Div(figure_components)

        except Exception as e:
            return html.Div(
                [
                    html.I(className="fa fa-exclamation-triangle fa-2x text-danger mb-3"),
                    html.P(f"Error loading figures: {e!s}", className="text-danger"),
                ],
                className="text-center py-5",
            )
