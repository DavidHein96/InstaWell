"""
Data models for InstaWell experiments.

This module defines the core Pydantic models used throughout the package
for representing experimental conditions and replicates.
"""

from __future__ import annotations

from typing import Annotated, List

from pydantic import BaseModel, Field
from pydantic.types import StringConstraints

# Allows underscores, dashes, and alphanumerics, but must start with a letter, no whitespace
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
    Represents a unique experimental condition with its replicates.

    A condition is defined by the combination of concentration, ligand,
    protein, and buffer. Multiple wells (replicates) can share the same
    condition.

    Attributes:
        full_name: Full condition string (e.g., '500uM_ATP_Protein1_Buffer1')
        concentration: Concentration value with units (e.g., '500uM')
        ligand_name: Name of the ligand being tested
        protein_name: Name of the target protein
        buffer_condition: Buffer composition identifier
        replicates: List of Replicate objects for this condition

    Example:
        >>> condition = UniqueCondition(
        ...     full_name="500uM_ATP_Protein1_Buffer1",
        ...     concentration="500uM",
        ...     ligand_name="ATP",
        ...     protein_name="Protein1",
        ...     buffer_condition="Buffer1",
        ... )
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

    # Optional: enforce a required/allowed set (can be injected from config)


#     _required_keys: set[str] = {"concentration", "ligand", "protein", "buffer"}
#     _allowed_keys: Optional[set[str]] = None  # or set([...]) to enforce a whitelist

#     @field_validator("dimensions")
#     @classmethod
#     def check_required_and_allowed(cls, dims: Dict[str, str]):
#         missing = cls._required_keys - set(dims)
#         if missing:
#             raise ValueError(f"Missing required dimension keys: {sorted(missing)}")
#         if cls._allowed_keys is not None:
#             extra = set(dims) - cls._allowed_keys
#             if extra:
#                 raise ValueError(f"Disallowed dimension keys: {sorted(extra)}")
#         return dims

#     @field_validator("full_name", mode="before")
#     @classmethod
#     def compute_full_name(cls, v, info):
#         # Build a stable, readable name from the dimensions.
#         dims: Dict[str, str] = info.data.get("dimensions", {})  # already validated
#         if not dims:
#             return v or ""
#         # fixed order for reproducibility; fall back to alpha if not all are present
#         order: Iterable[str] = ["concentration", "ligand", "protein", "buffer"] + sorted(
#             set(dims) - {"concentration", "ligand", "protein", "buffer"}
#         )
#         parts = [f"{k}={dims[k]}" for k in order if k in dims]
#         return "|".join(parts)
