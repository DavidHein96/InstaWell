"""
Visual plate layout designer for creating layout CSV files.

Allows users to interactively design their plate layouts by selecting wells
and assigning conditions.
"""

import string
from typing import Dict, List, Tuple

import dash_bootstrap_components as dbc
import pandas as pd
from dash import dash_table, dcc, html

from .utils import WELL_PATTERN, normalize_well

# Plate configurations
PLATE_TYPES = {
    "96": (8, 12),  # 8 rows, 12 columns
    "384": (16, 24),  # 16 rows, 24 columns
}

DESIGNER_FIELDS = ("concentration", "ligand", "protein", "buffer")


def get_row_labels(n_rows: int) -> List[str]:
    """Get row labels (A, B, C, ...)."""
    return list(string.ascii_uppercase[:n_rows])


def infer_plate_from_raw(raw_df: pd.DataFrame) -> Tuple[str, int, int, List[str]]:
    """
    Infer plate type and available wells from raw data columns.

    Args:
        raw_df: Raw data DataFrame with well names as columns

    Returns:
        Tuple of (plate_type, rows, cols, available_wells)
    """
    wells = []
    max_row = "A"
    max_col = 1

    for col in raw_df.columns:
        if col == "Temperature":
            continue
        well = normalize_well(col)
        wells.append(well)

        match = WELL_PATTERN.match(well)
        if match:
            row = match.group(1).upper()
            col_num = int(match.group(2))
            max_row = max(max_row, row)
            max_col = max(max_col, col_num)

    # Determine plate type
    rows_needed = ord(max_row) - ord("A") + 1
    cols_needed = max_col

    max_96_rows, max_96_cols = PLATE_TYPES["96"]
    plate_type = "96" if rows_needed <= max_96_rows and cols_needed <= max_96_cols else "384"

    rows, cols = PLATE_TYPES[plate_type]
    return plate_type, rows, cols, sorted(set(wells))


def create_plate_grid(
    plate_type: str,
    cells: Dict[str, Dict],
    available_wells: List[str] | None = None,
) -> html.Div:
    """
    Create an interactive plate grid using Dash DataTable.

    Args:
        plate_type: '96' or '384'
        cells: Dict mapping well names to condition dicts
        available_wells: List of wells that have data (highlighted)

    Returns:
        Dash HTML div containing the grid
    """
    rows, cols = PLATE_TYPES.get(plate_type, PLATE_TYPES["96"])
    row_labels = get_row_labels(rows)

    # Create table data and tooltips
    data = []
    tooltip_data = []
    for row_label in row_labels:
        row_data = {"Well": row_label}
        tooltip_row = {"Well": row_label}
        for col_num in range(1, cols + 1):
            well_name = f"{row_label}{col_num}"
            col_id = str(col_num)
            if well_name in cells:
                cond = cells[well_name]
                # Display: show only concentration
                display_text = f"{cond.get('concentration', '')}{cond.get('unit', '')}"
                row_data[col_id] = display_text.strip()

                # Tooltip: show full details
                tooltip_text = (
                    f"Concentration: {cond.get('concentration', '')}{cond.get('unit', '')}\n"
                    f"Ligand: {cond.get('ligand', '')}\n"
                    f"Protein: {cond.get('protein', '')}\n"
                    f"Buffer: {cond.get('buffer', '')}"
                )
                tooltip_row[col_id] = tooltip_text
            else:
                row_data[col_id] = ""
                tooltip_row[col_id] = ""
        data.append(row_data)
        tooltip_data.append(tooltip_row)

    # Column definitions
    columns = [{"name": "Well", "id": "Well"}]
    columns += [{"name": str(i), "id": str(i)} for i in range(1, cols + 1)]

    # Styling for available wells (if raw data provided) and filled cells
    style_data_conditional = []

    # Style for filled cells (has condition assigned)
    for _row_idx, row_label in enumerate(row_labels):
        for col_num in range(1, cols + 1):
            well_name = f"{row_label}{col_num}"
            col_id = str(col_num)
            if well_name in cells:
                style_data_conditional.append(
                    {
                        "if": {
                            "filter_query": f'{{Well}} = "{row_label}"',
                            "column_id": col_id,
                        },
                        "backgroundColor": "rgba(40, 167, 69, 0.15)",  # Light green for filled
                        "border": "1px solid rgba(40, 167, 69, 0.4)",
                        "fontWeight": "bold",
                    }
                )

    # Style for available wells (if raw data provided) - only if not already filled
    if available_wells:
        for well in available_wells:
            match = WELL_PATTERN.match(well)
            if not match:
                continue
            row_label = match.group(1).upper()
            col_id = str(int(match.group(2)))

            if row_label in row_labels and f"{row_label}{col_id}" not in cells:
                style_data_conditional.append(
                    {
                        "if": {
                            "filter_query": f'{{Well}} = "{row_label}"',
                            "column_id": col_id,
                        },
                        "backgroundColor": "rgba(13, 110, 253, 0.1)",
                        "border": "1px solid rgba(13, 110, 253, 0.3)",
                    }
                )

    # Create DataTable
    table = dash_table.DataTable(
        id="designer-plate-grid",
        data=data,
        columns=columns,
        tooltip_data=tooltip_data,
        tooltip_duration=None,  # Tooltip stays until mouse leaves
        selected_cells=[],
        cell_selectable=True,
        editable=False,
        style_as_list_view=True,
        style_table={"maxHeight": "60vh", "overflowY": "auto", "overflowX": "auto"},
        fixed_rows={"headers": True},
        style_cell={
            "textAlign": "center",
            "padding": "6px",
            "fontSize": "12px",
            "minWidth": "80px",
            "width": "80px",
            "maxWidth": "80px",
            "whiteSpace": "nowrap",
            "overflow": "hidden",
            "textOverflow": "ellipsis",
        },
        style_header={
            "backgroundColor": "rgb(248, 249, 250)",
            "fontWeight": "bold",
        },
        style_data_conditional=[
            *style_data_conditional,
            {
                "if": {"column_id": "Well"},
                "backgroundColor": "rgb(248, 249, 250)",
                "fontWeight": "bold",
            },
        ],
        css=[
            {
                "selector": ".dash-spreadsheet td.cell--selected",
                "rule": "background-color: rgba(13, 110, 253, 0.25) !important;",
            },
            {
                "selector": ".dash-table-tooltip",
                "rule": "background-color: rgba(0, 0, 0, 0.9) !important; color: white; font-size: 12px; padding: 8px; border-radius: 4px;",
            },
        ],
    )

    return html.Div(
        [
            table,
            html.Small(
                "Hold Shift and click to select multiple wells, then assign conditions below. Hover over filled wells to see full details.",
                className="text-muted mt-2 d-block",
            ),
        ]
    )


