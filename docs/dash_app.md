# Dash App

![InstaWell icon](assets/instawell-icon-256.png){: style="width:90px"}

The Dash interface exposes the entire InstaWell pipeline plus a layout designer, CSV upload, validation, and figure browser. This page walks through each card on the page and the architecture behind it.

## Launching

```bash
pip install 'instawell[dash]'
instawell-dash --host 0.0.0.0 --port 8060 --experiments-root experiments
# or python -m instawell.dash_app.app --port 9000
```

`--host`, `--port`, `--experiments-root`, and `--debug` flags are optional; defaults remain `127.0.0.1`, `8050`, `./experiments`, and disabled debug mode.

## Experiment Browser

- Lists every experiment folder inside `experiments_root` (defaults to `./experiments`).
- The **Refresh** button re-scans the directory after you run a pipeline.
- Selecting an experiment locks the "New Experiment" and "Designer" cards to avoid mixing states; click **Clear** to re-enable them.
- After a pipeline run completes, the new experiment is auto-selected via a dedicated `last-pipeline-experiment` store (no fragile HTML parsing).

## Layout Designer

Use the designer to create a layout from scratch or highlight wells present in a raw CSV.

- Supports 96/384-well plates.
- Hold **Shift** and click to build a multi-well selection; assign concentration, ligand, protein, buffer, and unit in one shot.
- Use **Copy from Selected Well** (enabled when exactly one filled well is selected) to pull the existing values back into the form -- handy for making slight tweaks.
- New controls let you pick the layout separator (default `|`) and empty placeholder (default `^`). Exported CSVs respect those characters, so they match the pipeline config.
- Empty wells are filled with the placeholder mask (e.g., `^|^|^|^`) to keep parsing consistent.

## New Experiment Card

1. **Upload Raw/Layout CSVs** -- Drag/drop or click; both are required for validation.
2. **Configure Parsing Options**
   - Condition separator (default `|`)
   - Missing-condition placeholder (default `^`)
   - Temperature column name (default `Temperature`)
   - Condition field order (comma-separated)
   - Non-protein control marker (default `NPC`)
3. **Validate Layout** -- Runs the same parser as the pipeline, ensuring separator/placeholder combos work before writing anything to disk. Errors list the offending well + column identifier.
4. **Setup & View Raw Data** -- Calls `setup_experiment` and `ingest_data`, populates the well filtering card, and enables the "Run Full Pipeline" button.
5. **Run Full Pipeline** -- Executes steps 02-08 with the selected well filters. Buttons for figures become available as the corresponding CSVs appear.

Validation and setup messages stay visible under their buttons so it's easy to spot which phase succeeded. Exceptions are logged server-side and the frontend only shows a user-friendly message.

## Well Filtering

After setup completes, a grid of well buttons appears. Click individual wells to toggle them for exclusion, or use the **Select All** / **Deselect All** buttons. The selection is stored in `selected-wells-grid` and passed into `filter_wells` when running the pipeline.

## Figures

Buttons across the top map to data availability:

- **Raw** -- per-well traces (always available after setup).
- **Averaged**, **BG Sub**, **Normalized**, **Derivative**, **Tm** -- enabled only when their respective CSVs exist.

