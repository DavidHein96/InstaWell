# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Dash app test suite:** 75 unit tests (`test_dash_app.py`) for `utils`, `constants`, `designer`, and `_helpers`; 39 integration tests (`test_dash_integration.py`) covering app bootstrap smoke checks, direct callback invocation via `__wrapped__`, layout validation with cached data, and a full upload → setup → pipeline end-to-end flow.
- Added fuzz testing documentation (`docs/fuzz_testing.md`) covering the generator, test suite, tolerances, and how to add new scenarios.
- Added github actions for CI and publishing and docs site
  
### Changed

- **Dash app architecture overhaul:** Split the 1,367-line `callbacks.py` monolith into a `callbacks/` package with eight focused modules (`_session`, `_experiment`, `_upload`, `_well_filter`, `_validation`, `_pipeline`, `_figures`, `_helpers`), removing the `# noqa: C901` suppression entirely.
- Extracted magic strings and mappings into a new `constants.py` module (`FIGURE_BUTTON_MAP`, `FIGURE_STEP_FILES`, `STEP_ICONS`, default parsing settings).
- Consolidated duplicated well-parsing utilities (`WELL_PATTERN`, `normalize_well`, `parse_well_name`, `get_well_grid_dimensions`) into `utils.py`; `designer.py` now imports from there.
- Deduplicated the raw/layout upload handlers into a single `_handle_upload()` helper with pluggable validators.
- Shared separator/placeholder validation (`validate_separator_placeholder`) used by both the pipeline and the layout designer export.
- Added structured logging (`logging.getLogger("instawell.dash_app.*")`) across all Dash modules — uploads, setup, pipeline runs, figure loading, cache misses, and designer exports are now traceable in server logs.

### Fixed

- **Pipeline experiment tracking:** Replaced fragile HTML string-parsing of `pipeline-status` with a dedicated `last-pipeline-experiment` `dcc.Store`, eliminating breakage when message format changes.
- **Stack traces no longer leak to the frontend:** `setup_and_ingest` and `run_pipeline` now log exceptions server-side and show only a user-friendly message with "Check server logs for details."
- **Phantom well selection on setup:** Fixed a bug where well A1 appeared pre-selected after clicking "Setup & View Raw Data" — caused by Dash firing the pattern-matching `toggle_well_selection` callback when new well buttons rendered with `n_clicks=0`.
- Silent exception swallowing in `import_from_raw` and `load_figures` now logs warnings/exceptions instead of failing invisibly.
- Removed the hidden `wells-to-filter-checklist` compatibility hack; `update_filter_summary` reads directly from the `selected-wells-grid` store.
- Inline `import re` and `import json` moved to module-level where they belong.
- Type annotation corrected: `available_wells: List[str] | None = None` in `designer.py`.
- Added explicit `storage_type="memory"` to `figures-store` and `current-experiment-store` for clarity.
- Synthetic data generator defaults calibrated against real TSA_042/TSA_067 data (baselines, noise, NPC drift, temperature range 6–95 °C) and well-to-well variability (`baseline_cv=0.06`) added for more realistic fuzz testing.

### Developer Experience

- Full ruff and ty compliance across `src/` and `tests/` — added targeted per-file ignores in `pyproject.toml` for scientific naming conventions (`logEC50`), intentional import patterns (`E402` in `__init__.py`), and large callback registration functions.
- Switch to ty from mypy for type checking. ty overrides for test files to suppress false positives from Pydantic validation testing and pandas stub limitations.
- CI (`ci.yml`) skips `test_integration_pipeline.py` and `test_integration_tsa067.py` via `--ignore` because they depend on private TSA data files not committed to the repository. All other tests (unit, fuzz, Dash app, synthetic integration) run in CI on Python 3.10 and 3.12.

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