from typing import List

from pydantic import BaseModel, Field


class Replicate(BaseModel):
    well_row: str
    well_column: str
    well_name: str


class UniqueCondition(BaseModel):
    full_name: str = ""
    concentration: float = 0.0  # µM
    ligand_name: str = ""
    protein_name: str = ""
    buffer_condition: str = ""
    replicates: List[Replicate] = Field(default_factory=list)
