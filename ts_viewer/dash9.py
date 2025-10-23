# app.py
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from pydantic import BaseModel, Field
import plotly.io as pio
from plotly.subplots import make_subplots
import dash
from dash import Dash, dcc, html, ctx
from dash.dependencies import Input, Output, State, ALL
import dash_bootstrap_components as dbc

# ---------------------------------------------------------------------
# AESTHETICS
# ---------------------------------------------------------------------
pio.templates.default = "plotly_white"

THEME = dbc.themes.ZEPHYR  # pick your vibe: ZEPHYR, MINTY, LITERA, CYBORG (dark)
TITLE = "Thermal Shift Viewer"
PORT = 8056

# ---------------------------------------------------------------------
# DATA MODELS
# ---------------------------------------------------------------------
class Replicate(BaseModel):
    well_row: str
    well_column: str
    well_name: str

class UniqueCondition(BaseModel):
    full_name: str = ""
    concentration: float = 0.0  # uM as a float
    ligand_name: str = ""
    protein_name: str = ""
    buffer_condition: str = ""
    replicates: List[Replicate] = Field(default_factory=list)

# ---------------------------------------------------------------------
# HELPERS: Units, Keys, Colors
# ---------------------------------------------------------------------
_unit_re = re.compile(r"\s*([0-9]*\.?[0-9]+)\s*([mun]M)?\s*$", re.I)

def convert_concentration_to_float(s: str) -> float:
    """Return concentration in µM as float; accepts raw numbers or nM/uM/mM."""
    s = str(s)
    m = _unit_re.match(s)
    if not m:
        # fall back to 'just a float'
        return float(s.strip())
    val = float(m.group(1))
    unit = (m.group(2) or "").lower()
    if unit == "mm":
        return val * 1000.0
    if unit in ("um", ""):
        return val
    if unit == "nm":
        return val / 1000.0
    return val

def make_group_key(conc_uM: float, ligand: str, protein: str, buffer: str) -> str:
    """Stable JSON key (float, str, str, str)."""
    return json.dumps((float(conc_uM), str(ligand), str(protein), str(buffer)))

def parse_group_key(key_str: str) -> Tuple[float, str, str, str]:
    conc, ligand, protein, buffer = json.loads(key_str)
    return float(conc), ligand, protein, buffer

# Simple color utility: stable color per replicate name
def make_color_map(names: List[str]) -> Dict[str, str]:
    # Plotly qualitative palette (extend if needed)
    base = [
        "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728",
        "#9467bd", "#8c564b", "#e377c2", "#7f7f7f",
        "#bcbd22", "#17becf",
    ]
    cmap = {}
    for i, name in enumerate(sorted(set(names))):
        cmap[name] = base[i % len(base)]
    return cmap

# ---------------------------------------------------------------------
# LAYOUT PARSERS
# ---------------------------------------------------------------------
def get_unique_conditions(layout_data_path: Path, print_to_check: bool = False) -> Dict[str, UniqueCondition]:
    layout_df = pd.read_csv(layout_data_path)
    experiment_info: Dict[str, UniqueCondition] = {}

    for _, row in layout_df.iterrows():
        well_letter = row.get("Well", row.get("well", row.get("well_row")))
        if pd.isna(well_letter):
            continue
        well_letter = str(well_letter)

        for col in layout_df.columns:
            try:
                well_number_str = str(int(float(col)))  # handles '1.0'
            except ValueError:
                continue

            condition_str = row.get(col)
            if (
                pd.isna(condition_str)
                or condition_str == ""
                or condition_str == "0_0_0_0"
                or not isinstance(condition_str, str)
            ):
                continue

            parts = condition_str.split("_")
            if len(parts) < 4:
                continue

            concentration_str_part = parts[-4]
            ligand_name_part = parts[-3]
            protein_name_part = parts[-2]
            buffer_condition_part = parts[-1]
            concentration_float = convert_concentration_to_float(concentration_str_part)

            replicate_obj = Replicate(
                well_row=well_letter,
                well_column=well_number_str,
                well_name=well_letter + well_number_str,
            )

            if condition_str not in experiment_info:
                experiment_info[condition_str] = UniqueCondition(
                    full_name=condition_str,
                    concentration=concentration_float,
                    ligand_name=ligand_name_part,
                    protein_name=protein_name_part,
                    buffer_condition=buffer_condition_part,
                )
            experiment_info[condition_str].replicates.append(replicate_obj)

    if print_to_check:
        info_path = layout_data_path.parent / (layout_data_path.stem + "_experiment_info.json")
        try:
            with open(info_path, "w") as f:
                json.dump({k: v.model_dump() for k, v in experiment_info.items()}, f, indent=2)
            print(f"Experiment info saved to: {info_path}")
        except Exception as e:
            print(f"Error saving experiment_info.json: {e}")

    return experiment_info

