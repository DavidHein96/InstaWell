# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0.b1] - 2025-11-19

### Added

- MkDocs documentation scaffold (`mkdocs.yml`) with overview, pipeline, Dash app, and development guides (`docs/index.md`, `docs/pipeline.md`, `docs/dash_app.md`, `docs/development.md`).
- Optional `docs` extra in `pyproject.toml` to install MkDocs dependencies via `pip install 'instawell[docs]'`.
- Dash CLI now accepts `--host`, `--port`, `--experiments-root`, and `--debug` flags so `instawell-dash` can run on arbitrary addresses.
- Layout validator in the Dash app, alongside configuration inputs for condition separator, missing placeholder, temperature column, and NPC marker.

### Changed

- Dash layout designer instructions now clarify the Shift+click selection gesture and highlight the “Copy from Selected Well” helper.
- Navbar icon replaced with the packaged InstaWell logo; same logo/favicons reused across the MkDocs theme for consistent branding.
- README now points to the MkDocs site for detailed docs.

### Fixed

- Dash setup step uses `tempfile.TemporaryDirectory` instead of a hard-coded `/tmp` path (Bandit B108).
- Layout designer accepts zero concentration values when assigning conditions.
- Designer exports respect the user-selected separator/placeholder, preventing parsing errors downstream.

## [0.3.0.dev3] - 2025-11-19

### Added

- Core Pipeline: First public cut of the nine-step TSA workflow (setup → ingest → filter → average → background subtraction → min/max → derivative → Tm extraction → 4PL curve fitting).
- Experiment Contexts: Deterministic file layout per experiment, with numbered CSV outputs, logging, and stored metadata for reproducible reruns.
- Plotting Suite: Raw / processed / min-temperature Plotly generators plus notebook widgets for interactive browsing.
- Dash App Preview: Early-access UI for uploading raw/layout CSVs, running the pipeline, and visualizing figures (still rough around the edges in this build).
- Testing Harness: Basic pytest scaffolding to keep the core processing steps stable as the project evolves.

This dev release sets the baseline for the TSA pipeline and Dash experience—subsequent versions will layer on the UX polish and docs we've been adding.