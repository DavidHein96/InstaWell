# Fuzz Testing with Synthetic Data

![InstaWell icon](assets/instawell-icon-256.png){: style="width:90px"}

The InstaWell fuzz test suite generates synthetic DSF/TSA fluorescence data with known ground-truth parameters, runs the complete pipeline, and verifies that recovered Tm values and 4PL dose-response parameters match expectations. This page explains how the generator works, what each test validates, and how to extend coverage.

## Why Synthetic Data?

Real DSF experiments are expensive to run and impossible to control precisely. Synthetic data lets us:

- **Fix ground truth** &mdash; we know the exact Tm and 4PL parameters, so pipeline errors are measurable.
- **Sweep parameter space** &mdash; test combinations of Hill slopes, EC50 values, and noise levels that may never appear in a single real experiment.
- **Reproduce failures** &mdash; every curve is seeded, so a failing test always fails the same way.
- **Match production conditions** &mdash; defaults are calibrated against real TSA_042/TSA_067 experiments.

## Realistic Defaults

The generator defaults are calibrated against real instrument data:

| Parameter | Real Data (TSA_042/067) | Synthetic Default |
|---|---|---|
| Protein baseline | 3,900 &ndash; 6,700 RFU | 4,000 RFU |
| Protein amplitude | 5,400 &ndash; 12,100 RFU | 8,000 RFU |
| Protein noise | 2.4 &ndash; 4.8 RFU | 30 RFU |
| Max transition slope | 630 &ndash; 878 RFU/&deg;C | ~700 RFU/&deg;C |
| NPC baseline | 2,700 &ndash; 2,820 RFU | 2,800 RFU |
| NPC drift | &minus;0.63 to &minus;0.79 RFU/&deg;C | &minus;0.7 RFU/&deg;C |
| NPC noise | ~0.2 RFU | 5 RFU |
| Temperature range | 6 &ndash; 95 &deg;C | 6 &ndash; 95 &deg;C |
| Well-to-well CV | ~5 &ndash; 6 % | 6 % |

## Architecture

```
tests/
  synthetic_data_generator.py   # Curve generation + experiment assembly
  test_synthetic_fuzz.py        # Pipeline validation tests
```

### Data Flow

```
four_pl_tm_function()           ─── computes expected Tm per concentration
        │
        ▼
sigmoid_transition()            ─── generates clean sigmoidal fluorescence curve
        │
        ▼
generate_dsf_curve()            ─── adds Gaussian noise to sigmoid
generate_npc_curve()            ─── linear drift + noise (no transition)
        │
        ▼
SyntheticDSFExperiment          ─── assembles wells into a plate
  .add_dose_response_series()       ├── stores ground-truth Tms and 4PL params
  .add_npc_controls()               ├── applies well-to-well CV scaling
  .generate_plate_data()            └── outputs (raw_df, layout_df)
        │
        ▼
Pipeline steps 00–08           ─── ingest → filter → average → bg-sub → derivative → Tm → 4PL
        │
        ▼
Assertions                     ─── compare recovered values against ground truth
```

## Generator Reference

### Curve-Level Functions

**`generate_dsf_curve(temperature, tm, baseline, amplitude, slope, noise_std, seed)`**

Generates a single protein well. The clean fluorescence follows a logistic sigmoid from `baseline` to `baseline + amplitude`, centered at `tm` with steepness `slope`. Gaussian noise with standard deviation `noise_std` is added.

**`generate_npc_curve(temperature, baseline, drift, noise_std, seed)`**

Generates a non-protein control well. The signal is a linear ramp (`baseline + drift * dT`) plus Gaussian noise. NPC wells have no sigmoidal transition.

**`four_pl_tm_function(concentration, bottom, top, ec50, hill)`**

Computes the expected Tm at a given ligand concentration using the 4-parameter logistic model. This is the ground truth that the pipeline's Step 08 curve fitting should recover.

### Experiment Assembly

**`SyntheticDSFExperiment(temperature_range, temperature_step, seed)`**

Container that accumulates well definitions and produces plate-format CSVs.

**`.add_dose_response_series(...)`** &mdash; adds protein wells for one protein/ligand/buffer combination across a list of concentrations. Key parameters:

| Parameter | Default | Purpose |
|---|---|---|
| `n_replicates` | 3 | Technical replicates per concentration |
| `baseline` | 4,000 | Folded-state fluorescence (RFU) |
| `amplitude` | 8,000 | Unfolding signal (RFU) |
| `noise_std` | 30 | Per-point Gaussian noise (RFU) |
| `baseline_cv` | 0.06 | Well-to-well coefficient of variation |

**`.add_npc_controls(...)`** &mdash; adds NPC wells with matching concentrations. Concentration strings must match the protein series for background subtraction to pair correctly.

| Parameter | Default | Purpose |
|---|---|---|
| `n_replicates` | 2 | Technical replicates per concentration |
| `baseline` | 2,800 | NPC fluorescence (RFU) |
| `noise_std` | 5 | Per-point noise (RFU) |
| `baseline_cv` | 0.06 | Well-to-well CV |

**`.generate_plate_data()`** &mdash; assigns wells row-wise (A1, A2, ... J12) and returns `(raw_df, layout_df)`. Before generating each well's curve, a per-well scale factor is drawn from `Normal(1.0, baseline_cv)` and applied to baseline and amplitude (protein) or baseline alone (NPC).

### Ground Truth Access

