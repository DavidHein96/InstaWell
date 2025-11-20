# Pipeline

![InstaWell icon](assets/instawell-icon-256.png){: style="width:90px"}

The InstaWell pipeline is intentionally deterministic: every step reads numbered CSV files, writes its own numbered outputs, and logs to `experiment.log`. This page captures what each stage expects, produces, and how to rerun it safely.

## Directory Layout

Running `setup_experiment` creates `experiments/<name>/`:

```
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
experiment.json
experiment.log
experiment_info.json
plots/
```

Numbers correspond to the functions documented below.

## Step-by-Step

| # | Function | Description | Key Output |
|---|----------|-------------|------------|
| 00 | `setup_experiment` | Copies raw/layout CSVs into the experiment folder, stores parsing metadata (`experiment.json`), and configures logging. Custom separator, placeholder (`^`), condition order, and NPC marker all live here. | `experiment.json` |
| 01 | `ingest_data` | Melts the raw matrix into long form, expands condition strings via the configured separator, and records replicate metadata (`experiment_info.json`). | `01_raw_organized_data.csv` |
| 02 | `filter_wells` | Records wells to exclude. Must run even when the list is empty so downstream steps see `02_filtered_organized_data.csv`. | `02_filtered_organized_data.csv`, `filtered_wells.txt` |
| 03 | `average_across_replicates` | Groups measurements by `Temperature` + `unqcond`, outputs both wide and long tables. Maintains column order based on condition fields. | `03_averaged_data.csv`, `_long.csv` |
| 04 | `subtract_background` | Finds NPC traces per (ligand, buffer, concentration) key, subtracts from protein traces, drops NPC rows, and realigns the wide table. | `04_bg_subtracted_data.csv`, `_long.csv` |
| 05 | `min_max_scale` | Scales each `unqcond` trace to [0, 1] to make shape comparisons easier. Logs warnings for zero-variance traces. | `05_min_max_scaled_data.csv`, `_long.csv` |
| 06 | `calculate_derivative` | Computes `-d(value)/d(Temperature)` for each condition, rescales derivatives, and merges back condition metadata for long-form outputs. | `06_derivative_data.csv`, `_long.csv` |
| 07 | `find_min_temperature` | Picks the temperature at the minimum derivative for each `unqcond` (Tm-like point) and splits `unqcond` back into tidy columns. | `07_min_temperatures.csv` |
| 08 | `calculate_curve_params` | Fits Prism-style 4PLs (log10 domain) to Tm vs concentration per panel (ligand/buffer/protein), computes diagnostics, and stores CI metrics when covariance is available. | `08_curve_params.csv`, `08_curve_diagnostics.csv` |

!!! warning "Curve fitting still stabilizing"
    Step 08 and any downstream visuals that rely on its outputs (e.g.,
    ``min_temp_figure_generator(..., mode=\"log10_fit\")``) are still under
    active development. Inspect residuals and CSV diagnostics before trusting
    the fit parameters.

!!! tip "Rerunning"
    Steps are idempotent: rerunning a function overwrites its outputs but does not modify earlier steps. To reprocess a different separator or layout, re-run steps 00–08.

## CSV Schema Highlights

- **`unqcond`** – canonical string assembled from the configured condition fields using the separator (default `|`).
- **`well_unqcond`** – well name + separator + `unqcond`, used for per-well traces.
- **Condition columns** – automatically created from the layout parsing (e.g., `concentration`, `ligand`, `protein`, `buffer`). Additional layout fields are supported.
- **`min_temperature`** – output of step 07; downstream 4PL fits use the numeric `conc_num` column (converted via `utils.convert_concentration_to_float`).

## Troubleshooting

### Layout parsing failures

1. Ensure the layout CSV uses the same separator and placeholder provided to `setup_experiment`.
2. Every non-empty cell in the layout (outside the `Well` column) must contain exactly as many components as `condition_fields`.
3. Empty wells should be filled with the automatically computed mask (e.g., `^|^|^|^`).

The Dash layout validator reproduces the same parsing logic and surfaces helpful messages before pipeline execution.

### Missing NPC traces

- NPC rows are filtered out after background subtraction. If your downstream CSVs are missing certain conditions, confirm that:
  - `non_protein_control_marker` matches the layout's string (case-sensitive).
  - Each ligand/buffer/concentration combination has an NPC trace; missing NPCs are left unchanged but logged as warnings.

### Column order drift

Column order in the wide tables is reconstructed at each step. Custom condition field orders are supported, but the default ordering logic (sort by ligand → protein → buffer → concentration) only runs when the field tuple equals `("concentration","ligand","protein","buffer")`.

## Figure Generators by Step

| Stage | Figure | Notes |
|-------|--------|-------|
| Raw / Filtered | `raw_figure_generator` | Colors by replicate well, one subplot per condition combo (except `series_by`). |
| Averaged / BG / Min-Max / Derivative | `processed_figure_generator(data_source=...)` | Builds discrete color maps from numeric concentration ordering. |
| Min Temperatures | `min_temp_figure_generator(mode="linear"|"log1p"|"log10_fit")` | `log10_fit` overlays the 4PL curve; weighting and color scales are configurable. |

Use the widget wrappers (`*_figures_widget`) inside notebooks for quick browsing, or the Dash app to interactively explore each stage without writing code.
