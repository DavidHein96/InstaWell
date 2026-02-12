# InstaWell Examples

This directory contains example datasets and notebooks demonstrating InstaWell usage.

## Toy Example

A minimal synthetic dataset perfect for learning the pipeline:

- **`toy_example_raw.csv`** - Raw fluorescence data (11 temperatures × 20 wells)
- **`toy_example_layout.csv`** - Plate layout (10 rows × 2 columns)
- **`toy_example_notebook.ipynb`** - Complete walkthrough notebook

### Dataset Description

**Experimental Setup:**
- **Protein**: ProteinA (thermal stabilization by ATP)
- **Ligand**: ATP (dose-response)
- **Concentrations**: 0, 1, 10, 100, 1000 µM (5 concentrations)
- **Replicates**: 2 technical replicates per condition
- **Controls**: NPC (non-protein control) at each concentration (~10× lower signal)
- **Temperature range**: 25-75°C in 5°C steps
- **Total**: 20 wells (5 protein conditions + 5 NPC controls, each with 2 replicates)

**Expected Results:**
- Dose-dependent thermal stabilization
- Tm increases from ~45°C (apo) to ~63°C (1000 µM ATP)
- Clear 4PL dose-response curve with 4 non-zero concentrations

### Quick Start

```bash
cd examples
jupyter notebook toy_example_notebook.ipynb
```

Or run programmatically:

```python
from instawell import setup_experiment, ingest_data, filter_wells, average_across_replicates, \
                      subtract_background, calculate_derivative, find_min_temperature, calculate_curve_params

ctx = setup_experiment(
    experiment_name="toy_example",
    experiments_root="experiments",
    raw_data_path="toy_example_raw.csv",
    layout_data_path="toy_example_layout.csv",
)

# Run the pipeline
ingest_data(ctx)
filter_wells(ctx, wells_to_filter=[])
average_across_replicates(ctx)
subtract_background(ctx)
calculate_derivative(ctx)
find_min_temperature(ctx)
calculate_curve_params(ctx)

# Results are in: experiments/toy_example/
```

### Output Files

After running the pipeline, you'll find in `experiments/toy_example/`:

```
01_raw_organized_data.csv          - Long-format organized data
02_filtered_organized_data.csv     - After well filtering (none in this example)
03_averaged_data.csv               - Replicate averages (wide format)
03_averaged_data_long.csv          - Replicate averages (long format)
04_bg_subtracted_data.csv          - NPC background subtracted
05_min_max_scaled_data.csv         - Normalized to [0,1]
06_derivative_data.csv             - Derivative curves
07_min_temperatures.csv            - Extracted Tm values
08_curve_params.csv                - 4PL dose-response parameters
08_curve_diagnostics.csv           - Per-point fit diagnostics
experiment.log                      - Pipeline execution log
```

## Notes

- This toy example uses `_` as the condition separator (default)
- NPC controls are automatically matched and subtracted based on concentration, ligand, and buffer
- The data is synthetic but designed to look realistic
