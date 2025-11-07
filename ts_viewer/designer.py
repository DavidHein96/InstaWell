# ts_viewer/designer.py
from __future__ import annotations

import re
import string
from pathlib import Path
from typing import Dict, List

import dash_bootstrap_components as dbc
import pandas as pd
from dash import Input, Output, State, dash_table, dcc, html, no_update

from .config import DATA_DIR
from .io import build_dataset_from_dfs, df_from_upload, save_uploaded_pair
from .state import Dataset, state
from .units import to_uM

# -------- helpers --------
_PLATES = {"96": (8, 12), "384": (16, 24)}

_WELL_RE = re.compile(r"^\s*([A-Za-z]+)\s*0*([0-9]+)\s*$")


def _norm_well(s: str) -> str:
    m = _WELL_RE.match(str(s))
    if not m:
        return str(s).strip()
    return f"{m.group(1).upper()}{int(m.group(2))}"


def _row_labels(n_rows: int) -> List[str]:
    return list(string.ascii_uppercase[:n_rows])


def _safe_token(s: str) -> str:
    s = str(s or "").strip()
    s = re.sub(r"\s+", "", s)
    return s.replace("_", "-")


def _upload_display(icon: str, label: str, help_text: str, filename: str | None = None):
    name = Path(str(filename)).name if filename else label
    main = f"{icon} {name}"
    help_line = "Loaded successfully" if filename else help_text
    return html.Div(
        [
            html.Span(main, className="upload-filename"),
            html.Span(help_line, className="upload-help"),
        ]
    )


def _infer_plate_from_raw_cols(raw_df: pd.DataFrame):
    wells = []
    max_row, max_col = "A", 1
    for c in raw_df.columns:
        if c == "Temperature":
            continue
        w = _norm_well(c)
        wells.append(w)
        m = _WELL_RE.match(w)
        if m:
            r = m.group(1).upper()
            col = int(m.group(2))
            max_row = max(max_row, r)
            max_col = max(max_col, col)
    rows_needed = ord(max_row) - ord("A") + 1
    cols_needed = max_col
    kind = "96" if (rows_needed <= 8 and cols_needed <= 12) else "384"
    rows = 8 if kind == "96" else 16
    cols = 12 if kind == "96" else 24
    return kind, rows, cols, sorted(set(wells))


def _compose_cell_text(cond: dict | None) -> str:
    if not cond:
        return ""
    c = cond.get("conc", "")
    u = cond.get("unit", "uM")
    l = _safe_token(cond.get("ligand", ""))
    p = _safe_token(cond.get("protein", ""))
    b = _safe_token(cond.get("buffer", ""))
    if not (c and l and p and b):
        return ""
    return f"{c}{u}_{l}_{p}_{b}"


def _pretty_cell_badge(cond: dict | None) -> str:
    if not cond:
        return "—"
    return f"{cond.get('conc', '')}{cond.get('unit', 'uM')} · {cond.get('ligand', '')} + {cond.get('protein', '')}"


def _well_sort_key(well: str):
    m = _WELL_RE.match(str(well))
    if not m:
        return (str(well), 0)
    row = m.group(1).upper()
    col = int(m.group(2))
    return (row, col)


def _selected_cells_from_wells(selection: List[str], plate: dict) -> List[dict]:
    if not selection or not plate:
        return []
    rows = plate.get("rows", 0)
    cols = plate.get("cols", 0)
    rlabels = _row_labels(rows)
    column_ids = ["Well"] + [str(i) for i in range(1, cols + 1)]
    out = []
    for wid in selection:
        m = _WELL_RE.match(str(wid))
        if not m:
            continue
        row_label = m.group(1).upper()
        col_id = str(int(m.group(2)))
        if row_label not in rlabels or col_id not in column_ids:
            continue
        row_idx = rlabels.index(row_label)
        col_idx = column_ids.index(col_id)
        out.append(dict(row=row_idx, column=col_idx, column_id=col_id, row_id=row_label))
    return out


def _wells_from_selected_cells(selected_cells: List[dict], plate: dict) -> List[str]:
    if not selected_cells or not plate:
        return []
    rows = plate.get("rows", 0)
    rlabels = _row_labels(rows)
    wells = []
    for cell in selected_cells:
        row_idx = cell.get("row")
        col_id = cell.get("column_id")
        if (
            row_idx is None
            or col_id is None
            or col_id == "Well"
            or not str(col_id).isdigit()
            or row_idx >= len(rlabels)
        ):
            continue
        row_label = rlabels[row_idx]
        wells.append(f"{row_label}{int(col_id)}")
    wells_sorted = sorted({w: None for w in wells}.keys(), key=_well_sort_key)
    return wells_sorted


