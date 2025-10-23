import dash
from collections import defaultdict
from typing import Optional, List, Dict
from pathlib import Path
from pydantic import BaseModel, Field, FilePath
from dash import dcc, html, ctx
from dash.dependencies import Input, Output, State, ALL
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np  # Ensure NumPy is imported
import math
import json

# 1. --- Data Preparation (Same as your last version with Concentration) ---
np.random.seed(42)


# --- Helper Classes (from your provided code) ---
class Replicate(BaseModel):
    well_row: str
    well_column: str
    well_name: str


class UniqueCondition(BaseModel):
    full_name: str = ""  # e.g., "10_LigandA_ProteinX_Buffer1"
    concentration: float = 0.0
    ligand_name: str = ""
    protein_name: str = ""
    buffer_condition: str = ""
    replicates: List[Replicate] = Field(default_factory=list)


def convert_concentration_to_float(concentration: str) -> float:
    if "uM" in concentration:
        return float(concentration.replace("uM", "").strip())
    elif "mM" in concentration:
        return float(concentration.replace("mM", "").strip()) * 1000  # Convert mM to uM
    elif "nM" in concentration:
        c = float(concentration.replace("nM", "").strip())
        if c == 0:
            return 0.0
        return float(concentration.replace("nM", "").strip()) / 1000  # Convert nM to uM
    else:
        return float(concentration.strip())


# --- Helper Functions (Adapted from your provided code) ---
def get_unique_conditions(
    layout_data_path: Path, print_to_check: Optional[bool] = False
) -> Dict[str, UniqueCondition]:
    """
    Parses the layout CSV to identify unique experimental conditions and their replicates.
    The key of the returned dictionary is the 'full_name' string (e.g., "Conc_Ligand_Protein_Buffer").
    """
    layout_df = pd.read_csv(layout_data_path)
    experiment_info: Dict[str, UniqueCondition] = {}  # Use a standard dict

    for index, row_data in layout_df.iterrows():
        # Attempt to get well row identifier, case-insensitive
        well_letter = row_data.get(
            "Well", row_data.get("well", row_data.get("well_row"))
        )
        if pd.isna(well_letter):
            # print(f"Skipping row {index} due to missing well row identifier.")
            continue
        well_letter = str(well_letter)

        for col_header in layout_df.columns:
            # Try to interpret column header as a well column number
            try:
                # Ensure that if col_header is already numeric, it's converted to string.
                # If it's a string like "1", "2", int() works. If it's "Temperature", it fails.
                well_number_str = str(int(float(col_header)))  # Handles "1.0" or "1"
            except ValueError:
                # If conversion fails, it's not a well column number (e.g., "Well", "Temperature")
                continue

            condition_str = row_data.get(col_header)

            if (
                pd.isna(condition_str)
                or condition_str == ""
                or condition_str == "0_0_0_0"
                or not isinstance(condition_str, str)
            ):
                continue

            parts = condition_str.split("_")
            if len(parts) < 4:
                # print(f"Skipping malformed condition string: {condition_str} at {well_letter}{well_number_str}")
                continue

            full_name = condition_str  # This is the C_L_P_B string from the cell
            concentration_str_part = parts[-4]
            concentration_float = convert_concentration_to_float(concentration_str_part)
            ligand_name_part = parts[-3]
            protein_name_part = parts[-2]
            buffer_condition_part = parts[-1]

            replicate_obj = Replicate(
                well_row=well_letter,
                well_column=well_number_str,
                well_name=well_letter + well_number_str,
            )

            if full_name not in experiment_info:
                experiment_info[full_name] = UniqueCondition(
                    full_name=full_name,
                    concentration=concentration_float,  # Store as string from parts
                    ligand_name=ligand_name_part,
                    protein_name=protein_name_part,
                    buffer_condition=buffer_condition_part,
                    replicates=[],  # Initialize with an empty list
                )
            experiment_info[full_name].replicates.append(replicate_obj)

    if print_to_check:
        info_path = layout_data_path.parent / (
            layout_data_path.stem + "_experiment_info.json"
        )
        try:
            with open(info_path, "w") as f:
                json.dump(
                    {k: v.model_dump() for k, v in experiment_info.items()}, f, indent=4
                )
            print(f"Experiment info saved to: {info_path}")
        except Exception as e:
            print(f"Error saving experiment_info.json: {e}")
    return experiment_info


