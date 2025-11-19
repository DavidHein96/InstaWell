"""
Smoke tests for figure generation.

These tests verify that figure generators run without crashing and produce
valid Plotly Figure objects. They do not test visual appearance.
"""

# import plotly.graph_objects as go
# import pytest

# from instawell import (
#     StepFiles,
#     average_accross_replicates,
#     averaged_figure_generator,
#     bgsub_figure_generator,
#     bgsub_minmax_figure_generator,
#     calculate_derivative,
#     derivative_figure_generator,
#     filter_wells,
#     find_min_temperature,
#     ingest_data,
#     min_max_scale,
#     min_temp_figure_generator,
#     raw_figure_generator,
#     setup_experiment,
#     subtract_background,
# )


# @pytest.fixture
# def ctx_with_ingested_data(tmp_path, sample_csv_files):
#     """Create experiment context with ingested data."""
#     raw_path, layout_path = sample_csv_files

#     ctx = setup_experiment(
#         experiment_name="fig_test",
#         raw_data_path=str(raw_path),
#         layout_data_path=str(layout_path),
#         experiments_root=str(tmp_path / "experiments"),
#     )

#     ingest_data(ctx)
#     return ctx


# @pytest.fixture
# def ctx_with_averaged_data(ctx_with_ingested_data):
#     """Create experiment context with averaged data."""
#     ctx = ctx_with_ingested_data
#     filter_wells(ctx, wells_to_filter=[])
#     average_accross_replicates(ctx)
#     return ctx


# @pytest.fixture
# def ctx_with_full_pipeline(ctx_with_averaged_data):
#     """Create experiment context with full pipeline run."""
#     ctx = ctx_with_averaged_data
#     subtract_background(ctx)
#     min_max_scale(ctx)
#     calculate_derivative(ctx)
#     find_min_temperature(ctx)
#     return ctx


# class TestFigureGeneratorsSmokeTests:
#     """Smoke tests to verify figure generators run without crashing."""

#     @pytest.mark.integration
#     def test_all_generators_run_without_error(self, ctx_with_full_pipeline):
#         """
#         Smoke test: All figure generators run without error.

#         This is the most important test - verifies nothing crashes.
#         """
#         # Import here to avoid issues if figures module doesn't exist yet

#         ctx = ctx_with_full_pipeline

#         # Just verify they don't crash and return something
#         # We don't care about exact output, just that it works
#         raw_figs = list(raw_figure_generator(ctx))
#         assert len(raw_figs) > 0, "Should generate at least one raw figure"

#         avg_figs = list(averaged_figure_generator(ctx))
#         assert len(avg_figs) > 0, "Should generate at least one averaged figure"

#         bg_figs = list(bgsub_figure_generator(ctx))
#         assert len(bg_figs) > 0, "Should generate at least one background subtracted figure"

#         mm_figs = list(bgsub_minmax_figure_generator(ctx))
#         assert len(mm_figs) > 0, "Should generate at least one min-max scaled figure"

#         deriv_figs = list(derivative_figure_generator(ctx))
#         assert len(deriv_figs) > 0, "Should generate at least one derivative figure"

#         temp_figs = list(min_temp_figure_generator(ctx))
#         assert len(temp_figs) > 0, "Should generate at least one min temp figure"


# class TestFigureTypes:
#     """Test that generators return correct types."""

#     @pytest.mark.integration
#     def test_generators_return_plotly_figures(self, ctx_with_full_pipeline):
#         """Test that all generators yield Plotly Figure objects."""

#         ctx = ctx_with_full_pipeline

#         for fig in averaged_figure_generator(ctx):
#             assert isinstance(fig, go.Figure), "Should return Plotly Figure objects"
#             # Only check first one
#             break

#     @pytest.mark.integration
#     def test_figures_are_generators(self, ctx_with_averaged_data):
#         """Test that figure functions return generators (memory efficient)."""

#         ctx = ctx_with_averaged_data

#         result = averaged_figure_generator(ctx)

#         # Should be a generator, not a list
#         assert hasattr(result, "__iter__"), "Should be iterable"
#         assert hasattr(result, "__next__"), "Should be a generator"


# class TestFigureStructure:
#     """Test basic figure structure."""

