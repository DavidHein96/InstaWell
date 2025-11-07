from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd

from instawell.core.exp_context import ExperimentContext
from instawell.utils.logging_util import ensure_experiment_context, setup_experiment_logging

logger = logging.getLogger(__name__)


def setup_experiment(
    experiment_name: str,
    raw_data_path: str,
    layout_data_path: str,
    *,
    fields: tuple[str, ...] = ("concentration", "ligand", "protein", "buffer"),
    well_col_identifier: str = "Well",
    condition_separator: str = "_",
    empty_condition_placeholder: str = "0",
    non_protein_control_marker: str = "NPC",
    experiments_root: str | Path = "experiments",
    temperature_column: str = "Temperature",
    log_to_file: bool = True,
    log_level: int = logging.INFO,
) -> ExperimentContext:
    """
    Step 00: Set up the experiment directory, logging, and copy input files.

    Can be called either with an ExperimentContext:
        setup_experiment(ctx=my_ctx)

    or with individual arguments:
        setup_experiment(
            raw_data_path="raw.csv",
            layout_data_path="layout.csv",
            experiment_name="exp_001",
        )
    """

    tmp_ctx = ExperimentContext(
        experiment_name=experiment_name,
        raw_data_path=Path(raw_data_path),
        layout_data_path=Path(layout_data_path),
        experiments_root=Path(experiments_root),
        log_to_file=log_to_file,
        log_level=log_level,
        fields=fields,
        well_col_identifier=well_col_identifier,
        empty_condition_placeholder=empty_condition_placeholder,
        condition_separator=condition_separator,
        temperature_column=temperature_column,
        non_protein_control_marker=non_protein_control_marker,
    )
    experiment_dir = ensure_experiment_context(
        experiment_name=tmp_ctx.experiment_name,
        experiments_root=tmp_ctx.experiments_root,
        log_to_file=tmp_ctx.log_to_file,
        log_level=tmp_ctx.log_level,
    )

    # Ensure experiment directory + logging (this handles ./experiments/<name>)

    logger.info("Created new experiment directory at %s", experiment_dir)

    # Copy source files into experiment dir
    raw_df = pd.read_csv(tmp_ctx.raw_data_path)
    layout_df = pd.read_csv(tmp_ctx.layout_data_path)

    raw_copy = experiment_dir / tmp_ctx.raw_data_path.name
    layout_copy = experiment_dir / tmp_ctx.layout_data_path.name

    raw_df.to_csv(raw_copy, index=False)
    layout_df.to_csv(layout_copy, index=False)

    logger.info("Raw data copied to %s", raw_copy)
    logger.info("Layout data copied to %s", layout_copy)

    ctx = ExperimentContext(
        experiment_name=experiment_name,
        experiments_root=tmp_ctx.experiments_root,
        raw_data_path=raw_copy,
        layout_data_path=layout_copy,
        raw_data_source=tmp_ctx.raw_data_source,
        layout_data_source=tmp_ctx.layout_data_source,
        log_to_file=log_to_file,
        log_level=log_level,
        temperature_column=temperature_column,
        fields=fields,
        well_col_identifier=well_col_identifier,
        empty_condition_placeholder=empty_condition_placeholder,
        condition_separator=condition_separator,
        non_protein_control_marker=non_protein_control_marker,
    )
    if ctx.log_to_file:
        setup_experiment_logging(
            experiment_dir=ctx.experiment_dir, filename="experiment.log", level=ctx.log_level
        )

    logger.info(
        "Experiment '%s' setup completed in %s",
        ctx.experiment_name,
        experiment_dir,
    )
    ctx.metadata_path.write_text(ctx.model_dump_json(indent=2), encoding="utf-8")

    return ctx


def load_experiment_context(
    experiment_name: str,
    experiments_root: str | Path = "experiments",
) -> ExperimentContext:
    """
    Reload an ExperimentContext for an existing experiment.

    Looks for ./experiments/<experiment_name>/experiment.json by default.
    """
    experiments_root = Path(experiments_root)
    experiment_dir = (
        experiments_root if experiments_root.is_absolute() else Path.cwd() / experiments_root
    ) / experiment_name

    metadata_path = experiment_dir / "experiment.json"

    if not metadata_path.exists():
        raise FileNotFoundError(
            f"Could not find experiment metadata at: {metadata_path}\n"
            "This usually means step 00 (setup_experiment) has not been run "
            "or the experiment directory is incomplete."
        )

    data = json.loads(metadata_path.read_text(encoding="utf-8"))

    # Normalize paths back to Path objects relative to experiment_dir if needed
    # (they were saved as absolute or already correct by Pydantic)
    ctx = ExperimentContext.model_validate(data)

    # Safety: if experiments_root wasn't stored (older runs), fall back
    if not ctx.experiments_root.is_absolute() and not (ctx.experiments_root.exists()):
        ctx.experiments_root = experiments_root

    return ctx
