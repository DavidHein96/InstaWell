[![PyPI version](https://badge.fury.io/py/instawell.svg)](https://pypi.org/project/instawell/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL%203.0-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![codecov](https://codecov.io/gh/DavidHein96/InstaWell/graph/badge.svg)](https://codecov.io/gh/DavidHein96/InstaWell)
[![Jupyter-ready](https://img.shields.io/badge/jupyter-ready-orange.svg)](https://jupyter.org/)
[![Use uv](https://img.shields.io/badge/recommended%20installer-uv-4584b6.svg)](https://docs.astral.sh/uv/)

# InstaWell

![instawell — thermal shift tools](https://raw.githubusercontent.com/DavidHein96/InstaWell/dev/docs/assets/instawell-icon-256.png)

Tools for organizing, processing, and visualizing thermal shift assay (TSA) data.

## Why?

"Man I hate copying and pasting stuff in excel... I wish I could very quickly get from raw TSA data + layout to dose-response curves and Tm values without a million clicks."

## Features

* **Flexible layouts** → parse arbitrary condition fields (e.g., `concentration | ligand | protein | buffer`)
* **Long/wide transforms** and **replicate averaging**
* **Background subtraction** using a non-protein control (NPC) marker
* **Min-max scaling** and **derivative-based min-temperature** (Tm-like) extraction
* **Prism-style 4PL fit** (log10 domain with `logEC50`) + diagnostics CSV
* **Plotly figures**: raw per-well, processed averages, and min-temperature scatter
* **Jupyter widgets** to browse generated figures interactively

## Install

```bash
pip install instawell
# Optional: notebook extras (recommended)
pip install 'instawell[notebook]'
```

Python ≥3.10 recommended, as well as the tool [uv](https://docs.astral.sh/uv/getting-started/installation/) for development environments.

Or install from source:

```bash
git clone https://github.com/DavidHein96/InstaWell.git
cd InstaWell
uv sync
```

## Dash App

Prefer a UI? Install the Dash extra and launch the bundled server:

```bash
pip install 'instawell[dash]'
instawell-dash --port 8050 --experiments-root experiments
```

You can tweak `--host`, `--port`, `--experiments-root`, and `--debug`. The app
exposes layout upload/validation, well filtering, and figure browsing directly
in the browser. See [`docs/dash_app.md`](docs/dash_app.md) for architecture details and workflow tips.

## What does this do?

Instawell takes your instrument's **TSA output** (temperatures × wells) and a **layout** that describes each well's condition (e.g., `concentration|ligand|protein|buffer`). It then organizes, QC-plots, and computes dose-response summaries.

### 1) Inputs

**A) TSA output (raw instrument CSV)**
Each column after the temperature is a well (A1, A2, …). Values are the signal (e.g., fluorescence).

```csv
Temperature,A1,A2,A3,B1,B2,B3
25.0,  120,115,118,  130,126,127
26.0,  118,114,117,  128,125,126
...
```

**B) Layout (maps well positions to conditions)**
This ties each well to a condition string your pipeline understands.

```csv
well_row,1,2,3
A, 0|DMSO|NPC|PBS,  1.5|DrugX|ProteinA|PBS,  6|DrugX|ProteinA|PBS
B, 0|DMSO|NPC|PBS,  1.5|DrugX|ProteinA|PBS,  6|DrugX|ProteinA|PBS
```

* `well_row` + column number → **well name** (e.g., `A1`, `A2`, …).
* Condition fields (order matters): `concentration | ligand | protein | buffer`
* `NPC` in **protein** = non-protein control for background.

---

### 2) What the pipeline does (high level)

1. **Ingest & organize**

   * Melts the wide TSA matrix into long format (one measurement per row).
   * Expands condition fields into columns and builds:

     * `unqcond` = `concentration|ligand|protein|buffer`
     * `well_unqcond` = `well|concentration|ligand|protein|buffer`
   * 📄 `01_raw_organized_data.csv`

   Example (long rows):

   ```csv
   Temperature,well,value,concentration,ligand,protein,buffer,unqcond,well_unqcond
   25.0,A2,115,1.5,DrugX,ProteinA,PBS,1.5|DrugX|ProteinA|PBS,A2|1.5|DrugX|ProteinA|PBS
   26.0,A2,114,1.5,DrugX,ProteinA,PBS,1.5|DrugX|ProteinA|PBS,A2|1.5|DrugX|ProteinA|PBS
   ...
   ```

2. **(Optional) Filter bad wells**

   * You inspect **raw per-well plots** to flag odd traces (bubbles, spikes, drifts).
   * 📊 `raw_figures_widget(...)` helps you browse quickly.
   * 📄 `02_filtered_organized_data.csv` (even if nothing removed, for traceability)

3. **Average replicates**

   * Averages `value` over wells sharing the same `unqcond` at each temperature.
   * Produces long + pivoted wide tables keyed by `Temperature`.
   * 📄 `03_averaged_data.csv`, `03_averaged_data_long.csv`

4. **Background subtraction (NPC)**

   * For each `(ligand, buffer, concentration)` with **protein ≠ NPC**, subtracts the matching **NPC** column.
   * Leaves NPC columns out of the final set (less heavy-handed removal).
   * 📄 `04_bg_subtracted_data.csv`, `04_bg_subtracted_data_long.csv`

5. **Min–max scaling (QC convenience)**

   * Scales each `unqcond` trace to [0, 1] to make shapes comparable.
   * 📄 `05_min_max_scaled_data.csv`, `05_min_max_scaled_data_long.csv`

6. **Derivative & min temperature (“Tm-like”)**

   * Computes derivative curves and finds the temperature at the **minimum derivative** per `unqcond`.
   * 📄 `06_derivative_data(_long).csv`
   * 📄 `07_min_temperatures.csv` (has `concentration, ligand, protein, buffer, min_temperature`)

7. **Dose–response (Prism-style 4PL) EXPERIMENTAL**

   * Fits a **4-parameter logistic** in log10 dose space using `logEC50` (zeros are excluded there).
   * This is currently not well tested and is experimental—use with caution!
   * Outputs parameter table (Bottom, Top, **logEC50**, EC50, Hill, SEs, 95% CIs, RSS/RMSE, AIC/BIC) and point-wise diagnostics.
   * 📄 `08_curve_params.csv`, `08_curve_diagnostics.csv`

## Documentation

The full documentation now lives in the MkDocs site under `docs/`. To browse locally:

```bash
pip install 'instawell[docs]'
mkdocs serve
```

Key pages:

- `docs/index.md` – overview & quick start
- `docs/pipeline.md` – numbered CSV pipeline guide
- `docs/dash_app.md` – Dash workflow, layout designer, and validation tips

## Quick start

Also see the [example notebook](examples/toy_example_notebook.ipynb)

```python
from instawell import (
    setup_experiment,          # Step 00 - creates a folder structure and saves metadata
    ingest_data,               # Step 01 - organizes raw data and extracts conditions from the layout
    filter_wells,              # Step 02 - filtering of wells (required to be run)
    average_across_replicates, # Step 03 - groups replicate wells
    subtract_background,       # Step 04 - NPC background subtraction
    min_max_scale,             # Step 05 - min-max scaling
    calculate_derivative,      # Step 06 - derivative computation 
    find_min_temperature,      # Step 07 - min-temperature extraction
    calculate_curve_params,    # Step 08 - 4PL curve fitting
    load_experiment_context,   # load existing experiment context from disk
)

exp = setup_experiment(
    experiment_name="demo1",
    experiments_root="experiments/demo1",
    raw_data_path="data/demo1/raw.csv",
    layout_data_path="data/demo1/layout.csv",
    condition_fields=("concentration","ligand","protein","buffer"),
    condition_separator="|",
    empty_condition_placeholder="0",
    non_protein_control_marker="NPC",
)

# --- Pipeline (pass along the exp) ---
ingest_data(exp)                  # -> 01_raw_organized_data.csv
filter_wells(exp)                 # -> 02_filtered_organized_data.csv
average_across_replicates(exp)   # -> 03_averaged_data.csv (+ long for easier formatting)
subtract_background(exp)          # -> 04_bg_subtracted_data.csv (+ long)
min_max_scale(exp)                # -> 05_min_max_scaled_data.csv (+ long)
calculate_derivative(exp)         # -> 06_derivative_data.csv (+ long)
find_min_temperature(exp)         # -> 07_min_temperatures.csv
calculate_curve_params(exp)       # -> 08 curves: params/diagnostics CSVs (experimental)
```

## Jupyter widgets (requires jupyter notebook)

```python
from instawell import raw_figures_widget, processed_figures_widget, min_temp_figures_widget

# Raw per-well plots (discrete colors per well, only for raw and filtered data)
raw_figures_widget(exp)

# Processed/averaged plots (everything after averaging step)
processed_figures_widget(exp, data_source="bg_subtracted", color_scale="Thermal")

# Min-temperature scatter (with selectable modes in generator args experimental)
min_temp_figures_widget(exp, mode="log10_fit", color_scale="Viridis")
```

> The widget wrappers preserve the docstrings & signatures of the underlying generators. Use `show_help=True` to display the docstring in a collapsible panel.
> You can also save individual figures from the generators by passing `save_figs=True` to the widget, since they are in plotly they are saved as HTML files by default, which you can open in a browser or convert to PNG using kaleido.

## Typical files (by step)

`experiments/<name>/`

```plaintext
01_raw_organized_data.csv
02_filtered_organized_data.csv
03_averaged_data.csv
03_averaged_data_long.csv
04_bg_subtracted_data.csv
04_bg_subtracted_data_long.csv
05_min_max_scaled_data.csv
05_min_max_scaled_data_long.csv
06_derivative_data.csv
06_derivative_data_long.csv
07_min_temperatures.csv
08_curve_params.csv
08_curve_diagnostics.csv
experiment.log                  # A log file of pipeline steps
01_raw_plots/...                # saved HTML
03_averaged_plots/...
experiment_info.json            # Parsed layout and wells metadata
experiment.json                 # ExperimentContext configuration
filtered_wells.txt              # List of excluded wells for extra reference
original_raw_data.csv           # Copy of the original raw data
original_layout_data.csv        # Copy of the original layout data
```

## Key concepts

* **Condition fields** - configured via `ExperimentContext.condition_fields` and joined with `condition_separator` to derive:

  * `unqcond` (unique condition string)
  * `well_unqcond` (unique well + condition)
* **NPC background subtraction** - subtracts a matching **non-protein control** column per panel; leaves NPC traces out of the final set.

## Configuration (ExperimentContext)

Common fields:

* `experiment_dir`: output directory (CSV, plots, logs)
* `raw_data_path`, `layout_data_path`, `temperature_column`
* `condition_fields`: tuple of fields (order matters)
* `condition_separator`: string used to join/split fields (e.g., `"|"`)
* `empty_condition_placeholder`: placeholder for 'blank' conditions. A fully blank well would be e.g., `"0|0|0|0"`
* `non_protein_control_marker`: e.g., `"NPC"`
* `log_to_file`, `log_level`: pipeline logging

## Testing

```bash
# Run the full suite (unit, fuzz, Dash app, synthetic integration)
uv run pytest

# Run only Dash app tests
uv run pytest tests/test_dash_app.py tests/test_dash_integration.py
```

CI runs `pytest --ignore=tests/test_integration_pipeline.py --ignore=tests/test_integration_tsa067.py` because those two files depend on private TSA datasets (golden-file comparisons against real instrument data) that are not committed to the repository. All other tests run in CI on Python 3.10 and 3.12.

## Development Notes

**TODOs**

- Expand the Dash app to cover more of the pipeline steps and improve the layout designer UX.
- Improve documentation coverage, especially around advanced usage and configuration options.
- Setup github pages for hosting the MkDocs documentation site.
- Add more examples and tutorials in the docs.
- Optimize performance for larger datasets, especially in the data processing functions.

## License

This project is licensed under the GNU AFFERO GENERAL PUBLIC LICENSE Version 3 (AGPL-3.0)
