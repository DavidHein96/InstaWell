# InstaWell

![InstaWell icon](assets/instawell-icon-256.png){: style="width:120px"}

InstaWell is a set of opinionated tools for turning raw thermal shift assay (TSA/DSF) output into clean, notebook-ready visualizations and CSV summaries. The Python API powers a CLI pipeline, an interactive Dash app, and a suite of Plotly figures for quick QC.

## Why InstaWell?

- **Flexible layouts** – parse any condition schema (`concentration | ligand | protein | buffer | ...`).
- **Deterministic pipeline** – each step writes numbered CSV files for traceability.
- **Background subtraction & Tm extraction** – NPC-aware subtraction, derivative-based minima, and 4PL fits with diagnostics.
- **Plot-ready outputs** – min/max scaling, derivative curves, and interactive Plotly widgets.
- **Dash UI** – upload data, design plate layouts, run the full pipeline, and browse figures without writing code.

## Installation

```bash
pip install instawell
# Optional extras:
pip install 'instawell[notebook]'  # widget support
pip install 'instawell[dash]'      # Dash app
pip install 'instawell[docs]'      # MkDocs authoring
```

Or from source:

```bash
git clone https://github.com/DavidHein96/InstaWell.git
cd InstaWell
uv sync  # or pip install -e .
```

## Quick Start

```python
from instawell import (
    setup_experiment,
    ingest_data,
    filter_wells,
    average_across_replicates,
    subtract_background,
    min_max_scale,
    calculate_derivative,
    find_min_temperature,
    calculate_curve_params,
)

ctx = setup_experiment(
    experiment_name="demo1",
    experiments_root="experiments/demo1",
    raw_data_path="data/demo1/raw.csv",
    layout_data_path="data/demo1/layout.csv",
    condition_fields=("concentration","ligand","protein","buffer"),
    condition_separator="|",
    empty_condition_placeholder="^",
    non_protein_control_marker="NPC",
)

ingest_data(ctx)
filter_wells(ctx, wells_to_filter=[])
average_across_replicates(ctx)
subtract_background(ctx)
min_max_scale(ctx)
calculate_derivative(ctx)
find_min_temperature(ctx)
calculate_curve_params(ctx)
```

Each function writes numbered CSV/LOG files under `experiments/<name>/`. See [Pipeline](pipeline.md) for step-by-step expectations.

## Dash App

Install the Dash extra and launch:

```bash
pip install 'instawell[dash]'
instawell-dash --port 8051
```

The app lets you upload raw/layout CSVs, configure separators, validate layouts, run the pipeline, and browse Plotly figures. The [Dash App](dash_app.md) page walks through the layout designer and validation workflow in detail.

!!! warning "Experimental UI"
    The Dash interface is still under active development and hasn’t received the
    same level of automated testing as the core pipeline. Expect occasional rough
    edges; for production workflows stick to the Python API for now.

## Working With Figures

All figure generators live in `instawell.figures`:

- `raw_figure_generator` / `raw_figures_widget`
- `processed_figure_generator` / `processed_figures_widget`
- `min_temp_figure_generator` / `min_temp_figures_widget`

These yield Plotly `Figure` objects for inline usage or saving via `write_html`. Widgets wrap generators for ergonomic browsing in notebooks.

## Learn More

- [Pipeline](pipeline.md) – detailed explanation of every CSV, column, and validation step.
- [Dash App](dash_app.md) – layout designer, validation flow, and figure browsing.
- [Development](development.md) – contributing, running tests, and serving docs locally.

!!! warning "Curve fits experimental"
    The dose-response fitting stage (``calculate_curve_params`` / step 08) and
    the ``log10_fit`` mode of ``min_temp_figure_generator`` are currently
    lightly tested. Review residuals and diagnostics before drawing conclusions.

Have questions or suggestions? Open an issue on [GitHub](https://github.com/DavidHein96/InstaWell) or reach out to the maintainers.
