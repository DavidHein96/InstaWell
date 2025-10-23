"""
Data models for InstaWell experiments.

This module defines the core Pydantic models used throughout the package
for representing experimental conditions and replicates.
"""

from typing import List
from pydantic import BaseModel, Field


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
