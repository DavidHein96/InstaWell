# ts_viewer/callbacks.py
import math
from pathlib import Path
from typing import Dict, List, Optional

import dash_bootstrap_components as dbc
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, dcc, html, no_update
from dash.dependencies import ALL
from plotly.subplots import make_subplots

from .compute import compute_series_for_group
from .state import Dataset, state


# ---------- helpers ----------
def _active_ds() -> Optional[Dataset]:
    if not state.active or state.active not in state.datasets:
        return None
    return state.datasets[state.active]


def _color_map(names: List[str]) -> Dict[str, str]:
    base = [
        "#1f77b4",
        "#ff7f0e",
        "#2ca02c",
        "#d62728",
        "#9467bd",
        "#8c564b",
        "#e377c2",
        "#7f7f7f",
        "#bcbd22",
        "#17becf",
    ]
    return {name: base[i % len(base)] for i, name in enumerate(sorted(set(names)))}


def _selected_reps_map(selected_keys: List[str], rep_values, rep_ids, ds: Dataset):
    out = {}
    if selected_keys and rep_ids:
        for i, rid in enumerate(rep_ids):
            if isinstance(rid, dict):
                gk = rid.get("group_key")
                if gk in selected_keys:
                    out[gk] = rep_values[i] if rep_values and i < len(rep_values) else []
    for k in selected_keys:
        out.setdefault(k, ds.group_replicates.get(k, []))
    return out


def _upload_display(icon: str, label: str, help_text: str, filename: Optional[str] = None):
    name = Path(str(filename)).name if filename else label
    main = f"{icon} {name}"
    helper = "Loaded successfully" if filename else help_text
    return html.Div(
        [
            html.Span(main, className="upload-filename"),
            html.Span(helper, className="upload-help"),
        ]
    )


