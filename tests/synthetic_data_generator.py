"""
Synthetic DSF/TSA data generator for testing the InstaWell pipeline.

This module generates realistic thermal shift assay data with known ground-truth
parameters, allowing comprehensive testing of the entire pipeline.
"""

from typing import Optional

import numpy as np
import pandas as pd


def sigmoid_transition(
    temperature: np.ndarray,
    tm: float,
    min_val: float = 0.0,
    max_val: float = 1.0,
    slope: float = 0.1,
) -> np.ndarray:
    """
    Generate a sigmoidal fluorescence transition curve.

    This simulates protein unfolding where fluorescence changes from min_val
    to max_val as temperature increases through the melting temperature (Tm).

    Args:
        temperature: Array of temperature values
        tm: Melting temperature (inflection point)
        min_val: Minimum fluorescence (folded state)
        max_val: Maximum fluorescence (unfolded state)
        slope: Transition steepness (higher = sharper transition)

    Returns:
        Array of fluorescence values
    """
    return min_val + (max_val - min_val) / (1 + np.exp(-slope * (temperature - tm)))


def four_pl_tm_function(
    concentration: float,
    bottom: float,
    top: float,
    ec50: float,
    hill: float,
) -> float:
    """
    Calculate Tm at a given concentration using 4PL dose-response model.

    Args:
        concentration: Ligand concentration (uM)
        bottom: Tm at zero concentration (baseline)
        top: Tm at infinite concentration (maximum stabilization)
        ec50: Concentration giving half-maximal effect
        hill: Hill slope (steepness)

    Returns:
        Melting temperature at that concentration
    """
    if concentration <= 0:
        return bottom

    log_conc = np.log10(concentration)
    log_ec50 = np.log10(ec50)

    return bottom + (top - bottom) / (1 + 10 ** ((log_ec50 - log_conc) * hill))


def generate_dsf_curve(
    temperature: np.ndarray,
    tm: float,
    baseline: float = 1000.0,
    amplitude: float = 8000.0,
    slope: float = 0.15,
    noise_std: float = 50.0,
    seed: Optional[int] = None,
) -> np.ndarray:
    """
    Generate a synthetic DSF fluorescence curve with realistic noise.

    Args:
        temperature: Array of temperature values
        tm: Melting temperature
        baseline: Baseline fluorescence (folded state)
        amplitude: Fluorescence increase upon unfolding
        slope: Transition steepness
        noise_std: Standard deviation of Gaussian noise
        seed: Random seed for reproducibility

    Returns:
        Array of fluorescence values with noise
    """
    if seed is not None:
        np.random.seed(seed)

    # Generate clean sigmoid curve
    fluorescence = sigmoid_transition(
        temperature,
        tm=tm,
        min_val=baseline,
        max_val=baseline + amplitude,
        slope=slope,
    )

    # Add Gaussian noise
    noise = np.random.normal(0, noise_std, size=temperature.shape)

    return fluorescence + noise


def generate_npc_curve(
    temperature: np.ndarray,
    baseline: float = 500.0,
    drift: float = 10.0,
    noise_std: float = 30.0,
    seed: Optional[int] = None,
) -> np.ndarray:
    """
    Generate a non-protein control (NPC) curve with minimal signal.

    Args:
        temperature: Array of temperature values
        baseline: Baseline fluorescence
        drift: Linear drift per degree
        noise_std: Standard deviation of noise
        seed: Random seed for reproducibility

    Returns:
        Array of fluorescence values
    """
    if seed is not None:
        np.random.seed(seed)

    # Linear drift + noise (no transition)
    signal = baseline + drift * (temperature - temperature[0])
    noise = np.random.normal(0, noise_std, size=temperature.shape)

    return signal + noise