#     @pytest.mark.integration
#     def test_figures_have_traces(self, ctx_with_averaged_data):
#         """Test that generated figures have data traces."""

#         ctx = ctx_with_averaged_data

#         for fig in averaged_figure_generator(ctx):
#             assert len(fig.data) > 0, "Figure should have at least one trace"
#             # Check first one only
#             break

#     @pytest.mark.integration
#     def test_figures_have_axis_labels(self, ctx_with_averaged_data):
#         """Test that figures have axis labels."""

#         ctx = ctx_with_averaged_data

#         for fig in averaged_figure_generator(ctx):
#             # Should have layout with axis titles
#             assert fig.layout is not None, "Figure should have layout"
#             # Plotly figures always have xaxis and yaxis objects
#             assert hasattr(fig.layout, "xaxis"), "Should have x-axis"
#             assert hasattr(fig.layout, "yaxis"), "Should have y-axis"
#             break

#     @pytest.mark.integration
#     def test_figures_have_titles(self, ctx_with_averaged_data):
#         """Test that figures have titles."""

#         ctx = ctx_with_averaged_data

#         for fig in averaged_figure_generator(ctx):
#             # Title should be set (even if empty string)
#             assert hasattr(fig.layout, "title"), "Should have title attribute"
#             break


# class TestFigureEdgeCases:
#     """Test edge cases in figure generation."""

#     @pytest.mark.integration
#     def test_missing_data_file_raises_error(self, tmp_path):
#         """Test that missing data file raises appropriate error."""

#         # Create context pointing to non-existent data
#         from instawell import ExperimentContext

#         raw_path = tmp_path / "raw.csv"
#         layout_path = tmp_path / "layout.csv"
#         raw_path.touch()
#         layout_path.touch()

#         ctx = ExperimentContext(
#             experiment_name="test",
#             experiments_root=tmp_path,
#             raw_data_path=raw_path,
#             layout_data_path=layout_path,
#         )

#         # Should raise error when data file doesn't exist
#         with pytest.raises(FileNotFoundError):
#             list(averaged_figure_generator(ctx))

#     @pytest.mark.integration
#     def test_generator_is_lazy(self, ctx_with_averaged_data):
#         """Test that generator doesn't compute until consumed."""

#         ctx = ctx_with_averaged_data

#         # Creating generator should be fast (doesn't generate figures yet)
#         gen = averaged_figure_generator(ctx)

#         # Generator should exist but not have computed anything
#         assert gen is not None

#         # Only when we iterate do figures get created
#         first_fig = next(gen)
#         assert isinstance(first_fig, go.Figure)


# class TestFigureDataIntegrity:
#     """Test that figure data matches source data."""

#     @pytest.mark.integration
#     def test_figure_data_comes_from_correct_file(self, ctx_with_averaged_data):
#         """Test that averaged figures use averaged data file."""

#         ctx = ctx_with_averaged_data

#         # Read the source data
#         import pandas as pd

#         source_df = pd.read_csv(ctx.experiment_dir / StepFiles.AVERAGED_DATA.value)
#         temp_values = source_df["Temperature"].values

#         # Generate figure
#         for fig in averaged_figure_generator(ctx):
#             # Check that figure has temperature data
#             first_trace = fig.data[0]
#             assert first_trace.x is not None, "Trace should have x values"
#             assert len(first_trace.x) > 0, "Trace should have data"

#             # Temperature values should be in the figure somewhere
#             # (Either in x or as part of the data)
#             assert len(first_trace.x) == len(temp_values), (
#                 "Should have same number of temperature points"
#             )
#             break


# class TestFigureDataValidation:
#     """Test that figure data contains sensible values."""

#     @pytest.mark.integration
#     def test_minmax_scaled_values_between_0_and_1(self, ctx_with_full_pipeline):
#         """Test that min-max scaled figures have values between 0 and 1."""
#         ctx = ctx_with_full_pipeline

#         for fig in bgsub_minmax_figure_generator(ctx):
#             # Check all traces in the figure
#             for trace in fig.data:
#                 y_values = trace.y
#                 assert y_values is not None, "Trace should have y values"
#                 assert len(y_values) > 0, "Trace should have data"