def initial_raw_data_organize_for_dash(
    initial_raw_readings_df: pd.DataFrame,
    experiment_info: Dict[str, UniqueCondition],
) -> pd.DataFrame:
    if "Temperature" not in initial_raw_readings_df.columns:
        print("Error: 'Temperature' column not found in raw readings CSV.")
        return pd.DataFrame()

    raw_long = initial_raw_readings_df.melt(
        id_vars=["Temperature"], var_name="replicate_id", value_name="value"
    )

    # map well -> condition
    well_to_condition = {}
    for _, uc in experiment_info.items():
        for rep in uc.replicates:
            well_to_condition[rep.well_name] = dict(
                concentration=float(uc.concentration),
                ligand=uc.ligand_name,
                protein=uc.protein_name,
                buffer=uc.buffer_condition,
            )

    raw_long["concentration"] = raw_long["replicate_id"].map(lambda w: well_to_condition.get(w, {}).get("concentration"))
    raw_long["ligand"]        = raw_long["replicate_id"].map(lambda w: well_to_condition.get(w, {}).get("ligand"))
    raw_long["protein"]       = raw_long["replicate_id"].map(lambda w: well_to_condition.get(w, {}).get("protein"))
    raw_long["buffer"]        = raw_long["replicate_id"].map(lambda w: well_to_condition.get(w, {}).get("buffer"))

    raw_long.dropna(subset=["concentration", "ligand", "protein", "buffer"], inplace=True)

    # numeric coercion
    raw_long["Temperature"] = pd.to_numeric(raw_long["Temperature"], errors="coerce")
    raw_long["value"] = pd.to_numeric(raw_long["value"], errors="coerce")
    raw_long.dropna(subset=["Temperature", "value", "concentration"], inplace=True)

    # stable group key
    raw_long["group_key"] = raw_long.apply(
        lambda r: make_group_key(r["concentration"], r["ligand"], r["protein"], r["buffer"]),
        axis=1,
    )

    return raw_long

# ---------------------------------------------------------------------
# PATHS + DATA LOADING
# ---------------------------------------------------------------------
LAYOUT_CSV_PATH = Path("layout_real.csv")
RAW_READINGS_CSV_PATH = Path("raw_data_real2.csv")

raw_data_initial = pd.DataFrame()
group_titles_map: Dict[str, str] = {}
group_replicates_map: Dict[str, List[str]] = {}
unique_group_keys_str: List[str] = []

if LAYOUT_CSV_PATH.exists() and RAW_READINGS_CSV_PATH.exists():
    print(f"Loading layout from: {LAYOUT_CSV_PATH}")
    print(f"Loading raw data from: {RAW_READINGS_CSV_PATH}")
    try:
        experiment_layout_info = get_unique_conditions(LAYOUT_CSV_PATH, print_to_check=False)
        initial_raw_readings_df = pd.read_csv(RAW_READINGS_CSV_PATH)

        raw_data_initial = initial_raw_data_organize_for_dash(initial_raw_readings_df, experiment_layout_info)

        if not raw_data_initial.empty:
            # Build UI maps
            group_titles_map = {}
            group_replicates_map = {}
            for cond_full, uc in experiment_layout_info.items():
                key = make_group_key(uc.concentration, uc.ligand_name, uc.protein_name, uc.buffer_condition)
                group_titles_map[key] = f"C{uc.concentration:g} {uc.ligand_name} + {uc.protein_name} in {uc.buffer_condition}"
                group_replicates_map[key] = sorted([rep.well_name for rep in uc.replicates])
            unique_group_keys_str = sorted(group_titles_map.keys())
            print(f"Processed {len(unique_group_keys_str)} unique conditions.")
        else:
            print("Warning: Processing resulted in empty DataFrame. Falling back to dummy data.")
    except Exception as e:
        print(f"Error during processing: {e}. Falling back to dummy data.")

