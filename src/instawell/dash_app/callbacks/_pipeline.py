"""
Pipeline execution callbacks.
"""

import logging
import tempfile
from pathlib import Path

from dash import Input, Output, State, html
from dash.exceptions import PreventUpdate

from instawell import (
    average_across_replicates,
    calculate_derivative,
    filter_wells,
    find_min_temperature,
    ingest_data,
    load_experiment_context,
    min_max_scale,
    setup_experiment,
    subtract_background,
)

from ..constants import DEFAULT_NPC_MARKER, DEFAULT_PLACEHOLDER, DEFAULT_SEPARATOR

logger = logging.getLogger("instawell.dash_app.pipeline")


def register_pipeline_callbacks(app, cache):
    """Register pipeline execution callbacks."""

    @app.callback(
        Output("setup-status", "children"),
        Output("current-experiment-store", "data", allow_duplicate=True),
        Output("setup-complete-store", "data"),
        Output("well-filter-card", "style", allow_duplicate=True),
        Input("setup-ingest-btn", "n_clicks"),
        State("raw-data-store", "data"),
        State("layout-data-store", "data"),
        State("experiment-name-input", "value"),
        State("separator-input", "value"),
        State("fields-input", "value"),
        State("empty-placeholder-input", "value"),
        State("npc-input", "value"),
        prevent_initial_call=True,
    )
    def setup_and_ingest(
        n_clicks,
        raw_data_key,
        layout_data_key,
        exp_name,
        separator,
        fields_str,
        empty_placeholder,
        npc_marker,
    ):
        """Run setup and ingest steps only."""
        if not n_clicks:
            raise PreventUpdate

        logger.info("Starting setup & ingest for experiment '%s'", exp_name)

        raw_df = cache.get(raw_data_key)
        layout_df = cache.get(layout_data_key)

        if raw_df is None or layout_df is None:
            return (
                html.Div(
                    "Uploaded data has expired from cache. Please upload again.",
                    className="alert alert-danger",
                ),
                None,
                False,
                {"display": "none"},
            )

        try:
            # Parse fields
            fields = tuple(f.strip() for f in fields_str.split(",") if f.strip())
            sep = (separator or DEFAULT_SEPARATOR).strip() or DEFAULT_SEPARATOR
            placeholder = (
                (empty_placeholder or DEFAULT_PLACEHOLDER).strip() or DEFAULT_PLACEHOLDER
            )
            npc = (npc_marker or DEFAULT_NPC_MARKER).strip() or DEFAULT_NPC_MARKER

            # Save data to temp files (auto-cleaned)
            with tempfile.TemporaryDirectory(
                prefix="instawell_uploads_"
            ) as tmp_dir:
                temp_dir_path = Path(tmp_dir)

                raw_path = temp_dir_path / f"{exp_name}_raw.csv"
                layout_path = temp_dir_path / f"{exp_name}_layout.csv"

                raw_df.to_csv(raw_path, index=False)
                layout_df.to_csv(layout_path, index=False)

                # Step 1: Setup
                ctx = setup_experiment(
                    experiment_name=exp_name,
                    raw_data_path=str(raw_path),
                    layout_data_path=str(layout_path),
                    experiments_root=str(app.experiments_root),
                    condition_separator=sep,
                    condition_fields=fields,
                    empty_condition_placeholder=placeholder,
                    non_protein_control_marker=npc,
                )

                # Step 2: Ingest
                ingest_data(ctx)

            logger.info("Setup & ingest complete for '%s'", exp_name)
            return (
                html.Div(
                    [
                        html.I(className="fa fa-check-circle me-2"),
                        html.Strong("Setup complete! "),
                        "Review the raw data figures, filter wells, then 'Run Full Pipeline'.",
                    ],
                    className="alert alert-success",
                ),
                exp_name,
                True,  # setup_complete
                {"display": "block"},  # show well filter card
            )

        except Exception:
            logger.exception("Setup & ingest failed for '%s'", exp_name)
            return (
                html.Div(
                    [
                        html.I(className="fa fa-exclamation-triangle me-2"),
                        "Setup failed. Check server logs for details.",
                    ],
                    className="alert alert-danger",
                ),
                None,
                False,
                {"display": "none"},
            )

    @app.callback(
        Output("pipeline-status", "children"),
        Output("current-experiment-store", "data", allow_duplicate=True),
        Output("well-filter-card", "style", allow_duplicate=True),
        Output("last-pipeline-experiment", "data"),
        Input("run-pipeline-btn", "n_clicks"),
        State("current-experiment-store", "data"),
        State("filtered-wells-store", "data"),
        prevent_initial_call=True,
    )
    def run_pipeline(n_clicks, exp_name, wells_to_filter):
        """Run the full pipeline from filter step onwards."""
        if not n_clicks:
            raise PreventUpdate

        if not exp_name:
            return (
                html.Div(
                    "Please run 'Setup & View Raw Data' first",
                    className="alert alert-warning",
                ),
                None,
                {"display": "block"},
                None,
            )

        logger.info(
            "Running pipeline for '%s' (filtering %d wells)",
            exp_name,
            len(wells_to_filter or []),
        )

        try:
            # Load existing experiment context
            ctx = load_experiment_context(
                exp_name, experiments_root=str(app.experiments_root)
            )

            # Step 3: Filter wells (use selected wells from UI)
            filter_wells(ctx, wells_to_filter=wells_to_filter or [])

            # Step 4: Average
            average_across_replicates(ctx)

            # Step 5: Background subtraction
            subtract_background(ctx)

            # Step 6: Min-max scaling
            min_max_scale(ctx)

            # Step 7: Derivative
            calculate_derivative(ctx)

            # Step 8: Find Tm
            find_min_temperature(ctx)

            logger.info("Pipeline complete for '%s'", exp_name)
            return (
                html.Div(
                    [
                        html.I(className="fa fa-check-circle me-2"),
                        f"Pipeline complete for '{exp_name}'! All processing steps finished.",
                    ],
                    className="alert alert-success",
                ),
                exp_name,
                {"display": "none"},  # hide well filter card after pipeline runs
                exp_name,  # write to last-pipeline-experiment store
            )

        except Exception:
            logger.exception("Pipeline failed for '%s'", exp_name)
            return (
                html.Div(
                    [
                        html.I(className="fa fa-exclamation-triangle me-2"),
                        "Pipeline failed. Check server logs for details.",
                    ],
                    className="alert alert-danger",
                ),
                None,
                {"display": "block"},
                None,
            )