- **`.get_ground_truth_tms()`** &mdash; DataFrame with columns `unqcond`, `min_temperature`, `concentration`, `ligand`, `protein`, `buffer`. One row per unique condition (concentration/ligand/protein/buffer combination).
- **`.get_ground_truth_params()`** &mdash; DataFrame with columns `bottom`, `top`, `EC50`, `logEC50`, `Hill`, `protein`, `ligand`, `buffer`. One row per dose-response panel.

## Test Suite

### TestSyntheticDataGeneration

Validates the generator itself before trusting pipeline results.

| Test | What It Checks |
|---|---|
| `test_generator_creates_valid_data` | Data shape: 141 temperature points, 35 wells, layout dimensions |
| `test_ground_truth_tms_match_4pl` | Tm at EC50 equals `(bottom + top) / 2` within 0.1 &deg;C |

### TestSingleProteinDoseResponse

Simple scenario: one protein, one ligand, 7 concentrations, low noise (`noise_std=5`).

| Test | Pipeline Steps | Tolerances |
|---|---|---|
| `test_pipeline_recovers_correct_tms` | Steps 00 &ndash; 07 | Max &Delta;Tm < 3.5 &deg;C, mean &Delta;Tm < 1.5 &deg;C |
| `test_pipeline_recovers_4pl_parameters` | Steps 00 &ndash; 08 | &Delta;bottom < 1 &deg;C, &Delta;top < 1 &deg;C, &Delta;logEC50 < 0.3, &Delta;Hill < 0.5 |

### TestMultiProteinExperiment

Three dose-response curves (Kinase1+ATP, Kinase2+ATP, Kinase1+GTP) with 104 total wells.

| Test | Tolerances |
|---|---|
| `test_multi_protein_pipeline_end_to_end` | &Delta;bottom < 2 &deg;C, &Delta;top < 10 &deg;C, &Delta;logEC50 < 1.5 |

The relaxed top and EC50 tolerances reflect that curves with shallow Hill slopes (e.g., Kinase2/ATP with Hill=0.8) may not reach saturation at the highest test concentration, making the 4PL "top" and EC50 parameters poorly constrained and dependent on extrapolation.

### TestEdgeCases

| Test | Scenario | Key Settings | Tolerance |
|---|---|---|---|
| `test_high_noise_data` | 5&times; normal noise | `noise_std=150`, 5 replicates | Max &Delta;Tm < 5 &deg;C |
| `test_shallow_transition` | Weak signal | amplitude=2000, Hill=0.5, 2 &deg;C Tm shift | Pipeline completes; Tm in [6, 95] |

### TestParameterizedFuzz

Four parametrized 4PL parameter combinations swept across the same concentration series:

| Scenario | bottom | top | EC50 | Hill |
|---|---|---|---|---|
| Standard | 40 | 60 | 50 | 1.0 |
| Steep Hill | 45 | 55 | 100 | 1.5 |
| Shallow Hill | 50 | 65 | 500 | 0.75 |
| Low EC50, large shift | 35 | 70 | 10 | 1.5 |

All validated with: &Delta;bottom < 3 &deg;C, &Delta;top < 3 &deg;C, &Delta;logEC50 < 0.3, &Delta;Hill < 1.0.

## Running Fuzz Tests

```bash
# Just fuzz tests
uv run pytest tests/test_synthetic_fuzz.py -v

# Integration tests (includes fuzz)
uv run pytest -m integration -v

# Full suite
uv run pytest -v
```

## Adding New Test Scenarios

1. **Create a fixture** that builds a `SyntheticDSFExperiment` with the parameters you want to test.
2. **Add protein series** with `add_dose_response_series()` and matching NPC controls with `add_npc_controls()`.
3. **Generate and save** CSVs with `generate_plate_data()`.
4. **Run the pipeline** through whichever steps you need.
5. **Compare** against `get_ground_truth_tms()` or `get_ground_truth_params()`.

Example &mdash; testing a two-site binding model:

```python
def test_biphasic_stabilization(self, temp_synthetic_dir, tmp_path):
    gen = SyntheticDSFExperiment(seed=555)

    # High-affinity site: large shift at low concentrations
    gen.add_dose_response_series(
        protein="TwoSiteProtein",
        ligand="Drug",
        buffer="PBS",
        concentrations=[0, 0.1, 0.3, 1, 3, 10, 30, 100],
        bottom_tm=45.0,
        top_tm=55.0,
        ec50=5.0,
        hill=1.0,
        n_replicates=3,
    )

    gen.add_npc_controls(
        ligand="Drug",
        buffer="PBS",
        concentrations=[0, 0.1, 0.3, 1, 3, 10, 30, 100],
    )

    raw_df, layout_df = gen.generate_plate_data()
    # ... save, run pipeline, assert against ground truth
```

### Choosing Tolerances

- **Tm recovery** depends on temperature step size (0.5 &deg;C discretization), noise level, and replicate count. Start with 3.5 &deg;C for standard conditions and 5 &deg;C for high noise.
- **4PL top/bottom** are well-constrained when the curve reaches both plateaus. If the highest concentration doesn't reach saturation (check with `four_pl_tm_function`), relax the top tolerance.
- **EC50 in log space** is the natural comparison scale. A tolerance of 0.3 log units means the recovered EC50 is within a 2&times; fold of the true value.
- **Hill coefficient** is the hardest parameter to recover. Use ±0.5 for clean data and ±1.0 when sweeping extreme values.
