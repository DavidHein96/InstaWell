"""
Data models for InstaWell experiments.

This module defines the core Pydantic models used throughout the package
for representing experimental conditions and replicates.
"""

from __future__ import annotations

from typing import Annotated, List

from pydantic import BaseModel, Field
from pydantic.types import StringConstraints

# Alphanumerics only, must start with a letter, no whitespace
FriendlyStr = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        pattern=r"^[A-Za-z][A-Za-z0-9]*$",
    ),
]

# Allow exactly one character that is EITHER "0" for backwards compatibility
# OR a non-alphanumeric, non-underscore, non-whitespace, not comma/semicolon.
SingleSymbol = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=1,
        pattern=r"^(?:0|[^A-Za-z0-9_\s,;])$",
    ),
]


class Replicate(BaseModel):
    """
    Represents a single replicate well in an experiment.

    Attributes:
        well_row: The row identifier (e.g., 'A', 'B', 'C')
        well_column: The column identifier (e.g., '1', '2', '3')
        well_name: Combined well identifier (e.g., 'A1', 'B2')
    """

    well_row: str
    well_column: str
    well_name: str


class UniqueCondition(BaseModel):
    """
    Legacy fixed-dimension condition model with hardcoded fields.
    Deprecated in favor of Condition which supports flexible condition_fields.
    Kept for backwards compatibility with older experiment data.
    """

    full_name: str = ""
    concentration: str = ""
    ligand_name: str = ""
    protein_name: str = ""
    buffer_condition: str = ""
    replicates: List[Replicate] = Field(default_factory=list)


class Condition(BaseModel):
    """
    Core + flexible dimensions.
    - dimensions: variable key/value pairs (e.g., {"concentration": "500uM", "ligand": "ATP"})
    - replicates: your list of Replicate
    - full_name: computed from dimensions (stable naming)
    """

    full_name: str = ""
    condition_fields: tuple[str, ...] = ("concentration", "ligand", "protein", "buffer")
    dimensions: dict[str, str] = Field(default_factory=dict)
    replicates: List[Replicate] = Field(default_factory=list)
