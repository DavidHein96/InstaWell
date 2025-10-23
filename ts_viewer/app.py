import dash_bootstrap_components as dbc
import numpy as np
import pandas as pd
from dash import Dash

from .callbacks import register_callbacks
from .config import DATA_DIR, LAYOUT_CSV_PATH, PORT, RAW_READINGS_CSV_PATH, THEME, TITLE
from .designer import designer_card, register_designer_callbacks
from .io import get_unique_conditions, load_dataset_from_disk, to_long_dataframe
from .keys import make_group_key
from .state import AppState, Dataset, state
from .ui import controls, dataset_picker, navbar, plot_card


def build_default_dataset() -> Dataset:
    # Dummy fallback
    np.random.seed(42)
    rows = []
    conditions = [
        (10.0, "LigandA", "ProteinX", "Buffer1"),
        (10.0, "LigandA", "NPC", "Buffer1"),
        (20.0, "LigandA", "ProteinX", "Buffer1"),
        (20.0, "LigandA", "NPC", "Buffer1"),
    ]
    titles, reps = {}, {}
    for i, (conc, lig, pro, buf) in enumerate(conditions):
        key = make_group_key(conc, lig, pro, buf)
        titles[key] = f"C{conc:g} {lig} + {pro} in {buf}"
        rnames = [f"{pro}-R{j + 1}" for j in range(2 if pro == "NPC" else 3)]
        reps[key] = rnames
        for r_idx, name in enumerate(rnames):
            for t in np.linspace(20, 80, 61):
                val = (
                    1 / (1 + np.exp((t - (50 + i * 2 - r_idx)) / 5))
                    + (conc * 0.001)
                    + (np.random.rand() * 0.03)
                    + (0.05 if pro == "NPC" else 0.5)
                )
                rows.append(
                    dict(
                        Temperature=t,
                        replicate_id=name,
                        value=val,
                        concentration=conc,
                        ligand=lig,
                        protein=pro,
                        buffer=buf,
                        group_key=key,
                    )
                )
    data = pd.DataFrame(rows)
    return Dataset(
        name="demo",
        data=data,
        group_titles=titles,
        group_replicates=reps,
        unique_keys=sorted(titles.keys()),
    )


def build_state() -> AppState:
    if LAYOUT_CSV_PATH.exists() and RAW_READINGS_CSV_PATH.exists():
        info = get_unique_conditions(LAYOUT_CSV_PATH)
        data = to_long_dataframe(RAW_READINGS_CSV_PATH, info)
        if not data.empty:
            titles = {}
            reps = {}
            for uc in info.values():
                key = make_group_key(
                    uc.concentration, uc.ligand_name, uc.protein_name, uc.buffer_condition
                )
                titles[key] = (
                    f"C{uc.concentration:g} {uc.ligand_name} + {uc.protein_name} in {uc.buffer_condition}"
                )
                reps[key] = sorted([r.well_name for r in uc.replicates])
            return AppState(
                data=data,
                group_titles=titles,
                group_replicates=reps,
                unique_keys=sorted(titles.keys()),
            )
    # Dummy fallback
    np.random.seed(42)
    rows = []
    conditions = [
        (10.0, "LigandA", "ProteinX", "Buffer1"),
        (10.0, "LigandA", "NPC", "Buffer1"),
        (20.0, "LigandA", "ProteinX", "Buffer1"),
        (20.0, "LigandA", "NPC", "Buffer1"),
    ]
    titles, reps = {}, {}
    for i, (conc, lig, pro, buf) in enumerate(conditions):
        key = make_group_key(conc, lig, pro, buf)
        titles[key] = f"C{conc:g} {lig} + {pro} in {buf}"
        rnames = [f"{pro}-R{j + 1}" for j in range(2 if pro == "NPC" else 3)]
        reps[key] = rnames
        for r_idx, name in enumerate(rnames):
            for t in np.linspace(20, 80, 61):
                val = (
                    1 / (1 + np.exp((t - (50 + i * 2 - r_idx)) / 5))
                    + (conc * 0.001)
                    + (np.random.rand() * 0.03)
                    + (0.05 if pro == "NPC" else 0.5)
                )
                rows.append(
                    dict(
                        Temperature=t,
                        replicate_id=name,
                        value=val,
                        concentration=conc,
                        ligand=lig,
                        protein=pro,
                        buffer=buf,
                        group_key=key,
                    )
                )
    data = pd.DataFrame(rows)
    return AppState(
        data=data, group_titles=titles, group_replicates=reps, unique_keys=sorted(titles.keys())
    )


def create_app() -> Dash:
    app = Dash(
        __name__, external_stylesheets=[THEME], suppress_callback_exceptions=True, title=TITLE
    )

    # Build initial datasets:
    # Priority 1: real CSVs if present → dataset "local"
    datasets = {}
    if LAYOUT_CSV_PATH.exists() and RAW_READINGS_CSV_PATH.exists():
        info = get_unique_conditions(LAYOUT_CSV_PATH)
        tidy = to_long_dataframe(RAW_READINGS_CSV_PATH, info)
        if not tidy.empty:
            titles, reps = {}, {}
            for uc in info.values():
                k = make_group_key(
                    uc.concentration, uc.ligand_name, uc.protein_name, uc.buffer_condition
                )
                titles[k] = (
                    f"C{uc.concentration:g} {uc.ligand_name} + {uc.protein_name} in {uc.buffer_condition}"
                )
                reps[k] = sorted([r.well_name for r in uc.replicates])
            datasets["local"] = Dataset(
                name="local",
                data=tidy,
                group_titles=titles,
                group_replicates=reps,
                unique_keys=sorted(titles.keys()),
            )

    # Priority 2: any persisted uploads under data/<name>/
    for child in DATA_DIR.iterdir():
        if child.is_dir() and (child / "layout.csv").exists() and (child / "raw.csv").exists():
            try:
                tidy, titles, reps = load_dataset_from_disk(child)
                if not tidy.empty:
                    datasets[child.name] = Dataset(
                        name=child.name,
                        data=tidy,
                        group_titles=titles,
                        group_replicates=reps,
                        unique_keys=sorted(titles.keys()),
                    )
            except Exception:
                pass

    # Always include demo fallback
    if "local" not in datasets:
        datasets["demo"] = build_default_dataset()

    state.datasets = datasets
    state.active = sorted(datasets.keys())[0]  # pick first as active

    active_ds = state.datasets[state.active]
    dataset_options = [{"label": name, "value": name} for name in sorted(state.datasets.keys())]
    plot_options = [{"label": active_ds.group_titles[k], "value": k} for k in active_ds.unique_keys]

    app.layout = dbc.Container(
        fluid=True,
        children=[
            navbar(len(active_ds.unique_keys)),
            dataset_picker(dataset_options, state.active),  # NEW row: dataset select & upload
            designer_card(),  # ← NEW: the designer
            dbc.Row(
                [
                    dbc.Col(controls(plot_options), xs=12, md=4, lg=3),
                    dbc.Col(plot_card(), xs=12, md=8, lg=9),
                ],
                className="g-3",
            ),
        ],
    )
    register_callbacks(app)
    register_designer_callbacks(app)
    return app


app = create_app()
server = app.server

if __name__ == "__main__":
    app.run(debug=True, port=PORT)
