

# InstaWell

![instawell — thermal shift tools](https://raw.githubusercontent.com/DavidHein96/InstaWell/main/docs/assets/instawell-icon-256.png)

A powerful toolkit for analyzing Differential Scanning Fluorimetry (DSF) / Thermal Shift Assay data.

InstaWell helps researchers process temperature-dependent fluorescence measurements from multi-well plates, identify melting temperatures (Tm), and compare protein stability across different experimental conditions.

## Features

## Quick Start (CLI)

### 1. Initialize an Experiment

```bash
instawell init TSA_001 --raw raw_data.csv --layout plate_layout.csv
```

### 2. Run the Pipeline

```bash
# Run entire pipeline
instawell run TSA_001 --all

# Or run specific steps
instawell run TSA_001 --steps ingest,filter,average,background,scale,derivative,min_temp

# Filter problematic wells
instawell run TSA_001 --all --filter-wells A1,B2,G20
```

### 3. View Results

```bash
# List all experiments
instawell list

# Show experiment info
instawell info TSA_001 --verbose
```

## CLI Commands Reference

### `instawell init` - Initialize Experiment
```bash
instawell init EXPERIMENT_NAME --raw DATA.csv --layout LAYOUT.csv [OPTIONS]
```

### `instawell run` - Run Pipeline
```bash
instawell run EXPERIMENT_NAME --all [--filter-wells WELLS]
```

### `instawell list` - List Experiments
```bash
instawell list
```

### `instawell info` - Show Experiment Details
```bash
instawell info EXPERIMENT_NAME [--verbose]
```

### `instawell filter` - Filter Wells
```bash
instawell filter EXPERIMENT_NAME WELL1 [WELL2 ...]
```

For detailed documentation, run `instawell --help` or `instawell COMMAND --help`.