def designer_card():
    """Create the layout designer UI card."""
    return dbc.Card(
        [
            dbc.CardHeader(
                dbc.Row(
                    [
                        dbc.Col(
                            html.H5(
                                [html.I(className="fa fa-th me-2"), "Layout Designer"],
                                className="mb-0",
                            ),
                            width="auto",
                        ),
                        dbc.Col(
                            dbc.Button(
                                "Show Designer",
                                id="designer-toggle-btn",
                                color="primary",
                                size="sm",
                                outline=False,
                            ),
                            className="text-end",
                        ),
                    ],
                    align="center",
                )
            ),
            dbc.Collapse(
                dbc.CardBody(
                    [
                        # Stores for state management
                        dcc.Store(
                            id="designer-state",
                            data={
                                "plate_type": "96",
                                "cells": {},  # {well_name: {concentration, unit, ligand, protein, buffer}}
                                "available_wells": [],
                            },
                        ),
                        dcc.Store(id="designer-selected-wells", data=[]),
                        # Controls row
                        dbc.Row(
                            [
                                dbc.Col(
                                    [
                                        html.Label("Plate Type", className="fw-bold"),
                                        dcc.Dropdown(
                                            id="designer-plate-type",
                                            options=[
                                                {"label": "96-well", "value": "96"},
                                                {"label": "384-well", "value": "384"},
                                            ],
                                            value="96",
                                            clearable=False,
                                        ),
                                    ],
                                    width=12,
                                    md=3,
                                    className="mb-3",
                                ),
                                dbc.Col(
                                    [
                                        html.Label(
                                            "Import from Raw CSV (optional)",
                                            className="fw-bold",
                                        ),
                                        dcc.Upload(
                                            id="designer-raw-upload",
                                            children=html.Div(
                                                [
                                                    html.I(className="fa fa-file-csv me-2"),
                                                    "Click to import wells from raw.csv",
                                                ],
                                                className="text-center",
                                            ),
                                            style={
                                                "width": "100%",
                                                "height": "38px",
                                                "lineHeight": "38px",
                                                "borderWidth": "1px",
                                                "borderStyle": "dashed",
                                                "borderRadius": "5px",
                                                "textAlign": "center",
                                                "cursor": "pointer",
                                            },
                                            multiple=False,
                                        ),
                                    ],
                                    width=12,
                                    md=9,
                                    className="mb-3",
                                ),
                            ]
                        ),
                        dbc.Row(
                            [
                                dbc.Col(
                                    [
                                        html.Label("Condition Separator", className="fw-bold"),
                                        dbc.Input(
                                            id="designer-separator-input",
                                            value="|",
                                            maxLength=1,
                                            type="text",
                                        ),
                                    ],
                                    width=12,
                                    md=3,
                                    className="mb-3",
                                ),
                                dbc.Col(
                                    [
                                        html.Label(
                                            "Missing Condition Placeholder", className="fw-bold"
                                        ),
                                        dbc.Input(
                                            id="designer-placeholder-input",
                                            value="^",
                                            maxLength=1,
                                            type="text",
                                        ),
                                        html.Small(
                                            "Used for unfilled wells when exporting",
                                            className="text-muted",
                                        ),
                                    ],
                                    width=12,
                                    md=3,
                                    className="mb-3",
                                ),
                            ]
                        ),
                        # Plate grid
                        html.Div(id="designer-grid-container", className="mb-3"),
                        html.Hr(),
                        # Condition assignment form
                        html.Div(
                            [
                                dbc.Row(
                                    [
                                        dbc.Col(
                                            html.H6("Assign Condition to Selected Wells"),
                                            width="auto",
                                        ),
                                        dbc.Col(
                                            dbc.Button(
                                                [
                                                    html.I(className="fa fa-copy me-2"),
                                                    "Copy from Selected Well",
                                                ],
                                                id="designer-copy-btn",
                                                color="info",
                                                size="sm",
                                                outline=True,
                                                disabled=True,
                                            ),
                                            className="text-end",
                                        ),
                                    ],
                                    className="mb-2",
                                ),
                                html.Div(
                                    id="designer-selected-wells-display",
                                    className="mb-2 small text-muted",
                                ),
                                dbc.Row(
                                    [
                                        dbc.Col(
                                            [
                                                html.Label("Concentration"),
                                                dbc.InputGroup(
                                                    [
                                                        dbc.Input(
                                                            id="designer-concentration",
                                                            type="number",
                                                            placeholder="e.g. 10",
                                                        ),
                                                        dbc.Select(
                                                            id="designer-unit",
                                                            options=[
                                                                {"label": "nM", "value": "nM"},
                                                                {"label": "uM", "value": "uM"},
                                                                {"label": "mM", "value": "mM"},
                                                            ],
                                                            value="uM",
                                                        ),
                                                    ]
                                                ),
                                            ],
                                            width=12,
                                            md=3,
                                            className="mb-3",
                                        ),
                                        dbc.Col(
                                            [
                                                html.Label("Ligand"),
                                                dbc.Input(
                                                    id="designer-ligand",
                                                    placeholder="e.g. ATP",
                                                ),
                                            ],
                                            width=12,
                                            md=3,
                                            className="mb-3",
                                        ),
                                        dbc.Col(
                                            [
                                                html.Label("Protein"),
                                                dbc.Input(
                                                    id="designer-protein",
                                                    placeholder="e.g. Protein1 or NPC",
                                                ),
                                            ],
                                            width=12,
                                            md=3,
                                            className="mb-3",
                                        ),
                                        dbc.Col(
                                            [
                                                html.Label("Buffer"),
                                                dbc.Input(
                                                    id="designer-buffer",
                                                    placeholder="e.g. Buffer1",
                                                ),
                                            ],
                                            width=12,
                                            md=3,
                                            className="mb-3",
                                        ),
                                    ]
                                ),
                                dbc.Row(
                                    [
                                        dbc.Col(
                                            [
                                                dbc.Button(
                                                    [
                                                        html.I(className="fa fa-check me-2"),
                                                        "Assign to Wells",
                                                    ],
                                                    id="designer-assign-btn",
                                                    color="primary",
                                                    disabled=True,
                                                ),
                                                dbc.Button(
                                                    [
                                                        html.I(className="fa fa-eraser me-2"),
                                                        "Clear Selected",
                                                    ],
                                                    id="designer-clear-btn",
                                                    color="warning",
                                                    className="ms-2",
                                                    disabled=True,
                                                ),
                                                dbc.Button(
                                                    [
                                                        html.I(className="fa fa-trash me-2"),
                                                        "Reset All",
                                                    ],
                                                    id="designer-reset-btn",
                                                    color="danger",
                                                    outline=True,
                                                    className="ms-2",
                                                ),
                                            ],
                                            width=12,
                                        )
                                    ]
                                ),
                            ]
                        ),
                        html.Hr(),
                        # Export section
                        html.Div(
                            [
                                html.H6("Export Layout"),
                                dbc.Row(
                                    [
                                        dbc.Col(
                                            [
                                                dbc.Button(
                                                    [
                                                        html.I(className="fa fa-download me-2"),
                                                        "Download Layout CSV",
                                                    ],
                                                    id="designer-export-btn",
                                                    color="success",
                                                ),
                                                dcc.Download(id="designer-download"),
                                            ],
                                            width=12,
                                        )
                                    ]
                                ),
                            ]
                        ),
                    ]
                ),
                id="designer-collapse",
                is_open=False,
            ),
        ],
        className="mb-4",
    )