class SyntheticDSFExperiment:
    """
    Generator for complete synthetic DSF experiments with known ground truth.

    This class generates:
    - Raw fluorescence data (wide format)
    - Plate layout
    - Ground truth Tm values
    - Ground truth 4PL parameters
    """

    def __init__(
        self,
        temperature_range: tuple[float, float] = (25.0, 95.0),
        temperature_step: float = 0.5,
        seed: int = 42,
    ):
        """
        Initialize the synthetic experiment generator.

        Args:
            temperature_range: (min, max) temperature in °C
            temperature_step: Temperature increment
            seed: Random seed for reproducibility
        """
        self.temperature = np.arange(
            temperature_range[0],
            temperature_range[1] + temperature_step,
            temperature_step,
        )
        self.seed = seed
        self.conditions = []
        self.ground_truth_tms = {}
        self.ground_truth_params = {}

    def add_dose_response_series(
        self,
        protein: str,
        ligand: str,
        buffer: str,
        concentrations: list[float],  # in uM
        bottom_tm: float,
        top_tm: float,
        ec50: float,
        hill: float,
        n_replicates: int = 3,
        baseline: float = 1000.0,
        amplitude: float = 8000.0,
        noise_std: float = 50.0,
    ):
        """
        Add a complete dose-response series to the experiment.

        Args:
            protein: Protein name
            ligand: Ligand name
            buffer: Buffer condition
            concentrations: List of concentrations in uM
            bottom_tm: Tm at zero concentration
            top_tm: Tm at infinite concentration
            ec50: EC50 in uM
            hill: Hill slope
            n_replicates: Number of technical replicates per condition
            baseline: Baseline fluorescence
            amplitude: Fluorescence amplitude
            noise_std: Noise level
        """
        # Store ground truth parameters
        panel_key = f"{ligand}_{protein}_{buffer}"
        self.ground_truth_params[panel_key] = {
            "bottom": bottom_tm,
            "top": top_tm,
            "EC50": ec50,
            "logEC50": np.log10(ec50),
            "Hill": hill,
            "protein": protein,
            "ligand": ligand,
            "buffer": buffer,
        }

        # Generate conditions for each concentration
        for conc in concentrations:
            # Calculate ground truth Tm
            tm = four_pl_tm_function(conc, bottom_tm, top_tm, ec50, hill)

            # Format concentration string
            if conc == 0:
                conc_str = "0uM"
            elif conc < 1:
                conc_str = f"{int(conc * 1000)}nM"
            elif conc < 1000:
                conc_str = f"{int(conc)}uM"
            else:
                conc_str = f"{conc / 1000:.1f}mM"

            condition_str = f"{conc_str}_{ligand}_{protein}_{buffer}"

            # Store ground truth Tm
            self.ground_truth_tms[condition_str] = {
                "min_temperature": tm,
                "concentration": conc_str,
                "ligand": ligand,
                "protein": protein,
                "buffer": buffer,
            }

            # Generate replicates
            for rep in range(n_replicates):
                self.conditions.append(
                    {
                        "condition": condition_str,
                        "concentration": conc_str,
                        "ligand": ligand,
                        "protein": protein,
                        "buffer": buffer,
                        "tm": tm,
                        "replicate": rep,
                        "baseline": baseline,
                        "amplitude": amplitude,
                        "noise_std": noise_std,
                        "is_npc": False,
                    }
                )

    def add_npc_controls(
        self,
        ligand: str,
        buffer: str,
        concentrations: list[float],
        n_replicates: int = 2,
        baseline: float = 500.0,
        noise_std: float = 30.0,
    ):
        """
        Add non-protein control (NPC) wells.

        Args:
            ligand: Ligand name
            buffer: Buffer condition
            concentrations: List of concentrations in uM
            n_replicates: Number of replicates
            baseline: NPC baseline fluorescence
            noise_std: Noise level
        """
        for conc in concentrations:
            # Format concentration string
            if conc == 0:
                conc_str = "0uM"  # Must match protein wells for background subtraction
            elif conc < 1:
                conc_str = f"{int(conc * 1000)}nM"
            elif conc < 1000:
                conc_str = f"{int(conc)}uM"
            else:
                conc_str = f"{conc / 1000:.1f}mM"

            condition_str = f"{conc_str}_{ligand}_NPC_{buffer}"

            for rep in range(n_replicates):
                self.conditions.append(
                    {
                        "condition": condition_str,
                        "concentration": conc_str,
                        "ligand": ligand,
                        "protein": "NPC",
                        "buffer": buffer,
                        "tm": None,
                        "replicate": rep,
                        "baseline": baseline,
                        "noise_std": noise_std,
                        "is_npc": True,
                    }
                )

    def generate_plate_data(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Generate raw fluorescence data and plate layout.

        Returns:
            Tuple of (raw_data_df, layout_df)
        """
        # Assign wells (row-wise, A1, A2, ..., B1, B2, ...)
        rows = "ABCDEFGH"
        cols = list(range(1, 13))  # 1-12

        wells = []
        for row in rows:
            for col in cols:
                wells.append(f"{row}{col}")

        if len(self.conditions) > len(wells):
            raise ValueError(
                f"Too many conditions ({len(self.conditions)}) for available wells ({len(wells)})"
            )

        # Generate fluorescence data for each well
        raw_data = {"Temperature": self.temperature}
        layout_data = {"Well": list(rows[:8])}  # First column is row labels

        # Initialize layout columns
        for col in cols:
            layout_data[str(col)] = [""] * 8

        for i, condition in enumerate(self.conditions):
            well = wells[i]
            row_letter = well[0]
            col_number = int(well[1:])
            row_idx = rows.index(row_letter)

            # Generate fluorescence curve
            if condition["is_npc"]:
                fluorescence = generate_npc_curve(
                    self.temperature,
                    baseline=condition["baseline"],
                    noise_std=condition["noise_std"],
                    seed=self.seed + i,
                )
            else:
                fluorescence = generate_dsf_curve(
                    self.temperature,
                    tm=condition["tm"],
                    baseline=condition["baseline"],
                    amplitude=condition["amplitude"],
                    noise_std=condition["noise_std"],
                    seed=self.seed + i,
                )

            # Add to raw data
            raw_data[well] = fluorescence

            # Add to layout
            layout_data[str(col_number)][row_idx] = condition["condition"]

        raw_df = pd.DataFrame(raw_data)
        layout_df = pd.DataFrame(layout_data)

        return raw_df, layout_df

    def get_ground_truth_tms(self) -> pd.DataFrame:
        """
        Get ground truth Tm values as a DataFrame.

        Returns:
            DataFrame with columns: unqcond, min_temperature, concentration, ligand, protein, buffer
        """
        records = []
        for unqcond, data in self.ground_truth_tms.items():
            records.append(
                {
                    "unqcond": unqcond,
                    **data,
                }
            )

        return pd.DataFrame(records)

    def get_ground_truth_params(self) -> pd.DataFrame:
        """
        Get ground truth 4PL parameters as a DataFrame.

        Returns:
            DataFrame with columns matching Step 08 output format
        """
        records = []
        for panel_key, params in self.ground_truth_params.items():
            records.append(params)

        return pd.DataFrame(records)