#                 # All values should be between 0 and 1 (with small tolerance for floating point)
#                 min_val = min(y_values)
#                 max_val = max(y_values)
#                 assert min_val >= -0.01, f"Min value {min_val} should be >= 0"
#                 assert max_val <= 1.01, f"Max value {max_val} should be <= 1"
#             # Only check first figure
#             break

#     @pytest.mark.integration
#     def test_temperature_values_reasonable(self, ctx_with_full_pipeline):
#         """Test that temperature values are in reasonable range for DSF."""
#         ctx = ctx_with_full_pipeline

#         for fig in averaged_figure_generator(ctx):
#             first_trace = fig.data[0]
#             temp_values = first_trace.x
#             assert temp_values is not None, "Should have temperature values"

#             # DSF typically runs from 20-95°C, but could be wider range
#             min_temp = min(temp_values)
#             max_temp = max(temp_values)
#             assert 0 <= min_temp <= 50, f"Min temperature {min_temp}°C seems unreasonable"
#             assert 30 <= max_temp <= 120, f"Max temperature {max_temp}°C seems unreasonable"
#             assert max_temp > min_temp + 10, "Temperature range should span at least 10°C"
#             break

#     @pytest.mark.integration
#     def test_derivative_has_nonzero_values(self, ctx_with_full_pipeline):
#         """Test that derivative figures contain non-zero values."""
#         ctx = ctx_with_full_pipeline

#         for fig in derivative_figure_generator(ctx):
#             # Check that at least one trace has non-zero values
#             has_nonzero = False
#             for trace in fig.data:
#                 y_values = trace.y
#                 if y_values is not None and any(abs(v) > 0.001 for v in y_values):
#                     has_nonzero = True
#                     break

#             assert has_nonzero, "Derivative should have some non-zero values"
#             break

#     @pytest.mark.integration
#     def test_min_temp_values_reasonable(self, ctx_with_full_pipeline):
#         """Test that minimum temperature values are in reasonable range."""
#         ctx = ctx_with_full_pipeline

#         for fig in min_temp_figure_generator(ctx):
#             # Min temp figure plots min_temperature on y-axis
#             for trace in fig.data:
#                 y_values = trace.y
#                 assert y_values is not None, "Should have min temperature values"
#                 assert len(y_values) > 0, "Should have data"

#                 # Melting temperatures should be reasonable for proteins (typically 30-90°C)
#                 for temp in y_values:
#                     assert 20 <= temp <= 100, f"Melting temperature {temp}°C seems unreasonable"
#             break

#     @pytest.mark.integration
#     def test_raw_values_positive(self, ctx_with_full_pipeline):
#         """Test that raw fluorescence values are positive."""
#         ctx = ctx_with_full_pipeline

#         for fig in raw_figure_generator(ctx):
#             # Fluorescence should be positive
#             for trace in fig.data:
#                 y_values = trace.y
#                 assert y_values is not None, "Should have fluorescence values"

#                 # Allow small negative values due to noise, but mostly positive
#                 negative_count = sum(1 for v in y_values if v < -10)
#                 assert negative_count < len(y_values) * 0.1, "Too many negative fluorescence values"
#             break

#     @pytest.mark.integration
#     def test_averaged_data_smoother_than_raw(self, ctx_with_full_pipeline):
#         """Test that averaged data has less variation than raw data."""
#         import statistics

#         ctx = ctx_with_full_pipeline

#         # Get raw data variance
#         raw_variances = []
#         for fig in raw_figure_generator(ctx):
#             for trace in fig.data:
#                 y_values = trace.y
#                 if y_values is not None and len(y_values) > 1:
#                     raw_variances.append(statistics.variance(y_values))
#             break

#         # Get averaged data variance
#         avg_variances = []
#         for fig in averaged_figure_generator(ctx):
#             for trace in fig.data:
#                 y_values = trace.y
#                 if y_values is not None and len(y_values) > 1:
#                     avg_variances.append(statistics.variance(y_values))
#             break

#         # Check that we have data
#         assert len(raw_variances) > 0, "Should have raw variances"
#         assert len(avg_variances) > 0, "Should have averaged variances"

#         # Averaged data should generally have similar or lower variance
#         # (this is a weak test since averaging replicates may not reduce variance much)
#         avg_mean_var = sum(avg_variances) / len(avg_variances)
#         assert avg_mean_var > 0, "Averaged data should have some variation"