def _initial_options_from_active_dataset() -> Dict[str, List[str]]:
    if not state.active or state.active not in state.datasets:
        return dict(ligands=[], proteins=[], buffers=[], units=["nM", "uM", "mM"])
    ds = state.datasets[state.active]
    ligs = (
        sorted({str(x) for x in ds.data.get("ligand", pd.Series([])).unique()})
        if "ligand" in ds.data
        else []
    )
    prots = (
        sorted({str(x) for x in ds.data.get("protein", pd.Series([])).unique()})
        if "protein" in ds.data
        else []
    )
    bufs = (
        sorted({str(x) for x in ds.data.get("buffer", pd.Series([])).unique()})
        if "buffer" in ds.data
        else []
    )
    return dict(ligands=ligs, proteins=prots, buffers=bufs, units=["nM", "uM", "mM"])


def _infer_plate_kind_from_raw_cols(raw_df: pd.DataFrame) -> tuple[str, int, int, list[str]]:
    wells = []
    max_row = "A"
    max_col = 1
    for c in raw_df.columns:
        if c == "Temperature":
            continue
        w = _norm_well(c)
        wells.append(w)
        m = _WELL_RE.match(w)
        if m:
            row = m.group(1).upper()
            col = int(m.group(2))
            max_row = max(max_row, row)
            max_col = max(max_col, col)
    # Choose closest plate preset
    rows_needed = ord(max_row) - ord("A") + 1
    cols_needed = max_col
    kind = "96"
    if rows_needed > 8 or cols_needed > 12:
        kind = "384"
    rows, cols = _PLATES[kind]
    # Cap to fit inferred bounds but not exceed plate type
    rows = max(rows_needed, min(rows, rows))
    cols = max(cols_needed, min(cols, cols))
    return kind, rows, cols, sorted(set(wells))


