# Dash App

![InstaWell icon](assets/instawell-icon-256.png){: style="width:90px"}

The Dash interface exposes the entire InstaWell pipeline plus a layout designer, CSV upload, validation, and figure browser. This page walks through each card on the page and the new validation options introduced in this update.

!!! warning "Preview quality"
    The Dash UI is still considered experimental. It’s great for rapid QC, but
    it hasn’t been battle-tested the way the CLI/pipeline has. Keep backups of
    your inputs and rerun pipeline steps from Python if anything looks off.

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
- Selecting an experiment locks the “New Experiment” and “Designer” cards to avoid mixing states; click **Clear** to re-enable them.

## Layout Designer

Use the designer to create a layout from scratch or highlight wells present in a raw CSV.

- Supports 96/384-well plates.
- Hold **Shift** and click to build a multi-well selection; assign concentration, ligand, protein, buffer, and unit in one shot.
- Use **Copy from Selected Well** (enabled when exactly one filled well is selected) to pull the existing values back into the form—handy for making slight tweaks.
- New controls let you pick the layout separator (default `|`) and empty placeholder (default `^`). Exported CSVs respect those characters, so they match the pipeline config.
- Empty wells are filled with the placeholder mask (e.g., `^|^|^|^`) to keep parsing consistent.

## New Experiment Card

1. **Upload Raw/Layout CSVs** – Drag/drop or click; both are required for validation.
2. **Configure Parsing Options**
   - Condition separator (default `|`)
   - Missing-condition placeholder (default `^`)
   - Temperature column name (default `Temperature`)
   - Condition field order (comma-separated)
   - Non-protein control marker (default `NPC`)
3. **Validate Layout** – Runs the same parser as the pipeline, ensuring separator/placeholder combos work before writing anything to disk. Errors list the offending well + column identifier.
4. **Setup & View Raw Data** – Calls `setup_experiment` and `ingest_data`, populates the well filtering card, and enables the “Run Full Pipeline” button.
5. **Run Full Pipeline** – Executes steps 02–08 with the selected well filters. Buttons for figures become available as the corresponding CSVs appear.

Validation and setup messages stay visible under their buttons so it’s easy to spot which phase succeeded.

## Well Filtering

After setup completes, a checklist lists every well present in the uploaded raw CSV. Select wells to exclude or use the Select/Deselect buttons to toggle all wells. The selection is passed into `filter_wells` when running the pipeline.

## Figures

Buttons across the top map to data availability:

- **Raw** – per-well traces (always available after setup).
- **Averaged**, **BG Sub**, **Normalized**, **Derivative**, **Tm** – enabled only when their respective CSVs exist.

Each button renders all figures inline using the same generator functions documented in [Pipeline](pipeline.md#figure-generators-by-step). Large experiments can produce many subplots; use the browser’s find shortcut to jump to specific ligands/proteins.

## Tips

- **Re-running** – If you need to tweak separators or the NPC marker, clear the experiment, update the settings, and re-run setup/pipeline. Each step overwrites its outputs deterministically.
- **Exporting Plots** – Every figure shown in the Dash app can be downloaded via the Plotly mode bar. Use the notebook widget helpers if you prefer to stay in Jupyter.
- **Serving Offline/Remote** – Override host/port/experiments root using CLI flags (e.g., `instawell-dash --host 0.0.0.0 --port 8080 --experiments-root /data/exp`). In code, call `create_app(experiments_root="path").run(...)`.
- **Curve Fits** – The 4PL fitting step is still maturing. Treat ``log10_fit`` plots as exploratory, and double-check the saved diagnostics before using numbers in reports.