if raw_data_initial.empty or not unique_group_keys_str:
    print("Using DUMMY DATA.")
    np.random.seed(42)
    raw_data_list = []
    conditions = [
        (10.0, "LigandA", "ProteinX", "Buffer1"),
        (10.0, "LigandA", "NPC", "Buffer1"),
        (20.0, "LigandA", "ProteinX", "Buffer1"),
        (20.0, "LigandA", "NPC", "Buffer1"),
        (10.0, "LigandA", "ProteinY", "Buffer1"),
        (5.0, "LigandB", "ProteinZ", "Buffer2"),
        (5.0, "LigandB", "NPC", "Buffer2"),
    ]
    group_titles_map, group_replicates_map = {}, {}
    for i, (conc, ligand, protein, buffer) in enumerate(conditions):
        key = make_group_key(conc, ligand, protein, buffer)
        group_titles_map[key] = f"C{conc:g} {ligand} + {protein} in {buffer}"
        reps = [f"{protein}-R{j+1}" for j in range(2 if protein == "NPC" else 3)]
        group_replicates_map[key] = reps
        for rep_idx, rep in enumerate(reps):
            for t in np.linspace(20, 80, 61):
                val = (
                    1 / (1 + np.exp((t - (50 + i * 2 - rep_idx)) / 5))
                    + (conc * 0.001)
                    + (np.random.rand() * 0.03)
                    + (0.05 if protein == "NPC" else 0.5)
                )
                raw_data_list.append(
                    dict(
                        Temperature=t,
                        replicate_id=rep,
                        value=val,
                        concentration=conc,
                        ligand=ligand,
                        protein=protein,
                        buffer=buffer,
                        group_key=key,
                    )
                )
    raw_data_initial = pd.DataFrame(raw_data_list)
    unique_group_keys_str = sorted(group_titles_map.keys())
    print(f"Dummy data generated with {len(unique_group_keys_str)} conditions.")

