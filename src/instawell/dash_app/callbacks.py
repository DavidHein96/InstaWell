"""
Dash callbacks for user interactions.
"""

import tempfile
import traceback
import uuid
from pathlib import Path

import dash_bootstrap_components as dbc
import pandas as pd
from dash import ALL, Input, Output, State, callback_context, dcc, html, no_update
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


def parse_well_name(well_name):
    """Parse well name like 'A1' into row letter and column number."""
    import re

    match = re.match(r"([A-Z]+)(\d+)", well_name.strip())
    if match:
        row_letter = match.group(1)
        col_number = int(match.group(2))
        return row_letter, col_number
    return None, None


def get_well_grid_dimensions(well_names):
    """Determine grid dimensions from well names."""
    rows = set()
    cols = set()

    for well in well_names:
        row, col = parse_well_name(well)
        if row and col:
            rows.add(row)
            cols.add(col)

    if not rows or not cols:
        return [], []

    # Sort rows alphabetically, cols numerically
    sorted_rows = sorted(rows)
    sorted_cols = sorted(cols)

    return sorted_rows, sorted_cols


def register_callbacks(app):  # noqa: C901
    """Register all callbacks for the app."""
    cache = app.cache

    @app.callback(
        Output("session-id", "data"),
        Input("session-id", "data"),
    )
    def assign_session_id(session_id):
        """Assign a unique session ID if one doesn't exist."""
        if session_id is None:
            session_id = str(uuid.uuid4())
        return session_id

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
            # Closing
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
        Input("pipeline-status", "children"),
        Input("clear-experiment-btn", "n_clicks"),
        State("experiment-dropdown", "value"),
        prevent_initial_call="initial_duplicate",
    )
    def refresh_experiments(n_refresh, pipeline_status, n_clear, current_value):
        """Refresh the list of experiments or clear selection."""
        experiments = get_experiment_list(app.experiments_root)
        options = [{"label": name, "value": name} for name in experiments]

        # If triggered by clearing pipeline status (empty), don't reload
        if callback_context.triggered_id == "pipeline-status" and not pipeline_status:
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

        # If pipeline just completed successfully, select the new experiment
        if callback_context.triggered_id == "pipeline-status" and pipeline_status:
            if isinstance(pipeline_status, dict) and "props" in pipeline_status:
                children = pipeline_status["props"].get("children", [])
                if children and "Pipeline complete for" in str(children):
                    # Extract experiment name from success message
                    for child in children:
                        if isinstance(child, str) and "'" in child:
                            exp_name = child.split("'")[1]
                            if exp_name in experiments:
                                return (
                                    options,
                                    exp_name,
                                    no_update,  # Don't change stores
                                    no_update,
                                    no_update,
                                    no_update,
                                    no_update,
                                    no_update,
                                    no_update,
                                    no_update,
                                    no_update,
                                    no_update,
                                    no_update,
                                    no_update,
                                    no_update,
                                    no_update,
                                )

        # Keep current selection if it still exists (refresh button)
        if current_value and current_value in experiments:
            return (
                options,
                current_value,
                no_update,  # Don't change stores
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
            )

        # Otherwise select first experiment or None
        return (
            options,
            experiments[0] if experiments else None,
            no_update,  # Don't change stores
            no_update,
            no_update,
            no_update,
            no_update,
            no_update,
            no_update,
            no_update,
            no_update,
            no_update,
            no_update,
            no_update,
            no_update,
            no_update,
        )

    @app.callback(
        Output("experiment-info", "children"),
        Input("experiment-dropdown", "value"),
        Input(
            "pipeline-status", "children"
        ),  # Add trigger to update when pipeline completes
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
                html.Span(
                    f"{total_conditions} conditions", className="text-muted small"
                ),
            ]
        )

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
        if contents is None:
            return "", None

        try:
            # Ensure session_id is valid
            if session_id is None:
                session_id = str(uuid.uuid4())

            df = parse_upload(contents, filename)
            if "Temperature" not in df.columns:
                return (
                    html.Span(
                        "Error: Missing 'Temperature' column", className="text-danger"
                    ),
                    None,
                )

            # Cache the dataframe
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

            return (
                html.Span(
                    [html.I(className="fa fa-check-circle me-1"), f"Loaded: {filename}"],
                    className="text-success",
                ),
                cache_key,  # Return key instead of data
            )
        except Exception as e:
            return html.Span(f"Error: {e!s}", className="text-danger"), None

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
        if contents is None:
            return "", None

        try:
            # Ensure session_id is valid
            if session_id is None:
                session_id = str(uuid.uuid4())

            df = parse_upload(contents, filename)
            has_well_col = any("well" in col.lower() for col in df.columns)
            if not has_well_col:
                return (
                    html.Span("Error: Missing well column", className="text-danger"),
                    None,
                )

            # Cache the dataframe
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

            return (
                html.Span(
                    [html.I(className="fa fa-check-circle me-1"), f"Loaded: {filename}"],
                    className="text-success",
                ),
                cache_key,  # Return key instead of data
            )
        except Exception as e:
            return html.Span(f"Error: {e!s}", className="text-danger"), None

    @app.callback(
        Output("well-filter-content", "children"),
        Input("current-experiment-store", "data"),
        Input("selected-wells-grid", "data"),
        State("raw-data-store", "data"),
    )
    def populate_well_filter(exp_name, selected_wells, raw_data_key):
        """Populate well filter grid after setup completes."""
        if selected_wells is None:
            selected_wells = []
        if not exp_name or not raw_data_key:
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
        raw_df = cache.get(raw_data_key)
        if raw_df is None:
            return html.Div(
                [
                    html.I(className="fa fa-exclamation-triangle me-2"),
                    "Uploaded data has expired from cache. Please re-upload your files.",
                ],
                className="alert alert-warning text-center py-4",
            )
        well_columns = [col for col in raw_df.columns if col != "Temperature"]

        if not well_columns:
            return html.Div()

        # Get grid dimensions
        rows, cols = get_well_grid_dimensions(well_columns)

        if not rows or not cols:
            # Fallback to checklist if can't parse well names
            well_options = [
                {"label": well, "value": well} for well in sorted(well_columns)
            ]
            return html.Div(
                [
                    dbc.Checklist(
                        id="wells-to-filter-checklist",
                        options=well_options,
                        value=[],
                        inline=False,
                    ),
                ]
            )

        # Create well plate grid
        # Header row with column numbers
        header_cells = [html.Div("", style={"width": "40px"})]  # Empty corner cell
        for col in cols:
            header_cells.append(
                html.Div(
                    str(col),
                    style={
                        "width": "45px",
                        "textAlign": "center",
                        "fontWeight": "bold",
                        "fontSize": "12px",
                        "color": "#666",
                    },
                )
            )

        header_row = html.Div(
            header_cells,
            style={"display": "flex", "marginBottom": "5px"},
        )

        # Grid rows
        grid_rows = []
        for row in rows:
            # Row label
            row_cells = [
                html.Div(
                    row,
                    style={
                        "width": "40px",
                        "textAlign": "center",
                        "fontWeight": "bold",
                        "fontSize": "12px",
                        "color": "#666",
                        "lineHeight": "45px",
                    },
                )
            ]

            # Well cells for this row
            for col in cols:
                well_name = f"{row}{col}"
                if well_name in well_columns:
                    # Determine if this well is selected
                    is_selected = well_name in selected_wells

                    # Create clickable well button with conditional styling
                    cell = html.Button(
                        well_name,
                        id={"type": "well-cell", "well": well_name},
                        n_clicks=0,
                        style={
                            "width": "45px",
                            "height": "45px",
                            "margin": "2px",
                            "border": "2px solid" + (" #dc3545" if is_selected else " #ccc"),
                            "borderRadius": "4px",
                            "backgroundColor": "#495057" if is_selected else "#f8f9fa",
                            "color": "#fff" if is_selected else "#999",
                            "fontSize": "10px",
                            "fontWeight": "bold" if is_selected else "normal",
                            "cursor": "pointer",
                            "transition": "all 0.2s",
                            "boxShadow": "0 2px 4px rgba(0,0,0,0.2)" if is_selected else "none",
                        },
                    )
                else:
                    # Empty cell (well doesn't exist in data)
                    cell = html.Div(
                        style={
                            "width": "45px",
                            "height": "45px",
                            "margin": "2px",
                        }
                    )
                row_cells.append(cell)

            grid_rows.append(
                html.Div(
                    row_cells,
                    style={"display": "flex", "marginBottom": "2px"},
                )
            )

        return html.Div(
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
                html.Div(
                    [header_row] + grid_rows,
                    style={
                        "marginTop": "15px",
                        "display": "inline-block",
                        "padding": "10px",
                        "backgroundColor": "#fff",
                        "borderRadius": "8px",
                    },
                ),
                # Hidden checklist to maintain compatibility with existing callbacks
                dbc.Checklist(
                    id="wells-to-filter-checklist",
                    options=[{"label": w, "value": w} for w in well_columns],
                    value=[],
                    style={"display": "none"},
                ),
            ],
            className="well-filter-container",
        )

    @app.callback(
        Output("wells-to-filter-checklist", "value", allow_duplicate=True),
        Output("selected-wells-grid", "data", allow_duplicate=True),
        Input("select-all-wells-btn", "n_clicks"),
        State("wells-to-filter-checklist", "options"),
        prevent_initial_call=True,
    )
    def select_all_wells(n_clicks, options):
        """Select all wells for filtering."""
        if not n_clicks or not options:
            raise PreventUpdate
        all_wells = [opt["value"] for opt in options]
        return all_wells, all_wells

    @app.callback(
        Output("wells-to-filter-checklist", "value", allow_duplicate=True),
        Output("selected-wells-grid", "data", allow_duplicate=True),
        Input("deselect-all-wells-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def deselect_all_wells(n_clicks):
        """Deselect all wells."""
        if not n_clicks:
            raise PreventUpdate
        return [], []

    @app.callback(
        Output("selected-wells-grid", "data"),
        Output("wells-to-filter-checklist", "value", allow_duplicate=True),
        Input({"type": "well-cell", "well": ALL}, "n_clicks"),
        State({"type": "well-cell", "well": ALL}, "id"),
        State("selected-wells-grid", "data"),
        prevent_initial_call=True,
    )
    def toggle_well_selection(n_clicks_list, id_list, selected_wells):
        """Toggle well selection when a well cell is clicked."""
        if not n_clicks_list or not id_list:
            raise PreventUpdate

        # Find which button was clicked (n_clicks changed)
        ctx = callback_context
        if not ctx.triggered:
            raise PreventUpdate

        # Get the triggered input
        triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]
        if not triggered_id:
            raise PreventUpdate

        # Parse the triggered ID to get the well name
        import json

        try:
            triggered_dict = json.loads(triggered_id)
            clicked_well = triggered_dict["well"]
        except (json.JSONDecodeError, KeyError):
            raise PreventUpdate

        # Toggle the well in selected list
        if selected_wells is None:
            selected_wells = []

        if clicked_well in selected_wells:
            selected_wells.remove(clicked_well)
        else:
            selected_wells.append(clicked_well)

        return selected_wells, selected_wells

    @app.callback(
        Output("filter-summary", "children"),
        Output("filtered-wells-store", "data"),
        Input("wells-to-filter-checklist", "value"),
    )
    def update_filter_summary(selected_wells):
        """Update summary of filtered wells."""
        if not selected_wells:
            return (
                html.Span(
                    [
                        html.I(className="fa fa-check-circle text-success me-2"),
                        "No wells will be filtered - all wells will be included in analysis",
                    ],
                    className="text-success",
                ),
                [],
            )

        wells_str = ", ".join(sorted(selected_wells))
        return (
            html.Span(
                [
                    html.I(
                        className="fa fa-exclamation-triangle text-warning me-2"
                    ),
                    html.Strong(f"{len(selected_wells)} wells will be excluded: "),
                    html.Span(wells_str, className="font-monospace"),
                ],
                className="text-warning",
            ),
            selected_wells,
        )

    @app.callback(
        Output("setup-ingest-btn", "disabled"),
        Output("validate-layout-btn", "disabled"),
        Input("raw-data-store", "data"),
        Input("layout-data-store", "data"),
        Input("experiment-name-input", "value"),
    )
    def enable_setup_button(raw_data_key, layout_data_key, exp_name):
        """Enable buttons when required inputs are present."""
        has_uploads = bool(raw_data_key) and bool(layout_data_key)
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
        raw_data_key,
        layout_data_key,
        separator,
        fields_str,
        empty_placeholder,
        temperature_column,
    ):
        """Validate uploaded raw/layout files against provided parsing settings."""
        if not n_clicks:
            raise PreventUpdate

        if not raw_data_key or not layout_data_key:
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
            if not separator or len(separator) != 1:
                raise ValueError("Condition separator must be exactly one character.")
            if not empty_placeholder or len(empty_placeholder) != 1:
                raise ValueError(
                    "Missing condition placeholder must be exactly one character."
                )
            if separator == empty_placeholder:
                raise ValueError(
                    "Separator and placeholder must be different characters."
                )

            layout_df = cache.get(layout_data_key)
            raw_df = cache.get(raw_data_key)

            if layout_df is None or raw_df is None:
                return html.Div(
                    "Uploaded data has expired from cache. Please upload again.",
                    className="alert alert-danger",
                )

            temp_col = (temperature_column or "Temperature").strip()
            if temp_col not in raw_df.columns:
                match = next(
                    (c for c in raw_df.columns if c.lower() == temp_col.lower()),
                    None,
                )
                if match:
                    temp_col = match
                else:
                    raise ValueError(
                        f"Raw data is missing temperature column '{temp_col}'."
                    )

            well_cols = [c for c in layout_df.columns if c.lower().startswith("well")]
            if not well_cols:
                raise ValueError(
                    "Layout file must contain a column starting with 'Well'."
                )
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
        raw_data_key,
        layout_data_key,
        exp_name,
        separator,
        fields_str,
        empty_placeholder,
        npc_marker,
    ):
        """Run setup and ingest steps only."""
        if not n_clicks:
            raise PreventUpdate

        raw_df = cache.get(raw_data_key)
        layout_df = cache.get(layout_data_key)

        if raw_df is None or layout_df is None:
            return (
                html.Div(
                    "Uploaded data has expired from cache. Please upload again.",
                    className="alert alert-danger",
                ),
                None,
                False,
                {"display": "none"},
            )

        try:
            # Parse fields
            fields = tuple(f.strip() for f in fields_str.split(",") if f.strip())
            sep = (separator or "|").strip() or "|"
            placeholder = (empty_placeholder or "^").strip() or "^"
            npc = (npc_marker or "NPC").strip() or "NPC"

            # Save data to temp files (auto-cleaned)
            with tempfile.TemporaryDirectory(
                prefix="instawell_uploads_"
            ) as tmp_dir:
                temp_dir_path = Path(tmp_dir)

                raw_path = temp_dir_path / f"{exp_name}_raw.csv"
                layout_path = temp_dir_path / f"{exp_name}_layout.csv"

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
                        "Review the raw data figures, filter wells, then 'Run Full Pipeline'.",
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
            ctx = load_experiment_context(
                exp_name, experiments_root=str(app.experiments_root)
            )

            # Step 3: Filter wells (use selected wells from UI)
            filter_wells(ctx, wells_to_filter=wells_to_filter or [])

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
                        f"Pipeline complete for '{exp_name}'! All processing steps finished.",
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

        if not experiment_name:
            return (
                None,  # No figures to store
                0,  # Reset index
                {"display": "none"},
                {"display": "none"},
                {"display": "none"},
                {"display": "none"},
                {"display": "none"},
            )

        # Determine which figure type to show
        triggered = callback_context.triggered_id or "fig-btn-raw"

        figure_type_map = {
            "fig-btn-raw": "raw",
            "fig-btn-averaged": "averaged",
            "fig-btn-bgsub": "bgsub",
            "fig-btn-minmax": "minmax",
            "fig-btn-deriv": "derivative",
            "fig-btn-tm": "tm",
        }
        figure_type = figure_type_map.get(triggered, "raw")

        try:
            ctx = load_experiment_context(
                experiment_name, experiments_root=str(app.experiments_root)
            )

            # Check which data files exist
            step_files = {
                "raw": StepFiles.INGESTED_DATA,
                "averaged": StepFiles.AVERAGED_DATA,
                "bgsub": StepFiles.BG_SUB_DATA,
                "minmax": StepFiles.MIN_MAX_SCALED_DATA,
                "derivative": StepFiles.DERIVATIVE_DATA,
                "tm": StepFiles.MIN_TEMPERATURES_DATA,
            }
            visibility = {
                f"show_{key}": {
                    "display": "inline-block"
                    if (ctx.experiment_dir / step.value).exists()
                    else "none"
                }
                for key, step in step_files.items()
                if key != "raw"
            }

            required_file = ctx.experiment_dir / step_files[figure_type].value
            if not required_file.exists():
                return (
                    None,  # No figures to store
                    0,  # Reset index
                    visibility["show_averaged"],
                    visibility["show_bgsub"],
                    visibility["show_minmax"],
                    visibility["show_derivative"],
                    visibility["show_tm"],
                )

            # Generate figures
            generators = {
                "raw": raw_figure_generator,
                "averaged": lambda c: processed_figure_generator(
                    c, data_source="averaged_data"
                ),
                "bgsub": lambda c: processed_figure_generator(
                    c, data_source="bg_subtracted_data"
                ),
                "minmax": lambda c: processed_figure_generator(
                    c, data_source="min_max_scaled_data"
                ),
                "derivative": lambda c: processed_figure_generator(
                    c, data_source="derivative_data"
                ),
                "tm": min_temp_figure_generator,
            }
            figures = list(generators[figure_type](ctx))

            if not figures:
                return (
                    None,  # No figures to store
                    0,  # Reset index
                    visibility["show_averaged"],
                    visibility["show_bgsub"],
                    visibility["show_minmax"],
                    visibility["show_derivative"],
                    visibility["show_tm"],
                )

            # Extract titles and serialize figures
            figures_data = []
            for i, fig in enumerate(figures, start=1):
                # Extract title from figure
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
                    pass

                figures_data.append({"title": title, "figure": fig.to_dict()})

            return (
                figures_data,  # Store figures as serializable data
                0,  # Reset to first figure
                visibility["show_averaged"],
                visibility["show_bgsub"],
                visibility["show_minmax"],
                visibility["show_derivative"],
                visibility["show_tm"],
            )

        except Exception as e:
            return (
                None,  # No figures on error
                0,  # Reset index
                {"display": "none"},
                {"display": "none"},
                {"display": "none"},
                {"display": "none"},
                {"display": "none"},
            )

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