def initial_raw_data_organize_for_dash(
    initial_raw_readings_df: pd.DataFrame,
    experiment_info: Dict[str, UniqueCondition],
) -> pd.DataFrame:
    """
    Organizes the raw data based on the layout data into a format suitable for the Dash app.
    The output DataFrame will have columns:
    Temperature, replicate_id (well name), value, concentration (numeric), ligand, protein, buffer.
    """
    # Melt the raw data: 'Temperature' as id_var, other columns (wells) become 'replicate_id'
    if "Temperature" not in initial_raw_readings_df.columns:
        print("Error: 'Temperature' column not found in raw readings CSV.")
        return pd.DataFrame()

    raw_data_long = initial_raw_readings_df.melt(
        id_vars=["Temperature"], var_name="replicate_id", value_name="value"
    )

    # Create a mapping from well_name (replicate_id) to its condition details
    well_to_condition_details = {}
    for condition_full_name_key, uc_object in experiment_info.items():
        for rep in uc_object.replicates:
            try:
                # Concentration from layout is string, convert to numeric for the DataFrame
                numeric_conc = float(uc_object.concentration)
            except ValueError:
                print(
                    f"Warning: Could not convert concentration '{uc_object.concentration}' to numeric for well {rep.well_name}. Skipping this well's annotation."
                )
                continue

            well_to_condition_details[rep.well_name] = {
                "concentration": numeric_conc,  # Store as numeric
                "ligand": uc_object.ligand_name,
                "protein": uc_object.protein_name,
                "buffer": uc_object.buffer_condition,
            }

    # Add condition columns to the long DataFrame
    raw_data_long["concentration"] = raw_data_long["replicate_id"].map(
        lambda w: well_to_condition_details.get(w, {}).get("concentration")
    )
    raw_data_long["ligand"] = raw_data_long["replicate_id"].map(
        lambda w: well_to_condition_details.get(w, {}).get("ligand")
    )
    raw_data_long["protein"] = raw_data_long["replicate_id"].map(
        lambda w: well_to_condition_details.get(w, {}).get("protein")
    )
    raw_data_long["buffer"] = raw_data_long["replicate_id"].map(
        lambda w: well_to_condition_details.get(w, {}).get("buffer")
    )

    # Drop rows where well_id from raw data was not found in layout (i.e., no condition info)
    raw_data_long.dropna(
        subset=["concentration", "ligand", "protein", "buffer"], inplace=True
    )

    # Ensure essential columns are numeric
    raw_data_long["Temperature"] = pd.to_numeric(
        raw_data_long["Temperature"], errors="coerce"
    )
    raw_data_long["value"] = pd.to_numeric(raw_data_long["value"], errors="coerce")
    # 'concentration' should already be numeric from the mapping step

    # Drop rows if essential numeric conversions failed
    raw_data_long.dropna(subset=["Temperature", "value", "concentration"], inplace=True)

    return raw_data_long


# --- END OF DATA PROCESSING ADAPTER ---


# --- Data Loading Section ---
# !!! IMPORTANT: REPLACE THESE PATHS WITH YOUR ACTUAL FILE PATHS !!!
LAYOUT_CSV_PATH = Path("layout_real.csv")  # e.g., Path("data/plate_layout.csv")
RAW_READINGS_CSV_PATH = Path(
    "raw_data_real2.csv"
)  # e.g., Path("data/thermal_shift_data.csv")

# Initialize Dash data structures
raw_data_initial = pd.DataFrame()
group_titles_map = {}
group_replicates_map = {}
unique_group_keys_str = []