# ---------------------------------------------------------------------
# COMPUTE PIPELINE (reusable for figure & downloads)
# ---------------------------------------------------------------------
def compute_series_for_group(
    group_key: str,
    selected_replicates: List[str],
    bg_sub_enabled: bool,
    all_data: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Returns:
      - summary_df with columns:
        ['Temperature','avg','avg_norm','neg_deriv','neg_deriv_norm'] (norm columns only present if computable)
      - reps_df (long form) filtered to selected reps for this group (Temperature, replicate_id, value)
    Background subtraction:
      If enabled and protein!='NPC', subtract NPC group's average aligned by Temperature (inner join).
    """
    conc, ligand, protein, buffer = parse_group_key(group_key)
    group_df_all = all_data[all_data["group_key"] == group_key].copy()

    # filter to selected replicates
    if selected_replicates:
        reps_df = group_df_all[group_df_all["replicate_id"].isin([str(r) for r in selected_replicates])].copy()
    else:
        reps_df = group_df_all.copy()

    if reps_df.empty:
        return pd.DataFrame(), pd.DataFrame()

    # average per Temperature
    avg_df = (
        reps_df.groupby("Temperature", as_index=False)["value"]
        .mean()
        .rename(columns={"value": "avg"})
    )

    # background subtraction if needed
    if bg_sub_enabled and protein != "NPC":
        npc_key = make_group_key(conc, ligand, "NPC", buffer)
        npc_df_all = all_data[all_data["group_key"] == npc_key]
        if not npc_df_all.empty:
            # NPC reps selection—mirror selection if those replicate IDs exist; else all NPC reps
            # build selected npc reps list
            npc_default_reps = group_replicates_map.get(npc_key, [])
            npc_selected = npc_default_reps  # could also mirror by index/length
            npc_use = npc_df_all[npc_df_all["replicate_id"].isin(npc_selected)]
            if not npc_use.empty:
                npc_avg = npc_use.groupby("Temperature", as_index=False)["value"].mean().rename(columns={"value": "npc"})
                merged = pd.merge(avg_df, npc_avg, on="Temperature", how="inner")
                if not merged.empty:
                    avg_df = pd.DataFrame({
                        "Temperature": merged["Temperature"],
                        "avg": merged["avg"] - merged["npc"]
                    })

    # normalized average (0–1) if non-constant
    summary = avg_df.copy()
    if not summary.empty:
        a_min, a_max = summary["avg"].min(), summary["avg"].max()
        if a_max > a_min:
            summary["avg_norm"] = (summary["avg"] - a_min) / (a_max - a_min)
        else:
            summary["avg_norm"] = 0.5

    # derivative (negative) + normalized
    if len(summary) > 1:
        temps = summary["Temperature"].to_numpy()
        vals = summary["avg"].to_numpy()
        order = np.argsort(temps)
        temps_s = temps[order]
        vals_s = vals[order]
        deriv = np.gradient(vals_s, temps_s)
        neg_deriv = -1.0 * deriv
        dmin, dmax = float(np.min(neg_deriv)), float(np.max(neg_deriv))
        if dmax > dmin:
            norm = (neg_deriv - dmin) / (dmax - dmin)
        else:
            norm = np.full_like(neg_deriv, 0.5, dtype=float)
        summary = pd.DataFrame({
            "Temperature": temps_s,
            "avg": vals_s,
            "avg_norm": np.interp(temps_s, summary["Temperature"], summary["avg_norm"]),
            "neg_deriv": neg_deriv,
            "neg_deriv_norm": norm
        })
    return summary, reps_df[["Temperature", "replicate_id", "value"]].copy()

# ---------------------------------------------------------------------
# DASH APP
# ---------------------------------------------------------------------
app: Dash = dash.Dash(
    __name__,
    external_stylesheets=[THEME],
    suppress_callback_exceptions=True,
    title=TITLE,
)
server = app.server  # for gunicorn

# Build options
plot_options = [
    {"label": group_titles_map[key], "value": key} for key in unique_group_keys_str
]

# Sidebar (controls)
controls = dbc.Card(
    [
        html.Div(
            [
                html.H4("Select Conditions", className="mb-2"),
                dcc.Dropdown(
                    id="plot-selector",
                    options=plot_options,
                    value=([unique_group_keys_str[0]] if unique_group_keys_str else []),
                    multi=True,
                    placeholder="Pick one or more...",
                    className="mb-3",
                ),
                dbc.Accordion(
                    id="replicate-accordion",
                    start_collapsed=True,
                    always_open=False,
                    className="mb-3",
                    children=[
                        # dynamically populated
                    ],
                ),
                html.H5("Processing", className="mt-2"),
                dbc.Checklist(
                    id="bg-subtract-toggle",
                    options=[{"label": " Background subtraction (NPC)", "value": "BG"}],
                    value=[],
                    switch=True,
                    className="mb-2",
                ),
                dbc.Checklist(
                    id="normalize-toggle",
                    options=[{"label": " Normalize average to 0–1 (secondary Y)", "value": "NORM"}],
                    value=[],
                    switch=True,
                    className="mb-2",
                ),
                dbc.Checklist(
                    id="derivative-toggle",
                    options=[{"label": " Plot -dY/dT (normalized, secondary Y)", "value": "DERIV"}],
                    value=[],
                    switch=True,
                    className="mb-4",
                ),
                html.H5("Downloads"),
                dbc.Button("Processed Figure (HTML)", id="btn-download-avg-fig", className="me-2 mb-2", color="primary"),
                dbc.Button("Processed Data (CSV)", id="btn-download-avg-csv", className="me-2 mb-2", color="secondary"),
                dbc.Button("Metadata (CSV)", id="btn-download-metadata-csv", className="mb-2", color="secondary"),
                dcc.Download(id="download-avg-fig-html"),
                dcc.Download(id="download-avg-data-csv"),
                dcc.Download(id="download-metadata-csv"),
            ]
        )
    ],
    body=True,
    className="shadow-sm",
)

# Main plotting card
plot_card = dbc.Card(
    [
        dbc.CardHeader(
            [
                html.Div(
                    [
                        html.H4("Interactive Multi-Plot Viewer", className="m-0"),
                        html.Small(
                            "Averaging, background subtraction, normalization & derivative",
                            className="text-muted",
                        ),
                    ]
                )
            ]
        ),
        dbc.CardBody(
            dcc.Graph(id="dynamic-subplot-graph", style={"height": "84vh"})
        ),
    ],
    className="shadow-sm",
)

app.layout = dbc.Container(
    fluid=True,
    children=[
        dbc.Navbar(
            [
                dbc.NavbarBrand(TITLE, className="ms-2"),
                dbc.Nav(
                    [
                        dbc.Badge(f"{len(unique_group_keys_str)} conditions", color="info", className="ms-2"),
                    ],
                    className="ms-auto",
                    navbar=True,
                ),
            ],
            color="dark",
            dark=True,
            className="mb-3 rounded",
        ),
        dbc.Row(
            [
                dbc.Col(controls, xs=12, md=4, lg=3),
                dbc.Col(plot_card, xs=12, md=8, lg=9),
            ],
            className="g-3",
        ),
        # Stores for data (optional future use)
        dcc.Store(id="store-data-ready", data=True),
    ],
)

# ---------------------------------------------------------------------
# CALLBACKS
# ---------------------------------------------------------------------
@app.callback(
    Output("replicate-accordion", "children"),
    Input("plot-selector", "value"),
)
def populate_replicate_selectors(selected_keys: List[str]):
    if not selected_keys:
        return [
            dbc.AccordionItem("Select a condition above to choose replicates.", title="Replicates")
        ]
    items = []
    for key in selected_keys:
        title = group_titles_map.get(key, "Unknown")
        reps = group_replicates_map.get(key, [])
        checklist_id = {"type": "replicate-filter", "group_key": key}
        items.append(
            dbc.AccordionItem(
                [
                    dbc.Checklist(
                        id=checklist_id,
                        options=[{"label": r, "value": r} for r in reps],
                        value=reps,  # default select all
                        inline=True,
                    )
                ],
                title=title,
            )
        )
    return items

def get_selected_reps_map(selected_keys: List[str], rep_values, rep_ids):
    out = {}
    if selected_keys and rep_ids:
        for i, rid in enumerate(rep_ids):
            if isinstance(rid, dict):
                gk = rid.get("group_key")
                if gk in selected_keys:
                    out[gk] = rep_values[i] if rep_values and i < len(rep_values) else []
    for k in selected_keys:
        out.setdefault(k, group_replicates_map.get(k, []))
    return out

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
    fig_empty = go.Figure()
    fig_empty.update_layout(
        xaxis={"visible": False},
        yaxis={"visible": False},
        annotations=[dict(text="Select a condition to begin", showarrow=False, font=dict(size=18))]
    )
    if not selected_keys or raw_data_initial.empty:
        return fig_empty

    bg_enabled = "BG" in (bg_vals or [])
    norm_enabled = "NORM" in (norm_vals or [])
    deriv_enabled = "DERIV" in (deriv_vals or [])

    # grid sizing
    n = len(selected_keys)
    if n == 1:
        cols, rows = 1, 1
    elif n == 2:
        cols, rows = 2, 1
    elif n <= 4:
        cols, rows = 2, math.ceil(n / 2)
    else:
        cols, rows = 3, math.ceil(n / 3)

    specs = [[{"secondary_y": True} for _ in range(cols)] for _ in range(rows)]
    subtitles = [group_titles_map.get(k, "Plot") for k in selected_keys]

    fig = make_subplots(rows=rows, cols=cols, subplot_titles=subtitles, specs=specs)

    reps_map = get_selected_reps_map(selected_keys, rep_values, rep_ids)

    # precompute color map for replicates (across all selected)
    all_rep_names = []
    for k in selected_keys:
        all_rep_names.extend(reps_map.get(k, []))
    color_map = make_color_map(all_rep_names)

    r, c = 1, 1
    for key in selected_keys:
        title = group_titles_map.get(key, key)
        sel_reps = reps_map.get(key, [])

        summary, reps_df = compute_series_for_group(
            group_key=key,
            selected_replicates=sel_reps,
            bg_sub_enabled=bg_enabled,
            all_data=raw_data_initial,
        )

        # replicate traces (primary y)
        if not reps_df.empty:
            for rep_name, df_rep in reps_df.groupby("replicate_id"):
                fig.add_trace(
                    go.Scatter(
                        x=df_rep["Temperature"],
                        y=df_rep["value"],
                        mode="lines",
                        line=dict(width=1.5, color=color_map.get(rep_name, None)),
                        name=f"{title} · {rep_name}",
                        legendgroup=title,
                        showlegend=False,  # keep legend tidy—toggle via average/derivative only
                        hovertemplate="T=%{x:.2f} °C<br>Value=%{y:.4f}<extra>" + rep_name + "</extra>",
                    ),
                    row=r, col=c, secondary_y=False
                )

        # average (primary or secondary y if normalized)
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
                        hovertemplate="T=%{x:.2f} °C<br>Norm Avg=%{y:.3f}<extra>" + title + "</extra>",
                    ),
                    row=r, col=c, secondary_y=True
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
                        hovertemplate="T=%{x:.2f} °C<br>Avg=%{y:.4f}<extra>" + title + "</extra>",
                    ),
                    row=r, col=c, secondary_y=False
                )

            # derivative (normalized) on secondary y
            if deriv_enabled and "neg_deriv_norm" in summary.columns:
                fig.add_trace(
                    go.Scatter(
                        x=summary["Temperature"],
                        y=summary["neg_deriv_norm"],
                        mode="lines",
                        name=f"{title} · -dY/dT (Norm)",
                        legendgroup=title,
                        line=dict(width=2, dash="dot"),
                        hovertemplate="T=%{x:.2f} °C<br>-dY/dT (norm)=%{y:.3f}<extra>" + title + "</extra>",
                    ),
                    row=r, col=c, secondary_y=True
                )
                show_secondary = True

        # axes
        fig.update_xaxes(title_text="Temperature (°C)", row=r, col=c, tickfont=dict(size=10), title_font=dict(size=11))
        fig.update_yaxes(title_text="Value", secondary_y=False, row=r, col=c, tickfont=dict(size=10), title_font=dict(size=11))

        if show_secondary:
            fig.update_yaxes(
                title_text="Normalized (0–1)",
                secondary_y=True, row=r, col=c,
                range=[0, 1], tickfont=dict(size=10), title_font=dict(size=11)
            )
        else:
            fig.update_yaxes(visible=False, secondary_y=True, row=r, col=c)

        c += 1
        if c > cols:
            c = 1
            r += 1

    fig.update_layout(
        height=max(540, rows * 360),
        legend=dict(title="Traces", font=dict(size=10), orientation="h", yanchor="bottom", y=-0.08),
        margin=dict(l=60, r=40, t=60, b=80),
    )

    # For single plot, promote the subplot title to main title and remove annotation
    if len(selected_keys) == 1 and fig.layout.annotations:
        t = subtitles[0]
        fig.update_layout(title_text=t)
        fig.layout.annotations = tuple(
            ann for ann in fig.layout.annotations if ann.text != t
        )

    return fig

# -------------------- DOWNLOADS --------------------
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
def download_fig(n_clicks, selected_keys, rep_values, bg_vals, norm_vals, deriv_vals, rep_ids):
    if not n_clicks or not selected_keys or raw_data_initial.empty:
        return dash.no_update

    bg_enabled = "BG" in (bg_vals or [])
    norm_enabled = "NORM" in (norm_vals or [])
    deriv_enabled = "DERIV" in (deriv_vals or [])

    # Build a single big figure (same look as main) for download
    # re-use graph callback logic
    # To avoid duplicating code, we could call update_graph, but Dash discourages calling callbacks directly.
    # Here we duplicate minimal logic (layout + traces) for a single-page export.

    # simple: call update_graph-like function directly
    rep_ids = rep_ids or []
    rep_map = get_selected_reps_map(selected_keys, rep_values, rep_ids)

    n = len(selected_keys)
    if n == 1:
        cols, rows = 1, 1
    elif n == 2:
        cols, rows = 2, 1
    elif n <= 4:
        cols, rows = 2, math.ceil(n / 2)
    else:
        cols, rows = 3, math.ceil(n / 3)

    specs = [[{"secondary_y": True} for _ in range(cols)] for _ in range(rows)]
    subtitles = [group_titles_map.get(k, "Plot") for k in selected_keys]
    fig = make_subplots(rows=rows, cols=cols, subplot_titles=subtitles, specs=specs)

    # colors
    all_rep_names = []
    for k in selected_keys:
        all_rep_names.extend(rep_map.get(k, []))
    color_map = make_color_map(all_rep_names)

    r, c = 1, 1
    for key in selected_keys:
        title = group_titles_map.get(key, key)
        sel_reps = rep_map.get(key, [])

        summary, reps_df = compute_series_for_group(key, sel_reps, bg_enabled, raw_data_initial)

        # replicate traces
        if not reps_df.empty:
            for rep_name, df_rep in reps_df.groupby("replicate_id"):
                fig.add_trace(
                    go.Scatter(
                        x=df_rep["Temperature"],
                        y=df_rep["value"],
                        mode="lines",
                        line=dict(width=1.5, color=color_map.get(rep_name, None)),
                        name=f"{title} · {rep_name}",
                        legendgroup=title,
                        showlegend=False,
                    ),
                    row=r, col=c, secondary_y=False
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
                    row=r, col=c, secondary_y=True
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
                    row=r, col=c, secondary_y=False
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
                    row=r, col=c, secondary_y=True
                )
                show_secondary = True

        fig.update_xaxes(title_text="Temperature (°C)", row=r, col=c)
        fig.update_yaxes(title_text="Value", secondary_y=False, row=r, col=c)
        if show_secondary:
            fig.update_yaxes(title_text="Normalized (0–1)", secondary_y=True, row=r, col=c, range=[0, 1])
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
        template="plotly_white",
        title_text=(subtitles[0] if len(selected_keys) == 1 else None),
    )

    return dict(
        content=fig.to_html(full_html=True, include_plotlyjs="cdn"),
        filename="processed_plots.html",
    )

@app.callback(
    Output("download-avg-data-csv", "data"),
    Input("btn-download-avg-csv", "n_clicks"),
    State("plot-selector", "value"),
    State({"type": "replicate-filter", "group_key": ALL}, "value"),
    State("bg-subtract-toggle", "value"),
    State("normalize-toggle", "value"),
    State("derivative-toggle", "value"),
    State({"type": "replicate-filter", "group_key": ALL}, "id"),
    prevent_initial_call=True,
)
def download_data_csv(n_clicks, selected_keys, rep_values, bg_vals, norm_vals, deriv_vals, rep_ids):
    if not n_clicks or not selected_keys or raw_data_initial.empty:
        return dash.no_update

    bg_enabled = "BG" in (bg_vals or [])
    rep_map = get_selected_reps_map(selected_keys, rep_values, rep_ids or [])

    rows = []
    for key in selected_keys:
        title = group_titles_map.get(key, key)
        summary, _ = compute_series_for_group(key, rep_map.get(key, []), bg_enabled, raw_data_initial)
        if summary.empty:
            continue
        conc, ligand, protein, buffer = parse_group_key(key)
        df = summary.copy()
        df.insert(0, "group_key", key)
        df.insert(1, "title", title)
        df.insert(2, "concentration_uM", conc)
        df.insert(3, "ligand", ligand)
        df.insert(4, "protein", protein)
        df.insert(5, "buffer", buffer)
        rows.append(df)

    if not rows:
        tmp = pd.DataFrame([{"message": "No data available for the current selection."}])
        return dcc.send_data_frame(tmp.to_csv, "processed_data.csv", index=False)

    out = pd.concat(rows, ignore_index=True)
    # ensure columns present (even if NaN)
    for col in ["avg", "avg_norm", "neg_deriv", "neg_deriv_norm"]:
        if col not in out.columns:
            out[col] = np.nan

    return dcc.send_data_frame(out.to_csv, "processed_data.csv", index=False)

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
def download_meta_csv(n_clicks, selected_keys, rep_values, bg_vals, norm_vals, deriv_vals, rep_ids):
    if not n_clicks or not selected_keys:
        return dash.no_update

    bg_enabled = "BG" in (bg_vals or [])
    norm_enabled = "NORM" in (norm_vals or [])
    deriv_enabled = "DERIV" in (deriv_vals or [])
    rep_map = get_selected_reps_map(selected_keys, rep_values, rep_ids or [])

    rows = []
    for key in selected_keys:
        conc, ligand, protein, buffer = parse_group_key(key)
        rows.append(
            dict(
                group_key=key,
                title=group_titles_map.get(key, key),
                concentration_uM=conc,
                ligand=ligand,
                protein=protein,
                buffer=buffer,
                selected_replicates=";".join(rep_map.get(key, [])),
                background_subtraction=bg_enabled,
                normalize_average_0_1=norm_enabled,
                plot_derivative_norm=deriv_enabled,
            )
        )
    df = pd.DataFrame(rows)
    return dcc.send_data_frame(df.to_csv, "metadata.csv", index=False)

# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True, port=PORT)