# -------- UI --------
def designer_card():
    opts = _initial_options_from_active_dataset()
    return dbc.Card(
        [
            dbc.CardHeader(
                dbc.Row(
                    [
                        dbc.Col(html.H4("Well Layout Designer (beta)", className="m-0"), md="auto"),
                        dbc.Col(
                            dbc.Button(
                                "Hide Designer",
                                id="designer-toggle",
                                color="secondary",
                                size="sm",
                                className="ms-auto",
                            ),
                            md="auto",
                        ),
                    ],
                    align="center",
                    className="g-2",
                )
            ),
            dbc.Collapse(
                dbc.CardBody(
                    [
                        # stores
                        dcc.Store(
                            id="designer-layout",
                            data=dict(
                                plate=dict(kind="96", rows=_PLATES["96"][0], cols=_PLATES["96"][1]),
                                cells={},  # {"A1": {...}}
                                available_wells=[],
                                options=opts,
                            ),
                        ),
                        dcc.Store(id="designer-selection", data=[]),
                        dcc.Store(
                            id="designer-raw-store", data=None
                        ),  # holds raw.csv (base64) & filename
                        # RAW-ONLY IMPORT ROW
                        dbc.Row(
                            [
                                dbc.Col(
                                    [
                                        html.Label(
                                            "Start from raw.csv (optional)", className="fw-bold"
                                        ),
                                        dcc.Upload(
                                            id="designer-raw-upload",
                                            children=_upload_display(
                                                "📈", "raw.csv", "Drag & drop or click to choose raw readings"
                                            ),
                                            multiple=False,
                                            accept=".csv",
                                            className="upload-zone",
                                        ),
                                        html.Small(
                                            id="designer-upload-debug", className="text-muted mt-2"
                                        ),  # <-- add this
                                    ],
                                    md=6,
                                ),
                                dbc.Col(
                                    [
                                        html.Label("Dataset name (when saving)", className="fw-bold"),
                                        dbc.Input(
                                            id="designer-dataset-name",
                                            placeholder="e.g. runA-2025-10-22",
                                            className="mb-2",
                                        ),
                                        dbc.Button(
                                            "Create dataset from designer + raw",
                                            id="designer-create-dataset",
                                            color="success",
                                            className="me-2",
                                        ),
                                        html.Small(
                                            id="designer-save-status", className="text-muted ms-2"
                                        ),
                                    ],
                                    md=6,
                                ),
                            ],
                            className="g-3 mb-3",
                        ),
                        # controls row
                        dbc.Row(
                            [
                                dbc.Col(
                                    [
                                        html.Label("Plate size", className="fw-bold"),
                                        dcc.Dropdown(
                                            id="designer-plate-kind",
                                            options=[
                                                {"label": f"{k}-well", "value": k} for k in _PLATES
                                            ],
                                            value="96",
                                            clearable=False,
                                        ),
                                    ],
                                    md=2,
                                ),
                                dbc.Col(
                                    [
                                        html.Label("Fill selection", className="fw-bold"),
                                        dbc.Row(
                                            [
                                                dbc.Col(
                                                    dbc.Input(
                                                        id="designer-conc",
                                                        type="number",
                                                        placeholder="Conc",
                                                        min=0,
                                                    ),
                                                    sm=4,
                                                ),
                                                dbc.Col(
                                                    dcc.Dropdown(
                                                        id="designer-unit",
                                                        options=[
                                                            {"label": u, "value": u}
                                                            for u in opts["units"]
                                                        ],
                                                        value="uM",
                                                        clearable=False,
                                                    ),
                                                    sm=3,
                                                ),
                                                dbc.Col(
                                                    dbc.Input(
                                                        id="designer-ligand", placeholder="Ligand"
                                                    ),
                                                    sm=5,
                                                ),
                                            ],
                                            className="g-2",
                                        ),
                                        dbc.Row(
                                            [
                                                dbc.Col(
                                                    dbc.Input(
                                                        id="designer-protein", placeholder="Protein"
                                                    ),
                                                    sm=6,
                                                ),
                                                dbc.Col(
                                                    dbc.Input(
                                                        id="designer-buffer", placeholder="Buffer"
                                                    ),
                                                    sm=6,
                                                ),
                                            ],
                                            className="g-2 mt-1",
                                        ),
                                        dbc.Button(
                                            "Apply to selected wells",
                                            id="designer-apply",
                                            color="primary",
                                            className="mt-2 me-2",
                                        ),
                                        dbc.Button(
                                            "Clear selected",
                                            id="designer-clear",
                                            color="secondary",
                                            className="mt-2 me-2",
                                        ),
                                        dbc.Button(
                                            "Deselect all",
                                            id="designer-deselect-all",
                                            color="secondary",
                                            outline=True,
                                            className="mt-2 me-2",
                                        ),
                                        dbc.Button(
                                            "Select all",
                                            id="designer-select-all",
                                            color="secondary",
                                            className="mt-2",
                                        ),
                                        html.Small(
                                            id="designer-status", className="text-muted ms-3"
                                        ),
                                    ],
                                    md=7,
                                ),
                                dbc.Col(
                                    [
                                        html.Label("Export", className="fw-bold"),
                                        dbc.Button(
                                            "Download layout.csv",
                                            id="designer-download-btn",
                                            color="success",
                                            className="me-2",
                                        ),
                                        dcc.Download(id="designer-download"),
                                    ],
                                    md=3,
                                ),
                            ],
                            className="align-items-end g-3 mb-3",
                        ),
                        # grid
                        html.Div(id="designer-grid"),
                    ]
                ),
                id="designer-collapse",
                is_open=True,
            ),
        ],
        className="shadow-sm",
    )


