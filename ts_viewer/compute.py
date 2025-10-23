from typing import List, Tuple

import numpy as np
import pandas as pd

from .keys import make_group_key, parse_group_key


def compute_series_for_group(
    group_key: str,
    selected_replicates: List[str],
    bg_sub_enabled: bool,
    all_data: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    conc, ligand, protein, buffer = parse_group_key(group_key)
    group_df_all = all_data[all_data["group_key"] == group_key].copy()

    reps_df = (
        group_df_all
        if not selected_replicates
        else group_df_all[
            group_df_all["replicate_id"].isin([str(r) for r in selected_replicates])
        ].copy()
    )
    if reps_df.empty:
        return pd.DataFrame(), pd.DataFrame()

    avg_df = (
        reps_df.groupby("Temperature", as_index=False)["value"]
        .mean()
        .rename(columns={"value": "avg"})
    )

    if bg_sub_enabled and protein != "NPC":
        npc_key = make_group_key(conc, ligand, "NPC", buffer)
        npc_all = all_data[all_data["group_key"] == npc_key]
        if not npc_all.empty:
            npc_avg = (
                npc_all.groupby("Temperature", as_index=False)["value"]
                .mean()
                .rename(columns={"value": "npc"})
            )
            merged = pd.merge(avg_df, npc_avg, on="Temperature", how="inner")
            if not merged.empty:
                avg_df = pd.DataFrame(
                    {"Temperature": merged["Temperature"], "avg": merged["avg"] - merged["npc"]}
                )

    summary = avg_df.copy()
    if not summary.empty:
        a_min, a_max = summary["avg"].min(), summary["avg"].max()
        summary["avg_norm"] = 0.5 if a_max <= a_min else (summary["avg"] - a_min) / (a_max - a_min)

    if len(summary) > 1:
        temps = summary["Temperature"].to_numpy()
        vals = summary["avg"].to_numpy()
        order = np.argsort(temps)
        temps_s, vals_s = temps[order], vals[order]
        deriv = np.gradient(vals_s, temps_s)
        negd = -1.0 * deriv
        dmin, dmax = float(np.min(negd)), float(np.max(negd))
        norm = 0.5 if dmax <= dmin else (negd - dmin) / (dmax - dmin)
        summary = pd.DataFrame(
            {
                "Temperature": temps_s,
                "avg": vals_s,
                "avg_norm": np.interp(temps_s, summary["Temperature"], summary["avg_norm"]),
                "neg_deriv": negd,
                "neg_deriv_norm": norm,
            }
        )
    return summary, reps_df[["Temperature", "replicate_id", "value"]].copy()
