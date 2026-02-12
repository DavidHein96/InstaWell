"""
Well filter callbacks.
"""

import json
import logging

import dash_bootstrap_components as dbc
from dash import ALL, Input, Output, State, callback_context, html
from dash.exceptions import PreventUpdate

from ..utils import get_well_grid_dimensions

logger = logging.getLogger("instawell.dash_app.well_filter")


def register_well_filter_callbacks(app, cache):
    """Register well filtering and button-enable callbacks."""

    @app.callback(
        Output("well-filter-content", "children"),
        Output("available-wells-store", "data"),
        Input("current-experiment-store", "data"),
        Input("selected-wells-grid", "data"),
        State("raw-data-store", "data"),
    )
    def populate_well_filter(exp_name, selected_wells, raw_data_key):
        """Populate well filter grid after setup completes."""
        if selected_wells is None:
            selected_wells = []
        if not exp_name or not raw_data_key:
            return (
                html.Div(
                    [
                        html.I(className="fa fa-info-circle fa-2x text-muted mb-2"),
                        html.P(
                            "Run setup to see available wells",
                            className="text-muted",
                        ),
                    ],
                    className="text-center py-4",
                ),
                [],
            )

        # Extract well names from raw data
        raw_df = cache.get(raw_data_key)
        if raw_df is None:
            logger.warning("Cache miss for raw data key %s", raw_data_key)
            return (
                html.Div(
                    [
                        html.I(className="fa fa-exclamation-triangle me-2"),
                        "Uploaded data has expired from cache. Please re-upload your files.",
                    ],
                    className="alert alert-warning text-center py-4",
                ),
                [],
            )
        well_columns = [col for col in raw_df.columns if col != "Temperature"]
        logger.info("Populating well filter: %d wells available", len(well_columns))

        if not well_columns:
            return html.Div(), []

        # Get grid dimensions
        rows, cols = get_well_grid_dimensions(well_columns)

        if not rows or not cols:
            # Fallback to simple list if can't parse well names
            return (
                html.Div(
                    [
                        html.Small(
                            f"{len(well_columns)} wells available",
                            className="text-muted",
                        ),
                        html.Div(
                            ", ".join(sorted(well_columns)),
                            className="font-monospace small mt-2",
                        ),
                    ]
                ),
                well_columns,
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
                            "border": "2px solid"
                            + (" #dc3545" if is_selected else " #ccc"),
                            "borderRadius": "4px",
                            "backgroundColor": "#495057"
                            if is_selected
                            else "#f8f9fa",
                            "color": "#fff" if is_selected else "#999",
                            "fontSize": "10px",
                            "fontWeight": "bold" if is_selected else "normal",
                            "cursor": "pointer",
                            "transition": "all 0.2s",
                            "boxShadow": "0 2px 4px rgba(0,0,0,0.2)"
                            if is_selected
                            else "none",
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

        return (
            html.Div(
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
                        [header_row, *grid_rows],
                        style={
                            "marginTop": "15px",
                            "display": "inline-block",
                            "padding": "10px",
                            "backgroundColor": "#fff",
                            "borderRadius": "8px",
                        },
                    ),
                ],
                className="well-filter-container",
            ),
            well_columns,
        )

    @app.callback(
        Output("selected-wells-grid", "data", allow_duplicate=True),
        Input("select-all-wells-btn", "n_clicks"),
        State("available-wells-store", "data"),
        prevent_initial_call=True,
    )
    def select_all_wells(n_clicks, available_wells):
        """Select all wells for filtering."""
        if not n_clicks or not available_wells:
            raise PreventUpdate
        return available_wells

    @app.callback(
        Output("selected-wells-grid", "data", allow_duplicate=True),
        Input("deselect-all-wells-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def deselect_all_wells(n_clicks):
        """Deselect all wells."""
        if not n_clicks:
            raise PreventUpdate
        return []

    @app.callback(
        Output("selected-wells-grid", "data"),
        Input({"type": "well-cell", "well": ALL}, "n_clicks"),
        State({"type": "well-cell", "well": ALL}, "id"),
        State("selected-wells-grid", "data"),
        prevent_initial_call=True,
    )
    def toggle_well_selection(n_clicks_list, id_list, selected_wells):
        """Toggle well selection when a well cell is clicked."""
        if not n_clicks_list or not id_list:
            raise PreventUpdate

        # Ignore initial render when all buttons have n_clicks=0
        if not any(n_clicks_list):
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
        try:
            triggered_dict = json.loads(triggered_id)
            clicked_well = triggered_dict["well"]
        except (json.JSONDecodeError, KeyError) as exc:
            raise PreventUpdate from exc

        # Toggle the well in selected list
        if selected_wells is None:
            selected_wells = []

        if clicked_well in selected_wells:
            selected_wells.remove(clicked_well)
        else:
            selected_wells.append(clicked_well)

        return selected_wells

    @app.callback(
        Output("filter-summary", "children"),
        Output("filtered-wells-store", "data"),
        Input("selected-wells-grid", "data"),
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
