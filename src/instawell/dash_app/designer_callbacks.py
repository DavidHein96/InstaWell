"""
Callbacks for the layout designer.
"""

import io
from typing import List

import pandas as pd
from dash import Input, Output, State, html, no_update
from dash.exceptions import PreventUpdate

from .designer import (
    WELL_PATTERN,
    create_plate_grid,
    get_row_labels,
    infer_plate_from_raw,
    normalize_well,
    PLATE_TYPES,
)
from .utils import parse_upload


def register_designer_callbacks(app):
    """Register all designer callbacks."""

    @app.callback(
        Output("designer-collapse", "is_open"),
        Output("designer-toggle-btn", "children"),
        Input("designer-toggle-btn", "n_clicks"),
        State("designer-collapse", "is_open"),
        prevent_initial_call=True,
    )
    def toggle_designer(n_clicks, is_open):
        """Toggle designer visibility."""
        if n_clicks is None:
            raise PreventUpdate

        new_state = not is_open
        button_text = "Hide Designer" if new_state else "Show Designer"
        return new_state, button_text

    @app.callback(
        Output("designer-state", "data", allow_duplicate=True),
        Input("designer-plate-type", "value"),
        State("designer-state", "data"),
        prevent_initial_call=True,
    )
    def change_plate_type(plate_type, state):
        """Update plate type in state."""
        new_state = dict(state)
        new_state["plate_type"] = plate_type
        return new_state

    @app.callback(
        Output("designer-state", "data", allow_duplicate=True),
        Input("designer-raw-upload", "contents"),
        State("designer-raw-upload", "filename"),
        State("designer-state", "data"),
        prevent_initial_call=True,
    )
    def import_from_raw(contents, filename, state):
        """Import available wells from raw CSV."""
        if contents is None:
            raise PreventUpdate

        try:
            raw_df = parse_upload(contents, filename)
            plate_type, _, _, available_wells = infer_plate_from_raw(raw_df)

            new_state = dict(state)
            new_state["plate_type"] = plate_type
            new_state["available_wells"] = available_wells
            return new_state
        except Exception:
            # Silently fail - user can still use designer without import
            return no_update

    @app.callback(
        Output("designer-grid-container", "children"),
        Input("designer-state", "data"),
    )
    def render_grid(state):
        """Render the plate grid."""
        return create_plate_grid(
            state["plate_type"],
            state.get("cells", {}),
            state.get("available_wells", []),
        )

    @app.callback(
        Output("designer-selected-wells", "data"),
        Input("designer-plate-grid", "selected_cells"),
        State("designer-state", "data"),
    )
    def update_selected_wells(selected_cells, state):
        """Convert table selection to well names."""
        if not selected_cells:
            return []

        plate_type = state["plate_type"]
        rows, cols = PLATE_TYPES[plate_type]
        row_labels = get_row_labels(rows)

        wells = []
        for cell in selected_cells:
            row_idx = cell.get("row")
            col_id = cell.get("column_id")

            # Skip if Well column or invalid
            if (
                col_id is None
                or col_id == "Well"
                or row_idx is None
                or row_idx >= len(row_labels)
            ):
                continue

            try:
                col_num = int(col_id)
                row_label = row_labels[row_idx]
                well_name = f"{row_label}{col_num}"
                wells.append(well_name)
            except (ValueError, IndexError):
                continue

        return sorted(set(wells))

    @app.callback(
        Output("designer-selected-wells-display", "children"),
        Output("designer-assign-btn", "disabled"),
        Output("designer-clear-btn", "disabled"),
        Input("designer-selected-wells", "data"),
    )
    def update_selection_display(selected_wells):
        """Display selected wells and enable/disable buttons."""
        if not selected_wells:
            return "No wells selected", True, True

        wells_str = ", ".join(selected_wells)
        display = html.Span(
            [
                html.Strong(f"{len(selected_wells)} wells selected: "),
                html.Span(wells_str, className="font-monospace"),
            ]
        )
        return display, False, False

    @app.callback(
        Output("designer-state", "data", allow_duplicate=True),
        Output("designer-concentration", "value"),
        Output("designer-ligand", "value"),
        Output("designer-protein", "value"),
        Output("designer-buffer", "value"),
        Input("designer-assign-btn", "n_clicks"),
        State("designer-selected-wells", "data"),
        State("designer-concentration", "value"),
        State("designer-unit", "value"),
        State("designer-ligand", "value"),
        State("designer-protein", "value"),
        State("designer-buffer", "value"),
        State("designer-state", "data"),
        prevent_initial_call=True,
    )
    def assign_condition(
        n_clicks, selected_wells, concentration, unit, ligand, protein, buffer, state
    ):
        """Assign condition to selected wells."""
        if not n_clicks or not selected_wells:
            raise PreventUpdate

        # Validate inputs
        if not all([concentration, ligand, protein, buffer]):
            raise PreventUpdate

        # Update state
        new_state = dict(state)
        cells = dict(new_state.get("cells", {}))

        condition = {
            "concentration": concentration,
            "unit": unit,
            "ligand": ligand.strip(),
            "protein": protein.strip(),
            "buffer": buffer.strip(),
        }

        for well in selected_wells:
            cells[well] = condition

        new_state["cells"] = cells

        # Clear form
        return new_state, None, "", "", ""

    @app.callback(
        Output("designer-state", "data", allow_duplicate=True),
        Input("designer-clear-btn", "n_clicks"),
        State("designer-selected-wells", "data"),
        State("designer-state", "data"),
        prevent_initial_call=True,
    )
    def clear_selected_wells(n_clicks, selected_wells, state):
        """Clear conditions from selected wells."""
        if not n_clicks or not selected_wells:
            raise PreventUpdate

        new_state = dict(state)
        cells = dict(new_state.get("cells", {}))

        for well in selected_wells:
            if well in cells:
                del cells[well]

        new_state["cells"] = cells
        return new_state

    @app.callback(
        Output("designer-state", "data", allow_duplicate=True),
        Input("designer-reset-btn", "n_clicks"),
        State("designer-state", "data"),
        prevent_initial_call=True,
    )
    def reset_all(n_clicks, state):
        """Reset all cell assignments."""
        if not n_clicks:
            raise PreventUpdate

        new_state = dict(state)
        new_state["cells"] = {}
        return new_state

    @app.callback(
        Output("designer-download", "data"),
        Input("designer-export-btn", "n_clicks"),
        State("designer-state", "data"),
        prevent_initial_call=True,
    )
    def export_layout(n_clicks, state):
        """Export layout to CSV."""
        if not n_clicks:
            raise PreventUpdate

        cells = state.get("cells", {})
        if not cells:
            raise PreventUpdate

        plate_type = state["plate_type"]
        rows, cols = PLATE_TYPES[plate_type]
        row_labels = get_row_labels(rows)

        # Build layout dataframe
        data = []
        for row_label in row_labels:
            row_data = {"Well": row_label}
            for col_num in range(1, cols + 1):
                well_name = f"{row_label}{col_num}"
                if well_name in cells:
                    cond = cells[well_name]
                    # Format: concentration_ligand_protein_buffer
                    # e.g., "10uM_ATP_Protein1_Buffer1"
                    condition_str = f"{cond['concentration']}{cond['unit']}_{cond['ligand']}_{cond['protein']}_{cond['buffer']}"
                    row_data[str(col_num)] = condition_str
                else:
                    row_data[str(col_num)] = ""
            data.append(row_data)

        df = pd.DataFrame(data)

        # Convert to CSV
        csv_string = df.to_csv(index=False)

        return dict(content=csv_string, filename="layout.csv")
