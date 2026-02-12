from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Literal

import pandas as pd

from instawell.core.exp_context import ExperimentContext
from instawell.core.steps import StepFiles
from instawell.utils.logging_util import (
    ensure_experiment_context,
    normalize_log_level,
    setup_experiment_logging,
)

logger = logging.getLogger(__name__)


def setup_experiment(
    experiment_name: str,
    raw_data_path: str,
    layout_data_path: str,
    *,
    condition_fields: tuple[str, ...] = ("concentration", "ligand", "protein", "buffer"),
    condition_separator: str = "_",
    empty_condition_placeholder: str = "0",
    non_protein_control_marker: str = "NPC",
    experiments_root: str | Path = "experiments",
    log_to_file: bool = True,
    log_level: int | Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = logging.INFO,
) -> ExperimentContext:
    """
    Creates a new experiment directory and sets up the ExperimentContext. It also copies the raw data and layout files into the experiment directory. The returned ExperimentContext can then be passed to subsequent processing steps. To reload this experiment context later, use load_experiment_context(). Calling this function with the same experiment_name will not overwrite existing data, but if you want to change things but use the same name, you can call this function with different parameters and it will edit the saved experiment.json file. Note that if you change this, the data files that you create with subsequent steps may not match the new parameters.

    Parameters
    ----------
    experiment_name : str
        Experiment name, used to create a directory under experiments_root.
    raw_data_path : str
        Path to the raw data file, should be a CSV.
    layout_data_path : str
        Path to the layout data file, should be a CSV.
    condition_fields : tuple[str, ...], optional
        Layout fields in the order they appear in condition strings. Make sure these match the actual fields used in your layout. By default ("concentration", "ligand", "protein", "buffer").
    condition_separator : str, optional
        Used to split condition strings into their components in the layout file, by default "_"
    empty_condition_placeholder : str, optional
        Represents missing or empty condition values in the layout file, by default "0"
    non_protein_control_marker : str, optional
        Used to mark non-protein control samples that will be used for background subtraction. By default "NPC"
    experiments_root : str | Path, optional
        Path to the experiments root directory, by default "experiments", this is where all new experiment directories will be created, by default relative to the current working directory.
    log_to_file : bool, optional
        Whether to log actions to a log file in the exp dir, by default True
    log_level : int, optional
        logging level, set to 30 or logging.WARNING for less verbosity, by default logging.INFO

    Returns
    -------
    ExperimentContext
        The context for the experiment, containing all relevant paths and settings. This can be passed to subsequent processing steps.
    """

    log_level = normalize_log_level(log_level)

    # tmp made here so that experiment_dir can be created first, and then the final ctx can contain the correct absolute paths
    tmp_ctx = ExperimentContext(
        experiment_name=experiment_name,
        raw_data_path=Path(raw_data_path),
        layout_data_path=Path(layout_data_path),
        experiments_root=Path(experiments_root),
        log_to_file=log_to_file,
        log_level=log_level,
        condition_fields=condition_fields,
        well_col_identifier="Well",
        empty_condition_placeholder=empty_condition_placeholder,
        condition_separator=condition_separator,
        temperature_column="Temperature",
        non_protein_control_marker=non_protein_control_marker,
    )
    experiment_dir = ensure_experiment_context(
        experiment_name=tmp_ctx.experiment_name,
        experiments_root=tmp_ctx.experiments_root,
        log_to_file=tmp_ctx.log_to_file,
        log_level=tmp_ctx.log_level,
    )

    logger.info("Created new experiment directory at %s", experiment_dir)

    # read here to validate early
    raw_df = pd.read_csv(tmp_ctx.raw_data_path)
    layout_df = pd.read_csv(tmp_ctx.layout_data_path)

    raw_copy = experiment_dir / tmp_ctx.raw_data_path.name
    layout_copy = experiment_dir / tmp_ctx.layout_data_path.name

    raw_df.to_csv(raw_copy, index=False)
    layout_df.to_csv(layout_copy, index=False)

    logger.info("Raw data copied to %s", raw_copy)
    logger.info("Layout data copied to %s", layout_copy)

    exp_root = experiment_dir.parent

    ctx = ExperimentContext(
        experiment_name=experiment_name,
        experiments_root=exp_root,
        raw_data_path=raw_copy,
        layout_data_path=layout_copy,
        raw_data_source=tmp_ctx.raw_data_source,
        layout_data_source=tmp_ctx.layout_data_source,
        log_to_file=log_to_file,
        log_level=log_level,
        temperature_column="Temperature",
        condition_fields=condition_fields,
        well_col_identifier="Well",
        empty_condition_placeholder=empty_condition_placeholder,
        condition_separator=condition_separator,
        non_protein_control_marker=non_protein_control_marker,
    )
    if ctx.log_to_file:
        setup_experiment_logging(
            experiment_dir=ctx.experiment_dir,
            filename=StepFiles.EXPERIMENT_LOG.value,
            level=ctx.log_level,
        )

    logger.info(
        "Experiment '%s' setup completed in %s",
        ctx.experiment_name,
        experiment_dir,
    )
    ctx.metadata_path.write_text(ctx.model_dump_json(indent=2), encoding="utf-8")

    logger.info("Pass the returned ctx to ingest_data(ctx) to process the raw data.")
    logger.info(
        "To reload this experiment later, use load_experiment_context('%s')", ctx.experiment_name
    )

    return ctx


def load_experiment_context(
    experiment_name: str,
    experiments_root: str | Path = "experiments",
) -> ExperimentContext:
    """
    Reload an ExperimentContext for an existing experiment.
    Looks for ./experiments/<experiment_name>/experiment.json by default.

    Parameters
    ----------
    experiment_name : str
        The name of the experiment to load.
    experiments_root : str | Path, optional
        The root directory for experiments, by default "experiments"

    Returns
    -------
    ExperimentContext
        The loaded experiment context.

    Raises
    ------
    FileNotFoundError
        If the experiment metadata file is not found.
    """
    experiments_root = Path(experiments_root)
    experiment_dir = (
        experiments_root if experiments_root.is_absolute() else Path.cwd() / experiments_root
    ) / experiment_name

    metadata_path = experiment_dir / StepFiles.EXPERIMENT_CONTEXT.value

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
    logger.info("Loaded experiment context for '%s' from %s", experiment_name, metadata_path)

    return ctx