# Attempt to load and process real data
if LAYOUT_CSV_PATH.exists() and RAW_READINGS_CSV_PATH.exists():
    print(f"Loading layout from: {LAYOUT_CSV_PATH}")
    print(f"Loading raw data from: {RAW_READINGS_CSV_PATH}")
    try:
        experiment_layout_info = get_unique_conditions(
            LAYOUT_CSV_PATH, print_to_check=False
        )  # Set True to debug
        initial_raw_readings_df = pd.read_csv(RAW_READINGS_CSV_PATH)

        # This is the main DataFrame the Dash app will use
        raw_data_initial = initial_raw_data_organize_for_dash(
            initial_raw_readings_df, experiment_layout_info
        )

        if not raw_data_initial.empty:
            # Populate group_titles_map and group_replicates_map for Dash UI
            # These maps use a key: json.dumps((numeric_conc, ligand, protein, buffer))
            for condition_full_name, uc_object in experiment_layout_info.items():
                try:
                    # Concentration from uc_object.concentration is a string. Convert to float for the key.
                    numeric_conc = float(uc_object.concentration)
                except ValueError:
                    # print(f"Skipping condition '{condition_full_name}' for UI maps due to invalid concentration: {uc_object.concentration}")
                    continue

                dash_group_key_tuple = (
                    numeric_conc,
                    uc_object.ligand_name,
                    uc_object.protein_name,
                    uc_object.buffer_condition,
                )
                dash_group_key_str = json.dumps(dash_group_key_tuple)

                # Use original string concentration for the title for display consistency
                group_titles_map[dash_group_key_str] = (
                    f"C{uc_object.concentration} {uc_object.ligand_name} + {uc_object.protein_name} in {uc_object.buffer_condition}"
                )
                group_replicates_map[dash_group_key_str] = sorted(
                    [rep.well_name for rep in uc_object.replicates]
                )

            unique_group_keys_str = sorted(list(group_titles_map.keys()))
            print(
                f"Successfully processed real data. Found {len(unique_group_keys_str)} unique conditions for UI."
            )
            # print("Sample of final raw_data_initial for Dash:")
            # print(raw_data_initial.head())
        else:
            print(
                "Warning: Real data processing resulted in an empty DataFrame. Check CSVs and processing functions."
            )
    except Exception as e:
        print(f"Error during real data processing: {e}")
        print("Falling back to dummy data or empty state.")

# Fallback to dummy data if real data loading failed or files not found
if raw_data_initial.empty or not unique_group_keys_str:
    print("Using DUMMY DATA as real data loading failed or produced no conditions.")
    np.random.seed(42)
    raw_data_list_of_dicts_dummy = []
    conditions_for_dummy_data = (
        [  # Ensure this matches the structure used by Dash callbacks
            (10.0, "LigandA", "ProteinX", "Buffer1"),
            (10.0, "LigandA", "NPC", "Buffer1"),
            (20.0, "LigandA", "ProteinX", "Buffer1"),
            (20.0, "LigandA", "NPC", "Buffer1"),
            (10.0, "LigandA", "ProteinY", "Buffer1"),
            (5.0, "LigandB", "ProteinZ", "Buffer2"),
            (5.0, "LigandB", "NPC", "Buffer2"),
        ]
    )
    # Re-initialize maps for dummy data
    group_titles_map = {}
    group_replicates_map = {}
    for i, (conc, ligand, protein, buffer) in enumerate(conditions_for_dummy_data):
        group_key_tuple = (conc, ligand, protein, buffer)  # conc is already float here
        group_key_str = json.dumps(group_key_tuple)
        group_titles_map[group_key_str] = f"C{conc} {ligand} + {protein} in {buffer}"
        current_group_replicates_dummy = []
        num_replicates_dummy = 2 if protein == "NPC" else 3
        for replicate_idx in range(num_replicates_dummy):
            replicate_name_dummy = f"Rep {replicate_idx + 1}"  # Dummy replicate names
            current_group_replicates_dummy.append(replicate_name_dummy)
            for temp_val in np.linspace(20, 80, 61):
                raw_data_list_of_dicts_dummy.append(
                    {
                        "concentration": conc,
                        "ligand": ligand,
                        "protein": protein,
                        "buffer": buffer,
                        "replicate_id": replicate_name_dummy,
                        "Temperature": temp_val,
                        "value": 1
                        / (
                            1
                            + np.exp((temp_val - (50 + i * 2 - replicate_idx * 1)) / 5)
                        )
                        + (conc * 0.001)
                        + (np.random.rand() * 0.05)
                        + (0.05 if protein == "NPC" else 0.5),
                    }
                )
        group_replicates_map[group_key_str] = current_group_replicates_dummy
    raw_data_initial = pd.DataFrame(raw_data_list_of_dicts_dummy)
    unique_group_keys_str = sorted(list(group_titles_map.keys()))
    print(f"Dummy data generated with {len(unique_group_keys_str)} conditions.")


# raw_data = pd.read_csv('raw_data_real2.csv')
# experiment_info = get_unique_conditions(layout_data="layout_real.csv")
# raw_data_initial = initial_raw_data_organize(initial_raw_data=raw_data, experiment_info=experiment_info)

# 2. --- Dash App Initialization ---
app = dash.Dash(__name__, suppress_callback_exceptions=True)

