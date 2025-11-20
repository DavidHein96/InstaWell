"""
Dash callbacks for user interactions.
"""

import tempfile
import traceback
from pathlib import Path

import dash_bootstrap_components as dbc
import pandas as pd
from dash import Input, Output, State, callback_context, dcc, html
from dash.exceptions import PreventUpdate

from instawell import (
    StepFiles,
    average_across_replicates,
    calculate_derivative,
    filter_wells,
    find_min_temperature,
    ingest_data,
    load_experiment_context,
    min_max_scale,
    setup_experiment,
    subtract_background,
)
from instawell.core.parser import parse_condition_string
from instawell.figures.min_temp_fig import min_temp_figure_generator
from instawell.figures.processed_data_fig import processed_figure_generator
from instawell.figures.raw_data_fig import raw_figure_generator

from .utils import get_experiment_list, get_experiment_status, parse_upload


def register_callbacks(app):
    """Register all callbacks for the app."""

    @app.callback(
        Output("current-experiment-banner", "children"),
        Input("experiment-dropdown", "value"),
    )
    def show_experiment_banner(experiment_name):
        """Show prominent banner when an experiment is loaded."""
        if not experiment_name:
            return html.Div()  # Empty if no experiment

        return dbc.Alert(
            [
                html.I(className="fa fa-flask me-2"),
                html.Strong("Currently Viewing: "),
                html.Span(experiment_name, className="font-monospace"),
                html.Span(" — ", className="mx-2"),
                html.Small("Click 'Clear' above to create new experiments or layouts", className="text-muted"),
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

        # If an experiment is loaded, collapse and disable both buttons with helpful text
        if selected_exp:
            return (
                False,  # collapse new experiment
                "Clear loaded experiment to create new",
                "secondary",
                True,  # outlined
                True,  # disable new experiment button
                True,  # disable designer button
                "Clear loaded experiment to use designer",
                False,  # collapse designer too
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
                    False,  # enable button
                    False,  # enable designer button
                    "Show Designer",
                    False,  # keep designer collapsed when opening new experiment
                )
            else:  # Closing
                return (
                    False,
                    "Show New Experiment",
                    "primary",
                    False,
                    False,  # enable button
                    False,  # enable designer button
                    "Show Designer",
                    False,  # keep designer collapsed
                )

        # Default: no experiment loaded, no toggle click - keep new experiment open
        # This happens when experiment is cleared
        return (
            True,  # open by default
            "Hide New Experiment",
            "secondary",
            True,
            False,  # enable button
            False,  # enable designer button
            "Show Designer",
            False,  # designer collapsed by default
        )

    @app.callback(
        Output("experiment-dropdown", "options"),
        Output("experiment-dropdown", "value"),
        Input("refresh-experiments-btn", "n_clicks"),
        Input("pipeline-status", "children"),
        Input("clear-experiment-btn", "n_clicks"),
        State("experiment-dropdown", "value"),
    )
    def refresh_experiments(n_refresh, pipeline_status, n_clear, current_value):
        """Refresh the list of experiments or clear selection."""
        experiments = get_experiment_list(app.experiments_root)
        options = [{"label": name, "value": name} for name in experiments]

        # If clear button was clicked, clear the selection
        if callback_context.triggered_id == "clear-experiment-btn":
            return options, None

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
        Input("pipeline-status", "children"),  # Add trigger to update when pipeline completes
    )
    def update_experiment_info(experiment_name, pipeline_status):
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
            return ""  # Show nothing if not yet processed

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
        Output("well-filter-content", "children"),
        Input("current-experiment-store", "data"),
        State("raw-data-store", "data"),
    )
    def populate_well_filter(exp_name, raw_data):
        """Populate well filter checklist after setup completes."""
        if not exp_name or not raw_data:
            return html.Div(
                [
                    html.I(className="fa fa-info-circle fa-2x text-muted mb-2"),
                    html.P(
                        "Run setup to see available wells",
                        className="text-muted",
                    ),
                ],
                className="text-center py-4",
            )

        # Extract well names from raw data
        raw_df = pd.DataFrame(raw_data)
        well_columns = [col for col in raw_df.columns if col != "Temperature"]

        if not well_columns:
            return html.Div()

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

        return content

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
        Output("setup-ingest-btn", "disabled"),
        Output("validate-layout-btn", "disabled"),
        Input("raw-data-store", "data"),
        Input("layout-data-store", "data"),
        Input("experiment-name-input", "value"),
    )
    def enable_setup_button(raw_data, layout_data, exp_name):
        """Enable buttons when required inputs are present."""
        has_uploads = bool(raw_data) and bool(layout_data)
        setup_disabled = not (has_uploads and exp_name and exp_name.strip())
        validate_disabled = not has_uploads
        return setup_disabled, validate_disabled

    @app.callback(
        Output("run-pipeline-btn", "disabled"),
        Input("setup-complete-store", "data"),
    )
    def enable_pipeline_button(setup_complete):
        """Enable pipeline button only after setup/ingest is complete."""
        return not setup_complete

    @app.callback(
        Output("layout-validation-status", "children"),
        Input("validate-layout-btn", "n_clicks"),
        State("raw-data-store", "data"),
        State("layout-data-store", "data"),
        State("separator-input", "value"),
        State("fields-input", "value"),
        State("empty-placeholder-input", "value"),
        State("temp-col-input", "value"),
        prevent_initial_call=True,
    )
    def validate_layout(
        n_clicks,
        raw_data,
        layout_data,
        separator,
        fields_str,
        empty_placeholder,
        temperature_column,
    ):
        """Validate uploaded raw/layout files against provided parsing settings."""
        if not n_clicks:
            raise PreventUpdate

        if not raw_data or not layout_data:
            return html.Div(
                [
                    html.I(className="fa fa-exclamation-triangle me-2"),
                    "Upload both raw and layout CSV files before validating.",
                ],
                className="alert alert-warning",
            )

        try:
            fields = tuple(f.strip() for f in fields_str.split(",") if f.strip())
            if not fields:
                raise ValueError("Field order cannot be empty.")
            if not fields:
                raise ValueError("Field order cannot be empty.")
            if not separator or len(separator) != 1:
                raise ValueError("Condition separator must be exactly one character.")
            if not empty_placeholder or len(empty_placeholder) != 1:
                raise ValueError("Missing condition placeholder must be exactly one character.")
            if separator == empty_placeholder:
                raise ValueError("Separator and placeholder must be different characters.")

            layout_df = pd.DataFrame(layout_data)
            raw_df = pd.DataFrame(raw_data)

            temp_col = (temperature_column or "Temperature").strip()
            if temp_col not in raw_df.columns:
                match = next((c for c in raw_df.columns if c.lower() == temp_col.lower()), None)
                if match:
                    temp_col = match
                else:
                    raise ValueError(f"Raw data is missing temperature column '{temp_col}'.")

            well_cols = [c for c in layout_df.columns if c.lower().startswith("well")]
            if not well_cols:
                raise ValueError("Layout file must contain a column starting with 'Well'.")
            well_col = well_cols[0]

            mask = separator.join(empty_placeholder for _ in fields)
            errors: list[str] = []
            unique_conditions = set()

            for _, row in layout_df.iterrows():
                well_label = str(row[well_col]).strip()
                for col in layout_df.columns:
                    if col == well_col:
                        continue
                    val = row[col]
                    if pd.isna(val):
                        continue
                    condition_str = str(val).strip()
                    if not condition_str or condition_str == mask:
                        continue
                    try:
                        parse_condition_string(
                            condition_str,
                            delimiter=separator,
                            fields=fields,
                        )
                        unique_conditions.add(condition_str)
                    except ValueError as exc:
                        errors.append(f"{well_label}{col}: {exc}")

            if errors:
                preview = html.Ul(
                    [html.Li(err) for err in errors[:5]],
                    className="mb-0",
                )
                children = [
                    html.Div(
                        [
                            html.I(className="fa fa-exclamation-triangle me-2"),
                            "Layout validation failed. Fix the issues below:",
                        ],
                        className="alert alert-danger mb-2",
                    ),
                    preview,
                ]
                if len(errors) > 5:
                    children.append(
                        html.Small(
                            f"+{len(errors) - 5} more issues",
                            className="text-muted",
                        )
                    )
                return html.Div(children)

            num_wells = len([c for c in raw_df.columns if c != temp_col])
            return html.Div(
                [
                    html.I(className="fa fa-check-circle me-2"),
                    f"Validation successful! Parsed {len(unique_conditions)} conditions across {num_wells} wells.",
                ],
                className="alert alert-success",
            )
        except Exception as exc:
            return html.Div(
                [
                    html.I(className="fa fa-exclamation-triangle me-2"),
                    f"Validation error: {exc}",
                ],
                className="alert alert-danger",
            )

    @app.callback(
        Output("setup-status", "children"),
        Output("current-experiment-store", "data", allow_duplicate=True),
        Output("setup-complete-store", "data"),
        Output("well-filter-card", "style", allow_duplicate=True),
        Input("setup-ingest-btn", "n_clicks"),
        State("raw-data-store", "data"),
        State("layout-data-store", "data"),
        State("experiment-name-input", "value"),
        State("separator-input", "value"),
        State("fields-input", "value"),
        State("empty-placeholder-input", "value"),
        State("npc-input", "value"),
        prevent_initial_call=True,
    )
    def setup_and_ingest(
        n_clicks,
        raw_data,
        layout_data,
        exp_name,
        separator,
        fields_str,
        empty_placeholder,
        npc_marker,
    ):
        """Run setup and ingest steps only."""
        if not n_clicks:
            raise PreventUpdate

        try:
            # Parse fields
            fields = tuple(f.strip() for f in fields_str.split(",") if f.strip())
            sep = (separator or "|").strip() or "|"
            placeholder = (empty_placeholder or "^").strip() or "^"
            npc = (npc_marker or "NPC").strip() or "NPC"

            # Save data to temp files (auto-cleaned)
            with tempfile.TemporaryDirectory(prefix="instawell_uploads_") as tmp_dir:
                temp_dir = Path(tmp_dir)

                raw_df = pd.DataFrame(raw_data)
                layout_df = pd.DataFrame(layout_data)

                raw_path = temp_dir / f"{exp_name}_raw.csv"
                layout_path = temp_dir / f"{exp_name}_layout.csv"

                raw_df.to_csv(raw_path, index=False)
                layout_df.to_csv(layout_path, index=False)

                # Step 1: Setup
                ctx = setup_experiment(
                    experiment_name=exp_name,
                    raw_data_path=str(raw_path),
                    layout_data_path=str(layout_path),
                    experiments_root=str(app.experiments_root),
                    condition_separator=sep,
                    condition_fields=fields,
                    empty_condition_placeholder=placeholder,
                    non_protein_control_marker=npc,
                )

                # Step 2: Ingest
                ingest_data(ctx)

            return (
                html.Div(
                    [
                        html.I(className="fa fa-check-circle me-2"),
                        html.Strong("Setup complete! "),
                        "Review the raw data figures below, optionally filter problematic wells, then click 'Run Full Pipeline' to continue.",
                    ],
                    className="alert alert-success",
                ),
                exp_name,
                True,  # setup_complete
                {"display": "block"},  # show well filter card
            )

        except Exception as e:
            error_msg = str(e)
            stack_trace = traceback.format_exc()
            return (
                html.Div(
                    [
                        html.Div(
                            [
                                html.I(className="fa fa-exclamation-triangle me-2"),
                                f"Error during setup: {error_msg}",
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
                ),
                None,
                False,  # setup not complete
                {"display": "none"},  # hide well filter card
            )

    @app.callback(
        Output("pipeline-status", "children"),
        Output("current-experiment-store", "data", allow_duplicate=True),
        Output("well-filter-card", "style", allow_duplicate=True),
        Input("run-pipeline-btn", "n_clicks"),
        State("current-experiment-store", "data"),
        State("filtered-wells-store", "data"),
        prevent_initial_call=True,
    )
    def run_pipeline(n_clicks, exp_name, wells_to_filter):
        """Run the full pipeline from filter step onwards."""
        if not n_clicks:
            raise PreventUpdate

        if not exp_name:
            return (
                html.Div(
                    "Please run 'Setup & View Raw Data' first",
                    className="alert alert-warning",
                ),
                None,
                {"display": "block"},  # keep filter card visible
            )

        try:
            # Load existing experiment context
            ctx = load_experiment_context(exp_name, experiments_root=str(app.experiments_root))

            # Run pipeline from filter step onwards

            # Step 3: Filter wells (use selected wells from UI)
            if wells_to_filter:
                filter_wells(ctx, wells_to_filter=wells_to_filter)
            else:
                filter_wells(ctx, wells_to_filter=[])

            # Step 4: Average
            average_across_replicates(ctx)

            # Step 5: Background subtraction
            subtract_background(ctx)

            # Step 6: Min-max scaling
            min_max_scale(ctx)

            # Step 7: Derivative
            calculate_derivative(ctx)

            # Step 8: Find Tm
            find_min_temperature(ctx)

            return (
                html.Div(
                    [
                        html.I(className="fa fa-check-circle me-2"),
                        f"Pipeline complete for '{exp_name}'! All processing steps finished successfully.",
                    ],
                    className="alert alert-success",
                ),
                exp_name,
                {"display": "none"},  # hide well filter card after pipeline runs
            )

        except Exception as e:
            error_msg = str(e)
            stack_trace = traceback.format_exc()
            return (
                html.Div(
                    [
                        html.Div(
                            [
                                html.I(className="fa fa-exclamation-triangle me-2"),
                                f"Pipeline error: {error_msg}",
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
                ),
                None,
                {"display": "block"},  # keep filter card visible if pipeline failed
            )

    @app.callback(
        Output("figures-container", "children"),
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
    def display_figures(
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
        """Display figures for selected experiment."""
        # Determine which experiment to show
        experiment_name = new_exp if new_exp else selected_exp

        if not experiment_name:
            return (
                html.Div(
                    [
                        html.I(className="fa fa-info-circle fa-3x text-muted mb-3"),
                        html.P(
                            "Select an experiment or upload data to view figures",
                            className="text-muted",
                        ),
                    ],
                    className="text-center py-5",
                ),
                {"display": "none"},  # hide averaged
                {"display": "none"},  # hide bgsub
                {"display": "none"},  # hide minmax
                {"display": "none"},  # hide deriv
                {"display": "none"},  # hide tm
            )

        # Determine which figure type to show
        triggered = callback_context.triggered_id

        # Determine figure type based on button clicks
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
        else:
            # Smart default: show raw if only raw data exists, otherwise averaged
            figure_type = "raw"  # always default to raw for safety

        try:
            # Load experiment context
            ctx = load_experiment_context(
                experiment_name, experiments_root=str(app.experiments_root)
            )

            # Check which data files exist to determine button visibility
            has_raw = (ctx.experiment_dir / StepFiles.INGESTED_DATA.value).exists()
            has_averaged = (ctx.experiment_dir / StepFiles.AVERAGED_DATA.value).exists()
            has_bgsub = (ctx.experiment_dir / StepFiles.BG_SUB_DATA.value).exists()
            has_minmax = (ctx.experiment_dir / StepFiles.MIN_MAX_SCALED_DATA.value).exists()
            has_deriv = (ctx.experiment_dir / StepFiles.DERIVATIVE_DATA.value).exists()
            has_tm = (ctx.experiment_dir / StepFiles.MIN_TEMPERATURES_DATA.value).exists()

            # Determine which buttons to show
            show_averaged = {"display": "inline-block"} if has_averaged else {"display": "none"}
            show_bgsub = {"display": "inline-block"} if has_bgsub else {"display": "none"}
            show_minmax = {"display": "inline-block"} if has_minmax else {"display": "none"}
            show_deriv = {"display": "inline-block"} if has_deriv else {"display": "none"}
            show_tm = {"display": "inline-block"} if has_tm else {"display": "none"}

            # Check which data files exist for the selected figure type
            required_files = {
                "raw": StepFiles.INGESTED_DATA.value,
                "averaged": StepFiles.AVERAGED_DATA.value,
                "bgsub": StepFiles.BG_SUB_DATA.value,
                "minmax": StepFiles.MIN_MAX_SCALED_DATA.value,
                "derivative": StepFiles.DERIVATIVE_DATA.value,
                "tm": StepFiles.MIN_TEMPERATURES_DATA.value,
            }

            if not (ctx.experiment_dir / required_files[figure_type]).exists():
                return (
                    html.Div(
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
                    ),
                    show_averaged,
                    show_bgsub,
                    show_minmax,
                    show_deriv,
                    show_tm,
                )

            # Generate figures using tested generators
            if figure_type == "raw":
                figures = list(raw_figure_generator(ctx))
            elif figure_type == "averaged":
                figures = list(processed_figure_generator(ctx, data_source="averaged_data"))
            elif figure_type == "bgsub":
                figures = list(processed_figure_generator(ctx, data_source="bg_subtracted_data"))
            elif figure_type == "minmax":
                figures = list(processed_figure_generator(ctx, data_source="min_max_scaled_data"))
            elif figure_type == "derivative":
                figures = list(processed_figure_generator(ctx, data_source="derivative_data"))
            elif figure_type == "tm":
                figures = list(min_temp_figure_generator(ctx))
            else:
                figures = []

            if not figures:
                return (
                    html.Div(
                        [
                            html.I(className="fa fa-chart-line fa-2x text-muted mb-3"),
                            html.P("No figures generated", className="text-muted"),
                        ],
                        className="text-center py-5",
                    ),
                    show_averaged,
                    show_bgsub,
                    show_minmax,
                    show_deriv,
                    show_tm,
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

            return (
                html.Div(figure_components),
                show_averaged,
                show_bgsub,
                show_minmax,
                show_deriv,
                show_tm,
            )

        except Exception as e:
            return (
                html.Div(
                    [
                        html.I(className="fa fa-exclamation-triangle fa-2x text-danger mb-3"),
                        html.P(f"Error loading figures: {e!s}", className="text-danger"),
                    ],
                    className="text-center py-5",
                ),
                {"display": "none"},  # hide averaged
                {"display": "none"},  # hide bgsub
                {"display": "none"},  # hide minmax
                {"display": "none"},  # hide deriv
                {"display": "none"},  # hide tm
            )