# -------- grid render --------
def _render_grid(plate: dict, cells: dict, available: List[str]) -> html.Div:
    rows, cols = plate["rows"], plate["cols"]
    rlabels = _row_labels(rows)
    data = []
    for rlab in rlabels:
        row = {"Well": rlab}
        for c in range(1, cols + 1):
            wid = f"{rlab}{c}"
            cond = cells.get(wid)
            row[str(c)] = _pretty_cell_badge(cond) if cond else ""
        data.append(row)

    columns = [{"name": "Well", "id": "Well"}] + [
        {"name": str(i), "id": str(i)} for i in range(1, cols + 1)
    ]

    style_data_conditional = [
        {
            "if": {"column_id": "Well"},
            "fontWeight": "600",
            "backgroundColor": "rgba(0,0,0,0.04)",
        }
    ]
    for rlab in rlabels:
        for c in range(1, cols + 1):
            wid = f"{rlab}{c}"
            cond = cells.get(wid)
            if cond:
                style_data_conditional.append(
                    {
                        "if": {"filter_query": f'{{Well}} = "{rlab}"', "column_id": str(c)},
                        "backgroundColor": "rgba(13,110,253,0.12)",
                        "fontWeight": "600",
                    }
                )

    available_set = {str(w) for w in available or []}
    for wid in available_set:
        m = _WELL_RE.match(wid)
        if not m:
            continue
        row_label = m.group(1).upper()
        col_id = str(int(m.group(2)))
        if row_label not in rlabels:
            continue
        if cells.get(f"{row_label}{col_id}"):
            continue
        style_data_conditional.append(
            {
                "if": {"filter_query": f'{{Well}} = "{row_label}"', "column_id": col_id},
                "backgroundColor": "rgba(108,117,125,0.08)",
            }
        )

    table = dash_table.DataTable(
        id="designer-grid-table",
        data=data,
        columns=columns,
        selected_cells=[],
        cell_selectable=True,
        editable=False,
        style_as_list_view=True,
        style_table={"maxHeight": "60vh", "overflowY": "auto", "overflowX": "auto"},
        fixed_rows={"headers": True},
        style_cell={
            "textAlign": "center",
            "padding": "4px",
            "fontSize": "13px",
            "minWidth": "90px",
            "width": "90px",
            "maxWidth": "90px",
            "whiteSpace": "nowrap",
            "overflow": "hidden",
            "textOverflow": "ellipsis",
        },
        style_data_conditional=style_data_conditional,
        css=[
            {
                "selector": ".dash-spreadsheet td.focused",
                "rule": "outline: 2px solid var(--bs-primary); outline-offset: -1px;",
            },
            {
                "selector": ".dash-spreadsheet td.cell--selected",
                "rule": "background-color: rgba(13,110,253,0.18) !important;",
            },
            {
                "selector": ".dash-spreadsheet td, .dash-spreadsheet th",
                "rule": "border-right: 1px dashed rgba(0,0,0,0.12);",
            },
            {
                "selector": ".dash-spreadsheet td:last-child, .dash-spreadsheet th:last-child",
                "rule": "border-right: none;",
            },
        ],
    )
    return html.Div(table, style={"borderRadius": "4px"})


