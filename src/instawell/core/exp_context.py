from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field, FilePath, computed_field, field_validator, model_validator

from .steps import StepFiles

logger = logging.getLogger(__name__)


class ExperimentContext(BaseModel):
    """
    Configuration and paths for a single Instawell experiment.

    This object is:
    - created during setup_experiment()
    - saved to `experiment.json` in the experiment directory
    - passed into subsequent processing and plotting steps.
    - can be re-loaded with load_experiment_context()
    """

    experiment_name: str

    # Where all experiments live (default ./experiments)
    experiments_root: Path = Field(default_factory=lambda: Path("experiments"))

    # INSIDE experiment dir
    raw_data_path: Path
    layout_data_path: Path

    # Tracks the original input files
    raw_data_source: FilePath | None = None
    layout_data_source: FilePath | None = None

    # Field names in the order they appear in condition strings (must match layout data)
    condition_fields: tuple[str, ...] = ("concentration", "ligand", "protein", "buffer")
    well_col_identifier: str = "Well"
    empty_condition_placeholder: str = "0"
    condition_separator: str = "_"
    temperature_column: str = "Temperature"
    non_protein_control_marker: str = "NPC"

    # write the last edited datetime to the metadata
    # Timestamp (persisted)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when this context was created.",
    )

    # logging options
    log_to_file: bool = True
    log_level: int = logging.INFO

    @property
    def experiment_dir(self) -> Path:
        return (self.experiments_root / self.experiment_name).resolve()

    @property
    def log_path(self) -> Path:
        return self.experiment_dir / StepFiles.EXPERIMENT_LOG.value

    @property
    def metadata_path(self) -> Path:
        return self.experiment_dir / StepFiles.EXPERIMENT_CONTEXT.value

    @computed_field  # included in model_dump / JSON
    @property
    def created_at_iso(self) -> str:
        """ISO 8601 string version of created_at (nice for logs/UI)."""
        return self.created_at.isoformat()

    # validator that separator is a single character, and not a whitespace or comma or other char that might cause issues
    @field_validator("condition_separator")
    @classmethod
    def validate_condition_separator(cls, v: str) -> str:
        """
        Ensure the separator is a single, safe, non-whitespace, non-confusing char.
        """
        if len(v) != 1:
            raise ValueError("condition_separator must be exactly one character.")
        if v.isspace():
            raise ValueError("condition_separator cannot be whitespace.")
        if v in {",", ";"}:
            raise ValueError(
                f"condition_separator '{v}' is not allowed "
                "(commas/semicolons conflict with CSV/TSV parsing)."
            )
        # optional: discourage alphanumerics, which make parsing ambiguous
        if v.isalnum():
            raise ValueError(
                f"condition_separator '{v}' should not be a letter or digit; "
                "pick something like '|', ':', or '~'."
            )
        return v

    @computed_field
    @property
    def empty_condition_mask(self) -> str:
        """
        Mask pattern used to represent an all-empty condition row.

        Example:
            fields = ("a", "b", "c", "d")
            empty_condition_placeholder = "^"
            condition_separator = "|"

            -> "^|^|^|^"
        """
        n = len(self.condition_fields)
        if n == 0:
            return ""
        return self.condition_separator.join(self.empty_condition_placeholder for _ in range(n))

    @field_validator("empty_condition_placeholder")
    @classmethod
    def validate_empty_placeholder(cls, v: str) -> str:
        if len(v) != 1:
            raise ValueError("empty_condition_placeholder must be exactly one character.")
        if v.isspace():
            raise ValueError("empty_condition_placeholder cannot be whitespace.")
        if v in {",", ";"}:
            raise ValueError(
                f"empty_condition_placeholder '{v}' is not allowed "
                "(commas/semicolons conflict with CSV/TSV parsing)."
            )
        return v

    @model_validator(mode="after")
    def validate_separator_and_placeholder(self) -> ExperimentContext:
        # Must not collide
        if self.empty_condition_placeholder == self.condition_separator:
            raise ValueError(
                "empty_condition_placeholder and condition_separator must be different "
                f"(both are '{self.condition_separator}' right now)."
            )

        # If fields exist, mask must be non-empty (sanity check)
        if self.condition_fields and not self.empty_condition_mask:
            raise ValueError(
                "empty_condition_mask computed as empty; check fields/placeholder config."
            )

        return self
