# ts_viewer/state.py
from dataclasses import dataclass, field
from typing import Dict, List

import pandas as pd

# @dataclass
# class AppState:
#     data: pd.DataFrame = field(default_factory=pd.DataFrame)
#     group_titles: Dict[str, str] = field(default_factory=dict)
#     group_replicates: Dict[str, List[str]] = field(default_factory=dict)
#     unique_keys: List[str] = field(default_factory=list)


@dataclass
class Dataset:
    name: str
    data: pd.DataFrame
    group_titles: Dict[str, str]
    group_replicates: Dict[str, List[str]]
    unique_keys: List[str]


@dataclass
class AppState:
    # active dataset is just a name key into datasets
    datasets: Dict[str, Dataset] = field(default_factory=dict)
    active: str = ""  # name of the active dataset


state = AppState()


state = AppState()  # module-level singleton
