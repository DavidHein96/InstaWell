import logging

import pandas as pd

from instawell.core.exp_context import ExperimentContext
from instawell.core.steps import StepFiles
from instawell.utils.logging_util import setup_experiment_logging

logger = logging.getLogger(__name__)


def _load_data(ctx: ExperimentContext, dims: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    averaged_data_path = ctx.experiment_dir / StepFiles.AVERAGED_DATA.value
    averaged_data_long_path = ctx.experiment_dir / StepFiles.AVERAGED_DATA_LONG.value

    if not averaged_data_path.exists():
        raise FileNotFoundError(f"Averaged data file not found: {averaged_data_path}")
    if not averaged_data_long_path.exists():
        raise FileNotFoundError(f"Averaged long data file not found: {averaged_data_long_path}")

    long = pd.read_csv(averaged_data_long_path)

    # Basic validity
    required_cols = {"Temperature", "value", "unqcond", *dims}
    missing = required_cols.difference(long.columns)
    if missing:
        raise ValueError(f"Missing required columns in averaged long data: {sorted(missing)}")
    wide = pd.read_csv(averaged_data_path)
    return wide, long


def subtract_background(ctx: ExperimentContext) -> None:
    """
    Subtract the non-protein control (NPC) trace from each matching protein trace
    and drop NPC rows from the dataset.

    Parameters
    ----------
    ctx : ExperimentContext
        Experiment context with access to averaged wide/long data and the
        configured ``non_protein_control_marker``.

    Side Effects
    ------------
    - Reads ``03_averaged_data.csv`` and ``03_averaged_data_long.csv``.
    - Writes ``04_bg_subtracted_data.csv`` (wide) and
      ``04_bg_subtracted_data_long.csv`` (long).

    Raises
    ------
    FileNotFoundError
        If either averaged data file is missing.
    ValueError
        If required columns are absent or ``protein`` is not part of the
        configured condition fields.
    """
    if ctx.log_to_file:
        setup_experiment_logging(
            experiment_dir=ctx.experiment_dir, filename="experiment.log", level=ctx.log_level
        )

    npc = ctx.non_protein_control_marker
    dims = list(ctx.condition_fields)

    if "protein" not in dims:
        raise ValueError("Background subtraction requires 'protein' in ctx.condition_fields.")

    wide, long = _load_data(ctx, dims)

    # ---- Build background (NPC) map keyed by all dims except 'protein' + Temperature ----
    key_dims = [d for d in dims if d != "protein"]
    bg = long.loc[long["protein"] == npc, ["Temperature", *key_dims, "value"]].rename(
        columns={"value": "_bg"}
    )

    # If duplicates exist (shouldn't after averaging replicates), reduce safely
    if bg.duplicated(subset=["Temperature", *key_dims]).any():
        logger.warning("Duplicate NPC rows detected for some keys; averaging them.")
        bg = bg.groupby(["Temperature", *key_dims], as_index=False)["_bg"].mean()

    # ---- Join NPC to *all* rows on Temperature + key_dims ----
    long = long.merge(bg, on=["Temperature", *key_dims], how="left")

    # ---- Subtract for non-NPC rows only ----
    is_npc_row = long["protein"].astype(str) == str(npc)
    had_bg = long["_bg"].notna()

    # Warn for keys without NPC
    missing_bg_keys = long.loc[~is_npc_row & ~had_bg, ["Temperature", *dims]].drop_duplicates()
    if not missing_bg_keys.empty:
        logger.warning(
            "No NPC background found for %d condition/temperature combinations; left unchanged.",
            len(missing_bg_keys),
        )

    # Perform subtraction
    long.loc[~is_npc_row & had_bg, "value"] = (
        long.loc[~is_npc_row & had_bg, "value"] - long.loc[~is_npc_row & had_bg, "_bg"]
    )

    # ---- Clean up the DataFrame ----
    # Remove the original NPC rows
    long_clean = long.loc[~is_npc_row].copy()
    # Drop the temporary background column
    long_clean = long_clean.drop(columns=["_bg"], errors="ignore")

    # ---- Build wide matrix again from cleaned long ----
    wide_clean = long_clean.pivot(
        index="Temperature", columns="unqcond", values="value"
    ).reset_index()

    # ---- Re-order columns to match original averaged data file ----
    original_cols = wide.columns
    # Filter for columns that still exist after dropping NPC columns
    final_cols = [col for col in original_cols if col in wide_clean.columns]
    wide_clean = wide_clean[final_cols]

    # ---- Save outputs ----
    bg_sub_wide_path = ctx.experiment_dir / StepFiles.BG_SUB_DATA.value
    wide_clean.to_csv(bg_sub_wide_path, index=False)

    out_path = ctx.experiment_dir / StepFiles.BG_SUB_DATA_LONG.value
    long_clean.to_csv(out_path, index=False)

    logger.info("Background subtraction complete. Saved wide table to %s", bg_sub_wide_path)