# -------- callbacks --------
def register_designer_callbacks(app):
    @app.callback(
        Output("designer-collapse", "is_open"),
        Input("designer-toggle", "n_clicks"),
        State("designer-collapse", "is_open"),
        prevent_initial_call=True,
    )
    def _toggle_card(n, is_open):
        if not n:
            return no_update
        return not is_open

    @app.callback(
        Output("designer-toggle", "children"),
        Input("designer-collapse", "is_open"),
    )
    def _sync_toggle_label(is_open):
        return "Hide Designer" if is_open else "Show Designer"

    # Change plate kind
    @app.callback(
        Output("designer-layout", "data", allow_duplicate=True),
        Input("designer-plate-kind", "value"),
        State("designer-layout", "data"),
        prevent_initial_call=True,
    )
    def _change_plate(kind, data):
        if not data:
            return no_update
        r, c = _PLATES.get(kind, _PLATES["96"])
        new = dict(data)
        new["plate"] = dict(kind=kind, rows=r, cols=c)
        return new

    # Render grid
    @app.callback(
        Output("designer-grid", "children"),
        Input("designer-layout", "data"),
    )
    def _render(data):
        if not data:
            return html.Div("Designer not initialized.")
        return _render_grid(data["plate"], data.get("cells", {}), data.get("available_wells", []))

    # Sync table selection -> store
    @app.callback(
        Output("designer-selection", "data", allow_duplicate=True),
        Input("designer-grid-table", "selected_cells"),
        State("designer-layout", "data"),
        State("designer-selection", "data"),
        prevent_initial_call=True,
    )
    def _sync_selection(selected_cells, layout_data, selection_state):
        if not layout_data:
            return no_update
        plate = layout_data.get("plate", {})
        wells = _wells_from_selected_cells(selected_cells or [], plate)
        if wells == (selection_state or []):
            return no_update
        return wells

    @app.callback(
        Output("designer-grid-table", "selected_cells"),
        Input("designer-selection", "data"),
        Input("designer-layout", "data"),
        prevent_initial_call=True,
    )
    def _push_selection(selection, layout_data):
        if not layout_data:
            return no_update
        plate = layout_data.get("plate", {})
        return _selected_cells_from_wells(selection or [], plate)

    @app.callback(
        Output("designer-selection", "data", allow_duplicate=True),
        Input("designer-deselect-all", "n_clicks"),
        prevent_initial_call=True,
    )
    def _deselect_all(_n):
        if not _n:
            return no_update
        return []

    # Apply values to selected wells
    @app.callback(
        Output("designer-layout", "data", allow_duplicate=True),
        Output("designer-status", "children"),
        Input("designer-apply", "n_clicks"),
        State("designer-layout", "data"),
        State("designer-selection", "data"),
        State("designer-conc", "value"),
        State("designer-unit", "value"),
        State("designer-ligand", "value"),
        State("designer-protein", "value"),
        State("designer-buffer", "value"),
        prevent_initial_call=True,
    )
    def _apply(_n, data, selection, conc, unit, lig, prot, buf):
        if not data or not selection:
            return no_update, "Select one or more wells."
        if conc is None or str(conc).strip() == "":
            return no_update, "Concentration required."
        unit = unit or "uM"
        lig = (lig or "").strip()
        prot = (prot or "").strip()
        buf = (buf or "").strip()
        if not (lig and prot and buf):
            return no_update, "Ligand, Protein, and Buffer required."
        try:
            _ = to_uM(f"{conc} {unit}")
        except Exception:
            return no_update, "Invalid concentration."
        new = dict(data)
        cells = dict(new.get("cells", {}))
        for w in selection:
            cells[w] = dict(conc=str(conc), unit=unit, ligand=lig, protein=prot, buffer=buf)
        new["cells"] = cells
        return new, f"Applied to {len(selection)} well(s)."

    # Clear selected wells
    @app.callback(
        Output("designer-layout", "data", allow_duplicate=True),
        Output("designer-selection", "data", allow_duplicate=True),
        Input("designer-clear", "n_clicks"),
        State("designer-layout", "data"),
        State("designer-selection", "data"),
        prevent_initial_call=True,
    )
    def _clear(_n, data, selection):
        if not data or not selection:
            return no_update, no_update
        new = dict(data)
        cells = dict(new.get("cells", {}))
        for w in selection:
            cells.pop(w, None)
        new["cells"] = cells
        return new, []

    # Select all wells
    @app.callback(
        Output("designer-selection", "data", allow_duplicate=True),
        Input("designer-select-all", "n_clicks"),
        State("designer-layout", "data"),
        prevent_initial_call=True,
    )
    def _select_all(_n, data):
        if not data:
            return no_update
        r, c = data["plate"]["rows"], data["plate"]["cols"]
        rlabels = _row_labels(r)
        return [f"{rl}{ci}" for rl in rlabels for ci in range(1, c + 1)]

    # Download layout.csv
    @app.callback(
        Output("designer-download", "data"),
        Input("designer-download-btn", "n_clicks"),
        State("designer-layout", "data"),
        prevent_initial_call=True,
    )
    def _download(_n, data):
        if not data:
            return no_update
        r, c = data["plate"]["rows"], data["plate"]["cols"]
        rlabels = _row_labels(r)
        cols = ["Well"] + [str(i) for i in range(1, c + 1)]
        rows = []
        cells = data.get("cells", {})
        for rl in rlabels:
            row = {"Well": rl}
            for ci in range(1, c + 1):
                wid = f"{rl}{ci}"
                row[str(ci)] = _compose_cell_text(cells.get(wid))
            rows.append(row)
        df = pd.DataFrame(rows, columns=cols)
        return dcc.send_data_frame(df.to_csv, "layout.csv", index=False)

    # --- RAW-ONLY: accept raw.csv, infer plate, preselect wells, store raw in memory ---
    @app.callback(
        Output("designer-upload-debug", "children"),
        Output("designer-raw-store", "data", allow_duplicate=True),
        Output("designer-layout", "data", allow_duplicate=True),
        Output("designer-selection", "data", allow_duplicate=True),
        Output("designer-raw-upload", "children", allow_duplicate=True),
        Output("designer-raw-upload", "className", allow_duplicate=True),
        Input("designer-raw-upload", "contents"),
        State("designer-raw-upload", "filename"),
        State("designer-layout", "data"),
        prevent_initial_call=True,
    )
    def _designer_raw_upload(contents, filename, layout_state):
        app.logger.info(
            "designer-raw-upload fired. has_contents=%s filename=%s", bool(contents), filename
        )
        if not contents:
            return (
                html.Span("No file received."),
                no_update,
                no_update,
                no_update,
                _upload_display("📈", "raw.csv", "Drag & drop or click to choose raw readings"),
                "upload-zone",
            )

        try:
            from .io import df_from_upload

            raw_df = df_from_upload(contents, filename or "raw.csv")
        except Exception as e:
            app.logger.exception("Raw upload parse failed")
            return (
                html.Span(f"Could not read raw.csv: {e}"),
                no_update,
                no_update,
                no_update,
                _upload_display("📈", "raw.csv", "Drag & drop or click to choose raw readings"),
                "upload-zone",
            )

        if "Temperature" not in raw_df.columns:
            return (
                html.Span("Raw is missing 'Temperature' column."),
                no_update,
                no_update,
                [],
                _upload_display("📈", "raw.csv", "Drag & drop or click to choose raw readings"),
                "upload-zone",
            )

        kind, rows, cols, wells = _infer_plate_from_raw_cols(raw_df)
        new_layout = dict(layout_state or {})
        new_layout["plate"] = dict(kind=kind, rows=rows, cols=cols)
        new_layout["available_wells"] = wells

        # Show a clear preview message
        preview = html.Span(
            f"Loaded {filename or 'raw.csv'} → shape={tuple(raw_df.shape)}, inferred {kind}-well plate, detected {len(wells)} wells."
        )

        app.logger.info("raw upload ok: shape=%s plate=%s wells=%d", raw_df.shape, kind, len(wells))
        return (
            preview,
            {"contents": contents, "filename": filename or "raw.csv"},
            new_layout,
            [],
            _upload_display("📈", filename or "raw.csv", "Drag & drop or click to choose raw readings", filename or "raw.csv"),
            "upload-zone loaded",
        )

    # --- CREATE DATASET from designer + raw ---
    @app.callback(
        Output("designer-save-status", "children"),
        Output("dataset-select", "options"),
        Output("dataset-select", "value"),
        Output("designer-collapse", "is_open", allow_duplicate=True),
        Input("designer-create-dataset", "n_clicks"),
        State("designer-dataset-name", "value"),
        State("designer-raw-store", "data"),
        State("designer-layout", "data"),
        prevent_initial_call=True,
    )
    def _create_dataset(n, name, raw_store, layout_data):
        if not n:
            return no_update, no_update, no_update, no_update
        name = (name or "").strip()
        if not name:
            return (
                dbc.Alert("Please provide a dataset name.", color="warning"),
                no_update,
                no_update,
                no_update,
            )
        if name in state.datasets:
            return (
                dbc.Alert(f"Dataset “{name}” already exists.", color="warning"),
                no_update,
                no_update,
                no_update,
            )
        if not raw_store:
            return (
                dbc.Alert("No raw.csv loaded. Upload raw first.", color="warning"),
                no_update,
                no_update,
                no_update,
            )
        # Rebuild layout DataFrame from cells
        plate = layout_data.get("plate", {})
        rows = plate.get("rows", 8)
        cols = plate.get("cols", 12)
        rlabels = _row_labels(rows)
        cells = layout_data.get("cells", {})
        layout_rows = []
        for rl in rlabels:
            row = {"Well": rl}
            for ci in range(1, cols + 1):
                row[str(ci)] = _compose_cell_text(cells.get(f"{rl}{ci}"))
            layout_rows.append(row)
        layout_df = pd.DataFrame(
            layout_rows, columns=["Well"] + [str(i) for i in range(1, cols + 1)]
        )

        # Parse raw from store and build dataset
        try:
            raw_df = df_from_upload(raw_store["contents"], raw_store.get("filename") or "raw.csv")
        except Exception as e:
            return (
                dbc.Alert(f"Could not decode cached raw.csv: {e}", color="danger"),
                no_update,
                no_update,
                no_update,
            )

        try:
            tidy, titles, reps = build_dataset_from_dfs(layout_df, raw_df)
        except Exception as e:
            return (
                dbc.Alert(f"Building dataset failed: {e}", color="danger"),
                no_update,
                no_update,
                no_update,
            )

        if tidy.empty or not titles:
            return (
                dbc.Alert("Designed layout produced no conditions.", color="danger"),
                no_update,
                no_update,
                no_update,
            )

        # Persist to disk if possible
        try:
            save_uploaded_pair(DATA_DIR, name, layout_df, raw_df)
            persist_note = ""
        except Exception as e:
            persist_note = f" (disk save failed: {e})"

        # Register
        ds = Dataset(
            name=name,
            data=tidy,
            group_titles=titles,
            group_replicates=reps,
            unique_keys=sorted(titles.keys()),
        )
        state.datasets[name] = ds
        state.active = name
        options = [{"label": k, "value": k} for k in sorted(state.datasets.keys())]

        return (
            dbc.Alert(
                f"Dataset “{name}” created with {len(ds.unique_keys)} conditions.{persist_note}",
                color="success",
                dismissable=True,
            ),
            options,
            name,
            False,
        )