# 3. --- App Layout (MODIFIED for Derivative Toggle) ---
app.layout = html.Div(
    [
        html.H1(
            "Interactive Multi-Plot Viewer: Averaging, BG Subtraction, Normalization & Derivative"
        ),
        html.Div(
            [  # Main content flex container
                html.Div(
                    [  # Left panel
                        html.H3("Select Main Plots:"),
                        dcc.Checklist(
                            id="plot-selector-checklist",
                            options=[
                                {"label": group_titles_map[key_str], "value": key_str}
                                for key_str in unique_group_keys_str
                            ],
                            value=(
                                [unique_group_keys_str[0]]
                                if unique_group_keys_str
                                else []
                            ),
                            style={"marginBottom": "20px"},
                        ),
                        html.H4("Replicate Selection for Averaging:"),
                        html.Div(
                            id="replicate-selection-area",
                            style={
                                "overflowY": "auto",
                                "maxHeight": "20vh",
                                "marginBottom": "20px",
                            },
                        ),
                        html.H4("Processing Options:"),
                        dcc.Checklist(
                            id="bg-subtract-toggle",
                            options=[
                                {
                                    "label": "Enable Background Subtraction",
                                    "value": "ENABLE_BG_SUBTRACTION",
                                }
                            ],
                            value=[],
                            style={"marginBottom": "5px"},
                        ),
                        dcc.Checklist(
                            id="normalize-toggle",
                            options=[
                                {
                                    "label": "Normalize Avg Data (0-1 Scale)",
                                    "value": "ENABLE_NORM",
                                }
                            ],
                            value=[],
                            style={"marginBottom": "5px"},
                        ),
                        # --- Derivative Toggle ---
                        dcc.Checklist(
                            id="derivative-toggle",
                            options=[
                                {
                                    "label": "Plot Derivative (-dY/dT)",
                                    "value": "ENABLE_DERIV",
                                }
                            ],
                            value=[],
                            style={"marginBottom": "20px"},
                        ),
                        html.H4("Download Options:"),
                        html.Button(
                            "Download Processed Figure (HTML)",
                            id="btn-download-avg-fig",
                            style={"marginBottom": "5px", "display": "block"},
                        ),
                        html.Button(
                            "Download Processed Data (CSV)",
                            id="btn-download-avg-csv",
                            style={"marginBottom": "5px", "display": "block"},
                        ),
                        html.Button(
                            "Download Metadata (CSV)",
                            id="btn-download-metadata-csv",
                            style={"display": "block"},
                        ),
                        dcc.Download(id="download-avg-fig-html"),
                        dcc.Download(id="download-avg-data-csv"),
                        dcc.Download(id="download-metadata-csv"),
                    ],
                    style={
                        "width": "30%",
                        "float": "left",
                        "padding": "10px",
                        "boxSizing": "border-box",
                    },
                ),
                html.Div(
                    [  # Right panel
                        dcc.Graph(id="dynamic-subplot-graph", style={"height": "85vh"})
                    ],
                    style={
                        "width": "70%",
                        "float": "right",
                        "padding": "10px",
                        "boxSizing": "border-box",
                    },
                ),
            ],
            style={"display": "flex", "flexDirection": "row"},
        ),
    ]
)


# --- (generate_replicate_selectors callback: UNCHANGED) ---
@app.callback(
    Output("replicate-selection-area", "children"),
    [Input("plot-selector-checklist", "value")],
)
def generate_replicate_selectors(selected_main_plot_keys):
    if not selected_main_plot_keys:
        return html.P("Select a main plot to see replicate options.")
    replicate_dash_components = []
    for group_key_str in selected_main_plot_keys:
        group_title = group_titles_map.get(group_key_str, "Unknown Group")
        replicates_for_group = group_replicates_map.get(group_key_str, [])
        if not replicates_for_group:
            continue
        checklist_id = {"type": "replicate-filter", "group_key": group_key_str}
        component_for_group = html.Div(
            [
                html.Strong(f"Replicates for: {group_title}"),
                dcc.Checklist(
                    id=checklist_id,
                    options=[
                        {"label": rep_name, "value": rep_name}
                        for rep_name in replicates_for_group
                    ],
                    value=replicates_for_group,
                    inline=True,
                    style={"marginLeft": "10px", "marginBottom": "10px"},
                ),
            ],
            style={"border": "1px solid #eee", "padding": "5px", "marginBottom": "5px"},
        )
        replicate_dash_components.append(component_for_group)
    return replicate_dash_components


