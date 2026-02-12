"""
Smoke tests for figure generation.

These tests verify that figure generators run without crashing and produce
valid Plotly Figure objects. They do not test visual appearance.
"""

import plotly.graph_objects as go
import pytest
from synthetic_data_generator import SyntheticDSFExperiment

from instawell import (
    average_across_replicates,
    calculate_derivative,
    filter_wells,
    find_min_temperature,
    ingest_data,
    min_max_scale,
    setup_experiment,
    subtract_background,
)
from instawell.figures.min_temp_fig import min_temp_figure_generator
from instawell.figures.processed_data_fig import processed_figure_generator
from instawell.figures.raw_data_fig import raw_figure_generator


@pytest.fixture
def ctx_with_full_pipeline(tmp_path):
    """Run the full pipeline on synthetic data and return the context."""
    gen = SyntheticDSFExperiment(seed=42)

    gen.add_dose_response_series(
        protein="Protein1",
        ligand="Ligand1",
        buffer="Buffer1",
        concentrations=[0, 10, 100, 1000],
        bottom_tm=45.0,
        top_tm=55.0,
        ec50=100.0,
        hill=1.0,
        n_replicates=2,
        noise_std=5.0,
    )

    gen.add_npc_controls(
        ligand="Ligand1",
        buffer="Buffer1",
        concentrations=[0, 10, 100, 1000],
    )

    raw_df, layout_df = gen.generate_plate_data()
    raw_df.to_csv(tmp_path / "raw.csv", index=False)
    layout_df.to_csv(tmp_path / "layout.csv", index=False)

    ctx = setup_experiment(
        experiment_name="fig_test",
        raw_data_path=str(tmp_path / "raw.csv"),
        layout_data_path=str(tmp_path / "layout.csv"),
        experiments_root=str(tmp_path / "experiments"),
    )

    ingest_data(ctx)
    filter_wells(ctx, wells_to_filter=[])
    average_across_replicates(ctx)
    subtract_background(ctx)
    min_max_scale(ctx)
    calculate_derivative(ctx)
    find_min_temperature(ctx)

    return ctx


class TestFigureGeneratorsSmokeTests:
    """Smoke tests to verify figure generators run and return Plotly Figures."""

    @pytest.mark.integration
    def test_raw_figure_generator(self, ctx_with_full_pipeline):
        figs = list(raw_figure_generator(ctx_with_full_pipeline))
        assert len(figs) > 0
        assert all(isinstance(f, go.Figure) for f in figs)

    @pytest.mark.integration
    @pytest.mark.parametrize(
        "data_source",
        ["averaged_data", "bg_subtracted_data", "min_max_scaled_data", "derivative_data"],
    )
    def test_processed_figure_generator(self, ctx_with_full_pipeline, data_source):
        figs = list(processed_figure_generator(ctx_with_full_pipeline, data_source=data_source))
        assert len(figs) > 0
        assert all(isinstance(f, go.Figure) for f in figs)

    @pytest.mark.integration
    def test_min_temp_figure_generator(self, ctx_with_full_pipeline):
        figs = list(min_temp_figure_generator(ctx_with_full_pipeline))
        assert len(figs) > 0
        assert all(isinstance(f, go.Figure) for f in figs)

    @pytest.mark.integration
    def test_figures_have_traces(self, ctx_with_full_pipeline):
        """Every generated figure should contain at least one data trace."""
        for fig in raw_figure_generator(ctx_with_full_pipeline):
            assert len(fig.data) > 0
            break