Navigate between figures using the **prev/next** buttons, the **dropdown selector**, or the figure counter. Each figure is rendered inline using the same generator functions documented in [Pipeline](pipeline.md#figure-generators-by-step).

## Architecture

The Dash app source lives in `src/instawell/dash_app/` (~3,100 lines across 15 files).

### Module overview

| Module | Purpose |
|---|---|
| `app.py` | App factory (`create_app`), CLI entry point, cache + experiments root setup |
| `layout.py` | Component tree: navbar, cards, `dcc.Store` definitions |
| `constants.py` | Magic strings extracted into one place: `FIGURE_BUTTON_MAP`, `FIGURE_STEP_FILES`, `STEP_ICONS`, defaults |
| `utils.py` | Pure functions: `normalize_well`, `parse_well_name`, `get_well_grid_dimensions`, `validate_separator_placeholder`, `parse_upload`, `get_experiment_list/status` |
| `designer.py` | Plate layout designer component (96/384-well grid, condition assignment form) |
| `designer_callbacks.py` | Callbacks for the designer (grid rendering, condition CRUD, CSV export) |

### Callbacks package

The callback logic is split into `callbacks/` with eight focused modules, each exporting a `register_*_callbacks(app, cache)` function:

| Module | Callbacks |
|---|---|
| `_session.py` | Session ID assignment |
| `_experiment.py` | Experiment banner, toggle, refresh, info display |
| `_upload.py` | Raw/layout file upload handlers (via shared `_handle_upload` helper) |
| `_well_filter.py` | Well grid population, select/deselect all, toggle individual, filter summary |
| `_validation.py` | Layout validation against parsing settings |
| `_pipeline.py` | `setup_and_ingest`, `run_pipeline` |
| `_figures.py` | Figure loading, display, prev/next/dropdown navigation |
| `_helpers.py` | Shared helpers: `_handle_upload`, `_refresh_keep` |

The coordinator (`__init__.py`) registers all modules in one call, preserving the single import `from .callbacks import register_callbacks` in `app.py`.

### Client-side state (dcc.Store)

| Store ID | Storage | Purpose |
|---|---|---|
| `session-id` | session | UUID for cache key namespacing |
| `raw-data-store` | session | Cache key for uploaded raw DataFrame |
| `layout-data-store` | session | Cache key for uploaded layout DataFrame |
| `current-experiment-store` | memory | Currently active experiment name |
| `figures-store` | memory | Serialised list of Plotly figure dicts |
| `current-figure-index` | memory | Index into figures-store |
| `selected-wells-grid` | memory | List of wells selected for filtering |
| `available-wells-store` | memory | All wells present in the raw data |
| `filtered-wells-store` | memory | Wells passed to `filter_wells` |
| `setup-complete-store` | memory | Boolean gate for pipeline button |
| `last-pipeline-experiment` | memory | Experiment name from last pipeline run |

### Logging

All modules log to `instawell.dash_app.*` namespaces. Uploads, setup, pipeline runs, figure loading, cache misses, and designer exports are traceable in server logs. Exceptions are logged server-side; the frontend only shows user-friendly error messages.

## Testing

The Dash app has 114 tests across two files:

- **`test_dash_app.py`** (75 unit tests) -- pure function tests for `utils`, `constants`, `designer`, and `_helpers`. No Dash server required.
- **`test_dash_integration.py`** (39 integration tests) -- creates a real Dash app with a filesystem cache, then:
    - **Bootstrap smoke tests**: verifies the app builds, all `dcc.Store` IDs exist in the layout, and all callback outputs are registered.
    - **Direct callback invocation**: extracts registered callback functions via `__wrapped__` (bypassing Dash 3's context wrapper) and calls them with controlled inputs. Covers session assignment, button enable/disable logic, well filter summary, figure display + navigation, layout validation with cached data, and a full **upload -> setup -> pipeline -> verify output files** end-to-end flow.

Run them with:

```bash
uv run pytest tests/test_dash_app.py tests/test_dash_integration.py -v
```

## Tips

- **Re-running** -- If you need to tweak separators or the NPC marker, clear the experiment, update the settings, and re-run setup/pipeline. Each step overwrites its outputs deterministically.
- **Exporting Plots** -- Every figure shown in the Dash app can be downloaded via the Plotly mode bar. Use the notebook widget helpers if you prefer to stay in Jupyter.
- **Serving Offline/Remote** -- Override host/port/experiments root using CLI flags (e.g., `instawell-dash --host 0.0.0.0 --port 8080 --experiments-root /data/exp`). In code, call `create_app(experiments_root="path").run(...)`.
- **Curve Fits** -- The 4PL fitting step is still maturing. Treat `log10_fit` plots as exploratory, and double-check the saved diagnostics before using numbers in reports.