# --- (Helper get_selected_replicates_by_group: UNCHANGED) ---
def get_selected_replicates_by_group(
    selected_main_plot_keys, rep_values, rep_ids_with_dicts
):
    replicates_map = {}
    if selected_main_plot_keys and rep_ids_with_dicts:
        for i, rep_id_dict in enumerate(rep_ids_with_dicts):
            if rep_id_dict and isinstance(rep_id_dict, dict):
                group_key = rep_id_dict.get("group_key")
                if group_key in selected_main_plot_keys:
                    replicates_map[group_key] = (
                        rep_values[i] if rep_values and i < len(rep_values) else []
                    )
    for main_key in selected_main_plot_keys:
        if main_key not in replicates_map:
            replicates_map[main_key] = group_replicates_map.get(main_key, [])
    return replicates_map


# --- Main Graph Update Callback (MODIFIED for Derivative) ---
# --- Main Graph Update Callback (MODIFIED for new Y-axis logic) ---
@app.callback(
    Output("dynamic-subplot-graph", "figure"),
    [
        Input("plot-selector-checklist", "value"),
        Input({"type": "replicate-filter", "group_key": ALL}, "value"),
        Input("bg-subtract-toggle", "value"),
        Input(
            "normalize-toggle", "value"
        ),  # This toggle now means "normalize avg and put on secondary Y"
        Input("derivative-toggle", "value"),
    ],  # This toggle means "normalize deriv and put on secondary Y"
    [State({"type": "replicate-filter", "group_key": ALL}, "id")],
)
def update_graph(
    selected_main_plot_keys,
    selected_replicates_values,
    bg_subtract_status,
    normalize_status,
    derivative_status,
    selected_replicates_ids,
):
    fig_empty = go.Figure()
    fig_empty.update_layout(
        xaxis={"visible": False},
        yaxis={"visible": False},
        annotations=[
            {
                "text": "Processing...",
                "xref": "paper",
                "yref": "paper",
                "showarrow": False,
                "font": {"size": 20},
            }
        ],
    )
    if not selected_main_plot_keys or raw_data_initial.empty:
        # ... (empty/error message logic as before) ...
        return fig_empty

    bg_subtract_enabled = "ENABLE_BG_SUBTRACTION" in bg_subtract_status
    normalize_avg_enabled = (
        "ENABLE_NORM" in normalize_status
    )  # For the main average curve
    derivative_enabled = "ENABLE_DERIV" in derivative_status  # For the derivative curve

    replicates_for_main_plots = get_selected_replicates_by_group(
        selected_main_plot_keys, selected_replicates_values, selected_replicates_ids
    )
    num_selected_main_plots = len(selected_main_plot_keys)
    # ... (subplot layout calc: rows, cols - same) ...
    if num_selected_main_plots == 1:
        cols, rows = 1, 1
    elif num_selected_main_plots == 2:
        cols, rows = 2, 1
    elif num_selected_main_plots <= 4:
        cols, rows = 2, math.ceil(num_selected_main_plots / 2)
    else:
        cols, rows = 3, math.ceil(num_selected_main_plots / 3)

    subplot_titles = [
        group_titles_map.get(key_str, "Unknown") for key_str in selected_main_plot_keys
    ]
    specs_for_subplots = [[{"secondary_y": True}] * cols for _ in range(rows)]
    fig = make_subplots(
        rows=rows, cols=cols, subplot_titles=subplot_titles, specs=specs_for_subplots
    )

    current_row, current_col = 1, 1
    for main_plot_key_str in selected_main_plot_keys:
        conc_numeric, ligand, protein, buffer = json.loads(main_plot_key_str)
        subplot_main_title = group_titles_map.get(main_plot_key_str, "Plot")

        main_group_df_all_reps = raw_data_initial[
            (raw_data_initial["concentration"] == conc_numeric)
            & (raw_data_initial["ligand"] == ligand)
            & (raw_data_initial["protein"] == protein)
            & (raw_data_initial["buffer"] == buffer)
        ]
        selected_reps = replicates_for_main_plots.get(main_plot_key_str, [])
        df_indiv_reps = main_group_df_all_reps[
            main_group_df_all_reps["replicate_id"].isin([str(r) for r in selected_reps])
        ]

        # Plot individual selected replicates (always on primary Y-axis)
        if not df_indiv_reps.empty:
            temp_fig_reps = px.line(
                df_indiv_reps, x="Temperature", y="value", color="replicate_id"
            )
            for trace in temp_fig_reps.data:
                trace.name = f"{subplot_main_title} - {trace.name}"
                trace.legendgroup = subplot_main_title
                trace.showlegend = True
                fig.add_trace(
                    trace, row=current_row, col=current_col, secondary_y=False
                )

        primary_y_title = "Value"
        secondary_y_title = (
            "Normalized (0-1)"  # Default title if secondary axis is used
        )
        show_secondary_y_elements = False

        if not df_indiv_reps.empty:
            main_avg_df = (
                df_indiv_reps.groupby("Temperature")["value"].mean().reset_index()
            )
            avg_x_values = main_avg_df["Temperature"]
            avg_y_values_post_bg_sub = main_avg_df["value"].copy()  # Start with this

            avg_trace_name = f"{subplot_main_title} - Average"

            if bg_subtract_enabled and protein != "NPC":
                # ... (NPC subtraction logic, updates avg_y_values_post_bg_sub) ...
                npc_key_tuple = (conc_numeric, ligand, "NPC", buffer)
                npc_key_str = json.dumps(npc_key_tuple)
                npc_group_df_all_reps = raw_data_initial[
                    (raw_data_initial["concentration"] == conc_numeric)
                    & (raw_data_initial["ligand"] == ligand)
                    & (raw_data_initial["protein"] == "NPC")
                    & (raw_data_initial["buffer"] == buffer)
                ]
                if not npc_group_df_all_reps.empty:
                    selected_reps_for_npc = replicates_for_main_plots.get(
                        npc_key_str, group_replicates_map.get(npc_key_str, [])
                    )
                    df_for_npc_avg = npc_group_df_all_reps[
                        npc_group_df_all_reps["replicate_id"].isin(
                            [str(r) for r in selected_reps_for_npc]
                        )
                    ]
                    if not df_for_npc_avg.empty:
                        npc_avg_series = df_for_npc_avg.groupby("Temperature")[
                            "value"
                        ].mean()
                        avg_y_values_post_bg_sub = (
                            avg_y_values_post_bg_sub
                            - avg_x_values.map(npc_avg_series).fillna(0)
                        )
                        avg_trace_name += " (BG Sub)"

            # --- Averaged Data Plotting (Primary or Secondary Y) ---
            if normalize_avg_enabled and not avg_y_values_post_bg_sub.empty:
                min_val, max_val = (
                    avg_y_values_post_bg_sub.min(),
                    avg_y_values_post_bg_sub.max(),
                )
                norm_avg_y = avg_y_values_post_bg_sub.copy()
                if max_val > min_val:
                    norm_avg_y = (avg_y_values_post_bg_sub - min_val) / (
                        max_val - min_val
                    )
                elif not avg_y_values_post_bg_sub.empty:  # Flat line
                    norm_avg_y = pd.Series(
                        [0.5] * len(avg_y_values_post_bg_sub),
                        index=avg_y_values_post_bg_sub.index,
                    )

                fig.add_trace(
                    go.Scatter(
                        x=avg_x_values,
                        y=norm_avg_y,
                        mode="lines",
                        name=f"{avg_trace_name} (Norm 0-1)",
                        legendgroup=subplot_main_title,
                        line=dict(color="black", width=3, dash="dash"),
                        showlegend=True,
                    ),
                    row=current_row,
                    col=current_col,
                    secondary_y=True,
                )  # Plot on Secondary Y
                show_secondary_y_elements = True
            elif (
                not avg_y_values_post_bg_sub.empty
            ):  # Plot non-normalized average on primary
                fig.add_trace(
                    go.Scatter(
                        x=avg_x_values,
                        y=avg_y_values_post_bg_sub,
                        mode="lines",
                        name=avg_trace_name,
                        legendgroup=subplot_main_title,
                        line=dict(color="grey", width=3, dash="solid"),
                        showlegend=True,  # Different style
                    ),
                    row=current_row,
                    col=current_col,
                    secondary_y=False,
                )  # Plot on Primary Y

            # --- Derivative Plotting (Always Normalized, Always on Secondary Y if enabled) ---
            if (
                derivative_enabled
                and not avg_y_values_post_bg_sub.empty
                and len(avg_y_values_post_bg_sub) > 1
            ):
                temps_np = avg_x_values.to_numpy()
                vals_np = (
                    avg_y_values_post_bg_sub.to_numpy()
                )  # Use data after BG sub, before main avg normalization

                sort_indices = np.argsort(temps_np)
                temps_sorted, vals_sorted = (
                    temps_np[sort_indices],
                    vals_np[sort_indices],
                )

                if len(np.unique(temps_sorted)) > 1:
                    derivative = np.gradient(vals_sorted, temps_sorted)
                    neg_derivative = -1 * derivative

                    # Min-Max normalize the negative derivative
                    min_deriv, max_deriv = neg_derivative.min(), neg_derivative.max()
                    norm_neg_derivative = (
                        neg_derivative.copy()
                    )  # Make a copy before modifying
                    if max_deriv > min_deriv:
                        norm_neg_derivative = (neg_derivative - min_deriv) / (
                            max_deriv - min_deriv
                        )
                    elif len(neg_derivative) > 0:  # Flat derivative
                        norm_neg_derivative = np.full_like(neg_derivative, 0.5)

                    fig.add_trace(
                        go.Scatter(
                            x=temps_sorted,
                            y=norm_neg_derivative,
                            mode="lines",
                            name=f"{subplot_main_title} - Norm (-Derivative)",
                            legendgroup=subplot_main_title,  # Keep in same group for toggling all for this plot
                            line=dict(color="red", width=2, dash="dot"),
                            showlegend=True,
                        ),
                        row=current_row,
                        col=current_col,
                        secondary_y=True,
                    )  # Plot on Secondary Y
                    show_secondary_y_elements = True

        # Update Y-axis titles for the current subplot
        fig.update_yaxes(
            title_text=primary_y_title,
            secondary_y=False,
            row=current_row,
            col=current_col,
            title_font=dict(size=10),
            tickfont=dict(size=9),
        )
        if show_secondary_y_elements:
            fig.update_yaxes(
                title_text=secondary_y_title,
                secondary_y=True,
                row=current_row,
                col=current_col,
                title_font=dict(size=10),
                tickfont=dict(size=9),
                range=[0, 1],
            )  # Set range for normalized axis
        else:  # Hide secondary y-axis if no traces are plotted on it for this subplot
            fig.update_yaxes(
                visible=False, secondary_y=True, row=current_row, col=current_col
            )

        fig.update_xaxes(
            title_text="Temperature",
            row=current_row,
            col=current_col,
            title_font=dict(size=10),
            tickfont=dict(size=9),
        )
        current_col += 1
        if current_col > cols:
            current_col = 1
            current_row += 1

    fig.update_layout(
        height=max(500, rows * 350),
        showlegend=True,
        legend=dict(
            title_text="Plots & Conditions", groupclick="toggleitem", font=dict(size=9)
        ),
        margin=dict(
            l=70,
            r=50,
            t=max(60, num_selected_main_plots // cols * 30 if cols > 0 else 60),
            b=60,
        ),  # Dynamic top margin
    )
    if num_selected_main_plots == 1 and subplot_titles:
        fig.update_layout(title_text=subplot_titles[0])
        if fig.layout.annotations:
            fig.layout.annotations = [
                ann for ann in fig.layout.annotations if ann.text not in subplot_titles
            ]
    return fig


# --- Download Callbacks ---
# IMPORTANT: The download callbacks will need significant updates to:
# 1. Use the new `convert_concentration_to_float` where appropriate if parsing keys.
# 2. Correctly handle the new Y-axis logic (what data goes where, normalization of derivative for figure).
# 3. Include the normalized derivative in the CSV data.
# 4. Update metadata to reflect derivative normalization.
# For brevity, these are NOT fully updated here but the `update_graph` serves as a template.


@app.callback(
    Output("download-avg-fig-html", "data"),
    Input("btn-download-avg-fig", "n_clicks"),
    [
        State("plot-selector-checklist", "value"),
        State({"type": "replicate-filter", "group_key": ALL}, "value"),
        State("bg-subtract-toggle", "value"),
        State("normalize-toggle", "value"),
        State("derivative-toggle", "value"),
    ],
    [State({"type": "replicate-filter", "group_key": ALL}, "id")],
    prevent_initial_call=True,
)
def download_averaged_figure(
    n_clicks,
    selected_main_plot_keys,
    rep_values,
    bg_subtract_status,
    normalize_status,
    derivative_status,
    rep_ids,
):
    if not n_clicks or not selected_main_plot_keys or raw_data_initial.empty:
        return dash.no_update
    # --- THIS FUNCTION NEEDS TO BE FULLY REWRITTEN TO MIRROR `update_graph` ---
    # -   It should create a figure with primary Y for raw reps (optional for download fig)
    # -   And secondary Y for normalized average (if normalize_status) AND normalized derivative (if derivative_status)
    # -   Ensure all data processing steps (avg, bg_sub, deriv_calc, norm_of_avg, norm_of_deriv) are correct.
    print(
        "Download Averaged Figure - Needs full implementation of new Y-axis and normalization logic."
    )
    # Placeholder for now:
    fig_dl = go.Figure()
    fig_dl.add_annotation(
        "Figure download logic needs full update for new Y-axis and normalization features.",
        showarrow=False,
    )
    return dict(
        content=fig_dl.to_html(full_html=True, include_plotlyjs="cdn"),
        filename="processed_plots_placeholder.html",
    )


@app.callback(
    Output("download-avg-data-csv", "data"),
    Input("btn-download-avg-csv", "n_clicks"),
    [
        State("plot-selector-checklist", "value"),
        State({"type": "replicate-filter", "group_key": ALL}, "value"),
        State("bg-subtract-toggle", "value"),
        State("normalize-toggle", "value"),
        State("derivative-toggle", "value"),
    ],
    [State({"type": "replicate-filter", "group_key": ALL}, "id")],
    prevent_initial_call=True,
)
def download_averaged_data_csv(
    n_clicks,
    selected_main_plot_keys,
    rep_values,
    bg_subtract_status,
    normalize_status,
    derivative_status,
    rep_ids,
):
    if not n_clicks or not selected_main_plot_keys or raw_data_initial.empty:
        return dash.no_update
    # --- THIS FUNCTION NEEDS TO BE FULLY REWRITTEN ---
    # -   Add column for normalized negative derivative.
    # -   Ensure existing columns correctly reflect what was used for plotting (e.g., `value_normalized_0_1` for the average if it was normalized).
    print(
        "Download Averaged Data CSV - Needs full implementation for derivative normalization."
    )
    # Placeholder for now:
    temp_df = pd.DataFrame({"message": ["CSV download logic needs full update."]})
    return dcc.send_data_frame(
        temp_df.to_csv, "processed_data_placeholder.csv", index=False
    )


@app.callback(
    Output("download-metadata-csv", "data"),
    Input("btn-download-metadata-csv", "n_clicks"),
    [
        State("plot-selector-checklist", "value"),
        State({"type": "replicate-filter", "group_key": ALL}, "value"),
        State("bg-subtract-toggle", "value"),
        State("normalize-toggle", "value"),
        State("derivative-toggle", "value"),
    ],
    [State({"type": "replicate-filter", "group_key": ALL}, "id")],
    prevent_initial_call=True,
)
def download_metadata_csv(
    n_clicks,
    selected_main_plot_keys,
    rep_values,
    bg_subtract_status,
    normalize_status,
    derivative_status,
    rep_ids,
):
    if not n_clicks or not selected_main_plot_keys or raw_data_initial.empty:
        return dash.no_update
    # --- THIS FUNCTION NEEDS TO BE UPDATED ---
    # -   Add info about derivative normalization status.
    print("Download Metadata CSV - Needs update for derivative normalization status.")
    # Placeholder for now:
    temp_df = pd.DataFrame({"message": ["Metadata download logic needs update."]})
    return dcc.send_data_frame(temp_df.to_csv, "metadata_placeholder.csv", index=False)


# --- Run the App ---
if __name__ == "__main__":
    # if not LAYOUT_CSV_PATH.exists() or not RAW_READINGS_CSV_PATH.exists():
    #     print("---" * 20 + "\nWARNING: One or both CSV file paths are invalid.\n" +
    #           f"Layout Path: {LAYOUT_CSV_PATH.resolve()} (Exists: {LAYOUT_CSV_PATH.exists()})\n" +
    #           f"Raw Data Path: {RAW_READINGS_CSV_PATH.resolve()} (Exists: {RAW_READINGS_CSV_PATH.exists()})\n" +
    #           "The app may use DUMMY DATA or fail to load options if real data processing fails. Update paths in the script.\n" + "---" * 20)
    app.run(debug=True, port=8056)  # Changed port again
