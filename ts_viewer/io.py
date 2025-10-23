import base64
import io
import os
from pathlib import Path
from typing import Dict, Tuple

import pandas as pd

from .keys import make_group_key
from .models import Replicate, UniqueCondition
from .units import to_uM


def get_unique_conditions(
    layout_csv: Path, print_to_check: bool = False
) -> Dict[str, UniqueCondition]:
    df = pd.read_csv(layout_csv)
    info: Dict[str, UniqueCondition] = {}

    for _, row in df.iterrows():
        well_letter = row.get("Well", row.get("well", row.get("well_row")))
        if pd.isna(well_letter):
            continue
        well_letter = str(well_letter)

        for col in df.columns:
            try:
                col_num = str(int(float(col)))
            except ValueError:
                continue
            cond = row.get(col)
            if not isinstance(cond, str) or cond in ("", "0_0_0_0"):
                continue
            parts = cond.split("_")
            if len(parts) < 4:
                continue

            conc = to_uM(parts[-4])
            lig = parts[-3]
            pro = parts[-2]
            buf = parts[-1]
            rep = Replicate(
                well_row=well_letter, well_column=col_num, well_name=well_letter + col_num
            )

            if cond not in info:
                info[cond] = UniqueCondition(
                    full_name=cond,
                    concentration=conc,
                    ligand_name=lig,
                    protein_name=pro,
                    buffer_condition=buf,
                )
            info[cond].replicates.append(rep)
    return info


def to_long_dataframe(raw_csv: Path, info: Dict[str, UniqueCondition]) -> pd.DataFrame:
    raw = pd.read_csv(raw_csv)
    if "Temperature" not in raw.columns:
        return pd.DataFrame()

    long = raw.melt(id_vars=["Temperature"], var_name="replicate_id", value_name="value")

    # map replicate to condition fields
    well2cond = {}
    for uc in info.values():
        for rep in uc.replicates:
            well2cond[rep.well_name] = dict(
                concentration=float(uc.concentration),
                ligand=uc.ligand_name,
                protein=uc.protein_name,
                buffer=uc.buffer_condition,
            )

    long["concentration"] = long["replicate_id"].map(
        lambda w: well2cond.get(w, {}).get("concentration")
    )
    long["ligand"] = long["replicate_id"].map(lambda w: well2cond.get(w, {}).get("ligand"))
    long["protein"] = long["replicate_id"].map(lambda w: well2cond.get(w, {}).get("protein"))
    long["buffer"] = long["replicate_id"].map(lambda w: well2cond.get(w, {}).get("buffer"))
    long = long.dropna(subset=["concentration", "ligand", "protein", "buffer"])

    long["Temperature"] = pd.to_numeric(long["Temperature"], errors="coerce")
    long["value"] = pd.to_numeric(long["value"], errors="coerce")
    long = long.dropna(subset=["Temperature", "value", "concentration"])

    long["group_key"] = long.apply(
        lambda r: make_group_key(r["concentration"], r["ligand"], r["protein"], r["buffer"]), axis=1
    )
    return long


# NEW: parse a Dash upload (base64) into a pandas DataFrame
def df_from_upload(contents: str, filename: str) -> pd.DataFrame:
    """contents like 'data:text/csv;base64,....'"""
    content_type, content_string = contents.split(",", 1)
    decoded = base64.b64decode(content_string)
    # csv only for now; easy to extend to xlsx via pandas
    return pd.read_csv(io.BytesIO(decoded))


# NEW: build tidy DF & UI maps from two dataframes (layout_df is not used directly by pipeline)
def build_dataset_from_dfs(
    layout_df: pd.DataFrame, raw_df: pd.DataFrame
) -> Tuple[pd.DataFrame, Dict[str, str], Dict[str, list]]:
    # Write layout_df to a temp CSV-like buffer to reuse existing parser
    tmp = Path(os.getenv("TMPDIR", "/tmp"))
    lay = tmp / "layout_upload.csv"
    raw = tmp / "raw_upload.csv"
    layout_df.to_csv(lay, index=False)
    raw_df.to_csv(raw, index=False)

    info = get_unique_conditions(lay, print_to_check=False)
    tidy = to_long_dataframe(raw, info)

    titles, reps = {}, {}
    for uc in info.values():
        key = make_group_key(uc.concentration, uc.ligand_name, uc.protein_name, uc.buffer_condition)
        titles[key] = (
            f"C{uc.concentration:g} {uc.ligand_name} + {uc.protein_name} in {uc.buffer_condition}"
        )
        reps[key] = sorted([r.well_name for r in uc.replicates])

    return tidy, titles, reps


# NEW: save uploaded CSVs to disk (for persistence)
def save_uploaded_pair(
    data_dir: Path, dataset_name: str, layout_df: pd.DataFrame, raw_df: pd.DataFrame
) -> Tuple[Path, Path]:
    ds_dir = data_dir / dataset_name
    ds_dir.mkdir(parents=True, exist_ok=True)
    layout_path = ds_dir / "layout.csv"
    raw_path = ds_dir / "raw.csv"
    layout_df.to_csv(layout_path, index=False)
    raw_df.to_csv(raw_path, index=False)
    return layout_path, raw_path


# NEW: load a dataset from disk folder (data/<name>/layout.csv, raw.csv)
def load_dataset_from_disk(ds_dir: Path) -> Tuple[pd.DataFrame, Dict[str, str], Dict[str, list]]:
    layout_csv = ds_dir / "layout.csv"
    raw_csv = ds_dir / "raw.csv"
    info = get_unique_conditions(layout_csv, print_to_check=False)
    tidy = to_long_dataframe(raw_csv, info)
    titles, reps = {}, {}
    for uc in info.values():
        key = make_group_key(uc.concentration, uc.ligand_name, uc.protein_name, uc.buffer_condition)
        titles[key] = (
            f"C{uc.concentration:g} {uc.ligand_name} + {uc.protein_name} in {uc.buffer_condition}"
        )
        reps[key] = sorted([r.well_name for r in uc.replicates])
    return tidy, titles, reps
