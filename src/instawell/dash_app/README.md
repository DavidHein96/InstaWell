# InstaWell Dash App

A fully-featured interactive web interface for DSF (Differential Scanning Fluorimetry) data analysis.

## Features

- **Experiment Browser**: View and select existing experiments
- **Layout Designer**: Visual tool to create plate layouts (96 or 384-well)
  - Interactive grid for selecting wells
  - Assign conditions (concentration, ligand, protein, buffer)
  - Import from raw CSV to highlight data wells
  - Export layout.csv ready for pipeline
- **CSV Upload**: Upload raw data and layout files directly in the browser
- **Pipeline Configuration**: Customize separator, field order, and other parameters
- **Full Pipeline Execution**: Run the complete InstaWell pipeline with one click
- **Interactive Figures**: View all pipeline outputs:
  - Raw fluorescence data
  - Averaged replicates
  - Background subtracted
  - Min-max normalized
  - Derivative (-dY/dT)
  - Melting temperatures (Tm)

## Installation

Install with Dash dependencies:

```bash
pip install -e ".[dash]"
```

## Usage

### Command Line

Start the Dash app:

```bash
instawell-dash
```

Then open your browser to http://127.0.0.1:8050

### Python API

```python
from instawell.dash_app import create_app

app = create_app(experiments_root="experiments", debug=True)
app.run(host="127.0.0.1", port=8050)
```

## Architecture

The Dash app is built on top of the tested InstaWell core library:

- **No duplicate logic**: 100% reuses tested pipeline code
- **Consistent behavior**: Same results as CLI
- **Full feature support**: Custom separators, field orders, etc.
- **Clean codebase**: ~500 lines vs 2370 in old viewer

## Files

- `app.py` - Main app creation and configuration
- `layout.py` - UI components (navbar, upload forms, figure display)
- `callbacks.py` - Interactive behavior (uploads, pipeline execution, figure viewing)
- `utils.py` - Helper functions (parsing, experiment listing)

## Workflow

1. **Browse Existing**: Select an experiment from the dropdown to view its figures
2. **Upload New**:
   - Upload raw data CSV (with Temperature column)
   - Upload layout CSV (with well labels)
   - Configure experiment name and parameters
   - Click "Run Pipeline"
3. **View Results**: Use figure type buttons to switch between different visualizations