# ---------- registration ----------
def register_callbacks(app):
    # Replicate selectors: single owner of replicate-accordion.children
    @app.callback(
        Output("replicate-accordion", "children"),
        Input("plot-selector", "value"),
    )
    def populate_replicate_selectors(selected_keys: List[str]):
        ds = _active_ds()
        if not ds:
            return [dbc.AccordionItem("Load a dataset to begin.", title="Replicates")]
        if not selected_keys:
            return [
                dbc.AccordionItem(
                    "Select a condition above to choose replicates.", title="Replicates"
                )
            ]
        items = []
        for key in selected_keys:
            title = ds.group_titles.get(key, "Unknown")
            reps = ds.group_replicates.get(key, [])
            items.append(
                dbc.AccordionItem(
                    [
                        dbc.Checklist(
                            id={"type": "replicate-filter", "group_key": key},
                            options=[{"label": r, "value": r} for r in reps],
                            value=reps,
                            inline=True,
                        )
                    ],
                    title=title,
                )
            )
        return items

    # Main figure
    @app.callback(
        Output("dynamic-subplot-graph", "figure"),
        [
            Input("plot-selector", "value"),
            Input({"type": "replicate-filter", "group_key": ALL}, "value"),
            Input("bg-subtract-toggle", "value"),
            Input("normalize-toggle", "value"),
            Input("derivative-toggle", "value"),
        ],
        State({"type": "replicate-filter", "group_key": ALL}, "id"),
    )
    def update_graph(selected_keys, rep_values, bg_vals, norm_vals, deriv_vals, rep_ids):
        fig_empty = go.Figure().update_layout(
            xaxis={"visible": False},
            yaxis={"visible": False},
            annotations=[
                dict(text="Select a condition to begin", showarrow=False, font=dict(size=18))
            ],
        )
        ds = _active_ds()
        if not ds or not selected_keys or ds.data.empty:
            return fig_empty

        bg_enabled = "BG" in (bg_vals or [])
        norm_enabled = "NORM" in (norm_vals or [])
        deriv_enabled = "DERIV" in (deriv_vals or [])
        reps_map = _selected_reps_map(selected_keys, rep_values, rep_ids, ds)

        n = len(selected_keys)
        if n == 1:
            cols, rows = 1, 1
        elif n == 2:
            cols, rows = 2, 1
        elif n <= 4:
            cols, rows = 2, math.ceil(n / 2)
        else:
            cols, rows = 3, math.ceil(n / 3)

        fig = make_subplots(
            rows=rows,
            cols=cols,
            subplot_titles=[ds.group_titles.get(k, "Plot") for k in selected_keys],
            specs=[[{"secondary_y": True} for _ in range(cols)] for _ in range(rows)],
        )

        all_reps = [r for k in selected_keys for r in reps_map.get(k, [])]
        cmap = _color_map(all_reps)

        r = c = 1
        for key in selected_keys:
            title = ds.group_titles.get(key, key)
            sel = reps_map.get(key, [])

            summary, reps_df = compute_series_for_group(key, sel, bg_enabled, ds.data)

            # individual replicates (primary)
            if not reps_df.empty:
                for rep_name, df_rep in reps_df.groupby("replicate_id"):
                    fig.add_trace(
                        go.Scatter(
                            x=df_rep["Temperature"],
                            y=df_rep["value"],
                            mode="lines",
                            line=dict(width=1.5, color=cmap.get(rep_name)),
                            name=f"{title} · {rep_name}",
                            legendgroup=title,
                            showlegend=False,
                            hovertemplate="T=%{x:.2f} °C<br>Value=%{y:.4f}<extra>"
                            + rep_name
                            + "</extra>",
                        ),
                        row=r,
                        col=c,
                        secondary_y=False,
                    )

            # averages + derivative
            show_secondary = False
            if not summary.empty:
                if norm_enabled and "avg_norm" in summary.columns:
                    fig.add_trace(
                        go.Scatter(
                            x=summary["Temperature"],
                            y=summary["avg_norm"],
                            mode="lines",
                            name=f"{title} · Avg (Norm)",
                            legendgroup=title,
                            line=dict(width=3, dash="dash"),
                            hovertemplate="T=%{x:.2f} °C<br>Norm Avg=%{y:.3f}<extra>"
                            + title
                            + "</extra>",
                        ),
                        row=r,
                        col=c,
                        secondary_y=True,
                    )
                    show_secondary = True
                else:
                    fig.add_trace(
                        go.Scatter(
                            x=summary["Temperature"],
                            y=summary["avg"],
                            mode="lines",
                            name=f"{title} · Avg",
                            legendgroup=title,
                            line=dict(width=3),
                            hovertemplate="T=%{x:.2f} °C<br>Avg=%{y:.4f}<extra>"
                            + title
                            + "</extra>",
                        ),
                        row=r,
                        col=c,
                        secondary_y=False,
                    )

                if deriv_enabled and "neg_deriv_norm" in summary.columns:
                    fig.add_trace(
                        go.Scatter(
                            x=summary["Temperature"],
                            y=summary["neg_deriv_norm"],
                            mode="lines",
                            name=f"{title} · -dY/dT (Norm)",
                            legendgroup=title,
                            line=dict(width=2, dash="dot"),
                            hovertemplate="T=%{x:.2f} °C<br>-dY/dT (norm)=%{y:.3f}<extra>"
                            + title
                            + "</extra>",
                        ),
                        row=r,
                        col=c,
                        secondary_y=True,
                    )
                    show_secondary = True

            # axes
            fig.update_xaxes(title_text="Temperature (°C)", row=r, col=c)
            fig.update_yaxes(title_text="Value", secondary_y=False, row=r, col=c)
            if show_secondary:
                fig.update_yaxes(
                    title_text="Normalized (0–1)", secondary_y=True, row=r, col=c, range=[0, 1]
                )
            else:
                fig.update_yaxes(visible=False, secondary_y=True, row=r, col=c)

            c += 1
            if c > cols:
                c = 1
                r += 1

        fig.update_layout(
            height=max(540, rows * 360),
            legend=dict(orientation="h", yanchor="bottom", y=-0.08),
            margin=dict(l=60, r=40, t=60, b=80),
        )
        if len(selected_keys) == 1 and fig.layout.annotations:
            t = ds.group_titles.get(selected_keys[0], "")
            fig.update_layout(title_text=t)
            fig.layout.annotations = tuple(ann for ann in fig.layout.annotations if ann.text != t)
        return fig

    # Figure download (build directly; do not call another callback)
    @app.callback(
        Output("download-avg-fig-html", "data"),
        Input("btn-download-avg-fig", "n_clicks"),
        State("plot-selector", "value"),
        State({"type": "replicate-filter", "group_key": ALL}, "value"),
        State("bg-subtract-toggle", "value"),
        State("normalize-toggle", "value"),
        State("derivative-toggle", "value"),
        State({"type": "replicate-filter", "group_key": ALL}, "id"),
        prevent_initial_call=True,
    )
    def download_fig(n, selected_keys, rep_values, bg_vals, norm_vals, deriv_vals, rep_ids):
        ds = _active_ds()
        if not n or not ds or not selected_keys or ds.data.empty:
            return dcc.send_string("", "empty.html")

        bg_enabled = "BG" in (bg_vals or [])
        norm_enabled = "NORM" in (norm_vals or [])
        deriv_enabled = "DERIV" in (deriv_vals or [])
        reps_map = _selected_reps_map(selected_keys, rep_values, rep_ids or [], ds)

        nplots = len(selected_keys)
        if nplots == 1:
            cols, rows = 1, 1
        elif nplots == 2:
            cols, rows = 2, 1
        elif nplots <= 4:
            cols, rows = 2, math.ceil(nplots / 2)
        else:
            cols, rows = 3, math.ceil(nplots / 3)

        fig = make_subplots(
            rows=rows,
            cols=cols,
            subplot_titles=[ds.group_titles.get(k, "Plot") for k in selected_keys],
            specs=[[{"secondary_y": True} for _ in range(cols)] for _ in range(rows)],
        )

        all_reps = [r for k in selected_keys for r in reps_map.get(k, [])]
        cmap = _color_map(all_reps)

        r = c = 1
        for key in selected_keys:
            title = ds.group_titles.get(key, key)
            sel = reps_map.get(key, [])

            summary, reps_df = compute_series_for_group(key, sel, bg_enabled, ds.data)

            if not reps_df.empty:
                for rep_name, df_rep in reps_df.groupby("replicate_id"):
                    fig.add_trace(
                        go.Scatter(
                            x=df_rep["Temperature"],
                            y=df_rep["value"],
                            mode="lines",
                            line=dict(width=1.5, color=cmap.get(rep_name)),
                            name=f"{title} · {rep_name}",
                            legendgroup=title,
                            showlegend=False,
                        ),
                        row=r,
                        col=c,
                        secondary_y=False,
                    )

            show_secondary = False
            if not summary.empty:
                if norm_enabled and "avg_norm" in summary.columns:
                    fig.add_trace(
                        go.Scatter(
                            x=summary["Temperature"],
                            y=summary["avg_norm"],
                            mode="lines",
                            name=f"{title} · Avg (Norm)",
                            legendgroup=title,
                            line=dict(width=3, dash="dash"),
                        ),
                        row=r,
                        col=c,
                        secondary_y=True,
                    )
                    show_secondary = True
                else:
                    fig.add_trace(
                        go.Scatter(
                            x=summary["Temperature"],
                            y=summary["avg"],
                            mode="lines",
                            name=f"{title} · Avg",
                            legendgroup=title,
                            line=dict(width=3),
                        ),
                        row=r,
                        col=c,
                        secondary_y=False,
                    )

                if deriv_enabled and "neg_deriv_norm" in summary.columns:
                    fig.add_trace(
                        go.Scatter(
                            x=summary["Temperature"],
                            y=summary["neg_deriv_norm"],
                            mode="lines",
                            name=f"{title} · -dY/dT (Norm)",
                            legendgroup=title,
                            line=dict(width=2, dash="dot"),
                        ),
                        row=r,
                        col=c,
                        secondary_y=True,
                    )
                    show_secondary = True

            fig.update_xaxes(title_text="Temperature (°C)", row=r, col=c)
            fig.update_yaxes(title_text="Value", secondary_y=False, row=r, col=c)
            if show_secondary:
                fig.update_yaxes(
                    title_text="Normalized (0–1)", secondary_y=True, row=r, col=c, range=[0, 1]
                )
            else:
                fig.update_yaxes(visible=False, secondary_y=True, row=r, col=c)

            c += 1
            if c > cols:
                c = 1
                r += 1

        fig.update_layout(
            height=max(540, rows * 360),
            legend=dict(orientation="h", yanchor="bottom", y=-0.08),
            margin=dict(l=60, r=40, t=60, b=80),
            title_text=(
                ds.group_titles.get(selected_keys[0], "") if len(selected_keys) == 1 else None
            ),
        )

        return dict(
            content=fig.to_html(full_html=True, include_plotlyjs="cdn"),
            filename="processed_plots.html",
        )

    # Data CSV download
    @app.callback(
        Output("download-avg-data-csv", "data"),
        Input("btn-download-avg-csv", "n_clicks"),
        State("plot-selector", "value"),
        State({"type": "replicate-filter", "group_key": ALL}, "value"),
        State("bg-subtract-toggle", "value"),
        State({"type": "replicate-filter", "group_key": ALL}, "id"),
        prevent_initial_call=True,
    )
    def download_data(n, selected_keys, rep_values, bg_vals, rep_ids):
        ds = _active_ds()
        if not n or not ds or not selected_keys or ds.data.empty:
            return dcc.send_string("", "empty.csv")

        bg_enabled = "BG" in (bg_vals or [])
        rep_map = _selected_reps_map(selected_keys, rep_values, rep_ids or [], ds)

        rows = []
        for key in selected_keys:
            title = ds.group_titles.get(key, key)
            summary, _ = compute_series_for_group(key, rep_map.get(key, []), bg_enabled, ds.data)
            if summary.empty:
                continue
            out = summary.copy()
            out.insert(0, "group_key", key)
            out.insert(1, "title", title)
            rows.append(out)

        if not rows:
            return dcc.send_string("No data for current selection\n", "processed_data.csv")

        df = pd.concat(rows, ignore_index=True)
        for col in ["avg", "avg_norm", "neg_deriv", "neg_deriv_norm"]:
            if col not in df.columns:
                df[col] = np.nan
        return dcc.send_data_frame(df.to_csv, "processed_data.csv", index=False)

    # Metadata CSV download
    @app.callback(
        Output("download-metadata-csv", "data"),
        Input("btn-download-metadata-csv", "n_clicks"),
        State("plot-selector", "value"),
        State({"type": "replicate-filter", "group_key": ALL}, "value"),
        State("bg-subtract-toggle", "value"),
        State("normalize-toggle", "value"),
        State("derivative-toggle", "value"),
        State({"type": "replicate-filter", "group_key": ALL}, "id"),
        prevent_initial_call=True,
    )
    def download_meta(n, selected_keys, rep_values, bg_vals, norm_vals, deriv_vals, rep_ids):
        ds = _active_ds()
        if not n or not selected_keys or not ds:
            return dcc.send_string("", "empty.csv")

        rep_map = _selected_reps_map(selected_keys, rep_values, rep_ids or [], ds)
        rows = []
        for key in selected_keys:
            rows.append(
                dict(
                    dataset=state.active,
                    group_key=key,
                    title=ds.group_titles.get(key, key),
                    selected_replicates=";".join(rep_map.get(key, [])),
                    background_subtraction=("BG" in (bg_vals or [])),
                    normalize_average_0_1=("NORM" in (norm_vals or [])),
                    plot_derivative_norm=("DERIV" in (deriv_vals or [])),
                )
            )
        return dcc.send_data_frame(pd.DataFrame(rows).to_csv, "metadata.csv", index=False)

    # Template links (static data URLs)
    LAYOUT_TEMPLATE = "Well,1,2,3\nA,10_uM_LigX_ProtX_Buf1,10_uM_LigX_NPC_Buf1,\nB,,,\n"
    RAW_TEMPLATE = "Temperature,A1,A2,A3\n20,0.10,0.12,0.11\n21,0.12,0.13,0.12\n"

    @app.callback(
        Output("download-layout-template", "href"),
        Output("download-raw-template", "href"),
        Input("dynamic-subplot-graph", "figure"),  # dummy to compute once
        prevent_initial_call=False,
    )
    def _templ_links(_):
        layout_url = "data:text/plain;charset=utf-8," + LAYOUT_TEMPLATE
        raw_url = "data:text/plain;charset=utf-8," + RAW_TEMPLATE
        return layout_url, raw_url

    @app.callback(
        Output("upload-layout", "children"),
        Output("upload-layout", "className"),
        Input("upload-layout", "filename"),
        Input("upload-layout", "contents"),
        prevent_initial_call=True,
    )
    def _layout_upload_feedback(filename, contents):
        if contents:
            return (
                _upload_display(
                    "📄",
                    filename or "layout.csv",
                    "Drag & drop or click to choose layout",
                    filename or "layout.csv",
                ),
                "upload-zone loaded",
            )
        return (
            _upload_display("📄", "layout.csv", "Drag & drop or click to choose layout"),
            "upload-zone",
        )

    @app.callback(
        Output("upload-raw", "children"),
        Output("upload-raw", "className"),
        Input("upload-raw", "filename"),
        Input("upload-raw", "contents"),
        prevent_initial_call=True,
    )
    def _raw_upload_feedback(filename, contents):
        if contents:
            return (
                _upload_display(
                    "📈",
                    filename or "raw.csv",
                    "Drag & drop or click to choose raw readings",
                    filename or "raw.csv",
                ),
                "upload-zone loaded",
            )
        return (
            _upload_display("📈", "raw.csv", "Drag & drop or click to choose raw readings"),
            "upload-zone",
        )

    # @app.callback(
    #     Output("dataset-select", "options"),
    #     Output("dataset-select", "value"),
    #     Output("upload-status", "children"),
    #     Output("designer-raw-store", "data", allow_duplicate=True),
    #     Output("designer-layout", "data", allow_duplicate=True),
    #     Output("designer-selection", "data", allow_duplicate=True),
    #     Output("designer-save-status", "children", allow_duplicate=True),
    #     Input("btn-add-dataset", "n_clicks"),
    #     State("dataset-name", "value"),
    #     State("upload-layout", "contents"),
    #     State("upload-layout", "filename"),
    #     State("upload-raw", "contents"),
    #     State("upload-raw", "filename"),
    #     State("designer-layout", "data"),
    #     prevent_initial_call=True,
    # )
    # def add_dataset(
    #     n, name, layout_contents, layout_filename, raw_contents, raw_filename, designer_layout
    # ):
    #     if not n:
    #         return no_update, no_update, no_update, no_update, no_update, no_update, no_update

    #     # Normalize name
    #     name = (name or "").strip()

    #     # CASE A: both files present -> build dataset immediately (old behavior)
    #     if layout_contents and raw_contents:
    #         if not name:
    #             return (
    #                 no_update,
    #                 no_update,
    #                 dbc.Alert("Please enter a dataset name.", color="warning"),
    #                 no_update,
    #                 no_update,
    #                 no_update,
    #                 no_update,
    #             )
    #         if name in state.datasets:
    #             return (
    #                 no_update,
    #                 no_update,
    #                 dbc.Alert(f"A dataset named “{name}” already exists.", color="warning"),
    #                 no_update,
    #                 no_update,
    #                 no_update,
    #                 no_update,
    #             )
    #         try:
    #             layout_df = df_from_upload(layout_contents, layout_filename or "layout.csv")
    #         except Exception as e:
    #             return (
    #                 no_update,
    #                 no_update,
    #                 dbc.Alert(f"Could not read layout.csv: {e}", color="danger"),
    #                 no_update,
    #                 no_update,
    #                 no_update,
    #                 no_update,
    #             )
    #         try:
    #             raw_df = df_from_upload(raw_contents, raw_filename or "raw.csv")
    #         except Exception as e:
    #             return (
    #                 no_update,
    #                 no_update,
    #                 dbc.Alert(f"Could not read raw.csv: {e}", color="danger"),
    #                 no_update,
    #                 no_update,
    #                 no_update,
    #                 no_update,
    #             )
    #         try:
    #             tidy, titles, reps = build_dataset_from_dfs(layout_df, raw_df)
    #         except Exception as e:
    #             return (
    #                 no_update,
    #                 no_update,
    #                 dbc.Alert(f"Data processing failed: {e}", color="danger"),
    #                 no_update,
    #                 no_update,
    #                 no_update,
    #                 no_update,
    #             )
    #         if tidy.empty or not titles:
    #             return (
    #                 no_update,
    #                 no_update,
    #                 dbc.Alert(
    #                     "Parsed data is empty or layout produced no conditions.", color="danger"
    #                 ),
    #                 no_update,
    #                 no_update,
    #                 no_update,
    #                 no_update,
    #             )
    #         # Persist (non-fatal)
    #         try:
    #             save_uploaded_pair(DATA_DIR, name, layout_df, raw_df)
    #         except Exception:
    #             pass
    #         ds = Dataset(
    #             name=name,
    #             data=tidy,
    #             group_titles=titles,
    #             group_replicates=reps,
    #             unique_keys=sorted(titles.keys()),
    #         )
    #         state.datasets[name] = ds
    #         state.active = name
    #         options = [{"label": k, "value": k} for k in sorted(state.datasets.keys())]
    #         ok = dbc.Alert(
    #             f"Dataset “{name}” added: {len(ds.unique_keys)} conditions, {len(ds.data):,} rows.",
    #             color="success",
    #             dismissable=True,
    #             className="mt-2",
    #         )
    #         # designer outputs: no change
    #         return options, name, ok, no_update, no_update, no_update, no_update

    #     # CASE B: raw-only -> hand off to Designer (no dataset created yet)
    #     if raw_contents and not layout_contents:
    #         try:
    #             raw_df = df_from_upload(raw_contents, raw_filename or "raw.csv")
    #         except Exception as e:
    #             return (
    #                 no_update,
    #                 no_update,
    #                 dbc.Alert(f"Could not read raw.csv: {e}", color="danger"),
    #                 no_update,
    #                 no_update,
    #                 no_update,
    #                 no_update,
    #             )
    #         kind, rows, cols, wells = _infer_plate_from_raw_cols(raw_df)
    #         # seed Designer plate & selection
    #         base_layout = dict(designer_layout or {})
    #         base_layout["plate"] = dict(kind=kind, rows=rows, cols=cols)
    #         info = dbc.Alert(
    #             f"Raw uploaded: inferred {kind}-well plate; {len(wells)} wells detected. "
    #             "Now use the Designer to assign ligand/protein/buffer/conc, then click “Create dataset”.",
    #             color="info",
    #             className="mt-2",
    #         )
    #         # dataset-select unchanged; return designer stores
    #         return (
    #             no_update,
    #             no_update,
    #             info,
    #             dict(contents=raw_contents, filename=raw_filename or "raw.csv"),
    #             base_layout,
    #             wells,
    #             no_update,
    #         )

    #     # CASE C: layout-only or nothing -> explain next steps
    #     if layout_contents and not raw_contents:
    #         return (
    #             no_update,
    #             no_update,
    #             dbc.Alert(
    #                 "You uploaded layout.csv without raw.csv. Either upload both here, or upload raw only and use the Designer to build a layout.",
    #                 color="warning",
    #             ),
    #             no_update,
    #             no_update,
    #             no_update,
    #             no_update,
    #         )

    #     # nothing uploaded
    #     return (
    #         no_update,
    #         no_update,
    #         dbc.Alert("Please upload raw.csv, or both layout.csv and raw.csv.", color="warning"),
    #         no_update,
    #         no_update,
    #         no_update,
    #         no_update,
    #     )

    # Switch active dataset → update only plot-selector (the replicate accordion will rebuild via its own callback)
    @app.callback(
        Output("plot-selector", "options"),
        Output("plot-selector", "value"),
        Input("dataset-select", "value"),
        prevent_initial_call=True,
    )
    def switch_dataset(active_name):
        if not active_name or active_name not in state.datasets:
            return no_update, no_update

        state.active = active_name
        ds = state.datasets[active_name]
        options = [{"label": ds.group_titles[k], "value": k} for k in ds.unique_keys]
        default_value = [ds.unique_keys[0]] if ds.unique_keys else []
        return options, default_value


import re

_WELL_RE = re.compile(r"^\s*([A-Za-z]+)\s*0*([0-9]+)\s*$")


def _norm_well(s: str) -> str:
    m = _WELL_RE.match(str(s))
    return f"{m.group(1).upper()}{int(m.group(2))}" if m else str(s).strip()


def _infer_plate_from_raw_cols(raw_df):
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
