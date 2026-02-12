"""
Integration tests for the InstaWell Dash application.

Tier 1 — App bootstrap: verifies the app builds, layout contains expected stores,
         and all callback modules register without error.
Tier 2 — Direct callback invocation: extracts registered callback functions from
         the app and calls them with controlled inputs (no browser required).
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import pytest
from dash import dcc
from dash.exceptions import PreventUpdate

from instawell import StepFiles

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def dash_app(tmp_path, monkeypatch):
    """Create a fully wired Dash app using *tmp_path* for both cache and experiments."""
    monkeypatch.chdir(tmp_path)  # keeps .instawell-cache out of the project root
    from instawell.dash_app.app import create_app

    app = create_app(experiments_root=str(tmp_path / "experiments"))
    return app


@pytest.fixture
def sample_raw_df():
    return pd.DataFrame(
        {
            "Temperature": [25.0, 30.0, 35.0, 40.0, 45.0],
            "A1": [100.0, 105.0, 110.0, 115.0, 120.0],
            "A2": [101.0, 106.0, 111.0, 116.0, 121.0],
            "B1": [200.0, 205.0, 210.0, 215.0, 220.0],
            "B2": [201.0, 206.0, 211.0, 216.0, 221.0],
        }
    )


@pytest.fixture
def sample_layout_df():
    return pd.DataFrame(
        {
            "Well": ["A", "B"],
            "1": ["500uM|ATP|Protein1|Buffer1", "1mM|GTP|NPC|Buffer2"],
            "2": ["500uM|ATP|Protein1|Buffer1", "1mM|GTP|NPC|Buffer2"],
        }
    )


@pytest.fixture
def sample_figures_data():
    """Serialised figure data as stored in ``figures-store``."""
    figs = []
    for i in range(1, 4):
        fig = go.Figure()
        fig.update_layout(title_text=f"Test Figure {i}")
        figs.append({"title": f"Test Figure {i}", "figure": fig.to_dict()})
    return figs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_callback(app, *output_ids, input_id=None):
    """Return the unwrapped callback whose key contains **all** *output_ids*.

    Dash 3 wraps registered callbacks with context management that expects
    server-side kwargs.  We use ``__wrapped__`` to bypass the wrapper and
    call the raw function directly in tests.

    Parameters
    ----------
    output_ids : str
        Substrings that must all appear in the callback_map key.
    input_id : str, optional
        If given, also require a matching ``component_id`` in the
        callback's inputs.  Useful when multiple callbacks share the
        same output (``allow_duplicate=True``).
    """
    for key, entry in app.callback_map.items():
        if not all(oid in key for oid in output_ids):
            continue
        if input_id is not None:
            raw_inputs = entry.get("raw_inputs", [])
            ids = [getattr(inp, "component_id", None) for inp in raw_inputs]
            if input_id not in ids:
                continue
        wrapped = entry["callback"]
        return getattr(wrapped, "__wrapped__", wrapped)
    available = sorted(app.callback_map.keys())
    raise KeyError(
        f"No callback matching outputs={output_ids!r}, input_id={input_id!r}.\n"
        "Available keys:\n" + "\n".join(available)
    )


def _layout_component_ids(component, target_type=None):
    """Recursively collect ``id`` values from a Dash component tree."""
    ids = set()
    if target_type is None or isinstance(component, target_type):
        cid = getattr(component, "id", None)
        if isinstance(cid, str):
            ids.add(cid)
    children = getattr(component, "children", None)
    if isinstance(children, (list, tuple)):
        for child in children:
            ids |= _layout_component_ids(child, target_type)
    elif children is not None:
        ids |= _layout_component_ids(children, target_type)
    return ids


# ===================================================================
# Tier 1 — App bootstrap smoke tests
# ===================================================================


class TestAppBootstrap:
    """Verify the app builds without errors and is correctly wired."""

    def test_app_creates_successfully(self, dash_app):
        assert dash_app is not None

    def test_experiments_root_created(self, dash_app):
        assert dash_app.experiments_root.exists()
        assert dash_app.experiments_root.is_dir()

    def test_cache_available(self, dash_app):
        dash_app.cache.set("test_key", "test_value")
        assert dash_app.cache.get("test_key") == "test_value"

    def test_layout_has_expected_stores(self, dash_app):
        store_ids = _layout_component_ids(dash_app.layout, dcc.Store)
        expected = {
            "session-id",
            "raw-data-store",
            "layout-data-store",
            "current-experiment-store",
            "filtered-wells-store",
            "setup-complete-store",
            "figures-store",
            "current-figure-index",
            "selected-wells-grid",
            "available-wells-store",
            "last-pipeline-experiment",
        }
        missing = expected - store_ids
        assert not missing, f"Missing dcc.Store IDs in layout: {missing}"

    def test_expected_callback_outputs_registered(self, dash_app):
        keys = " ".join(dash_app.callback_map.keys())
        critical_outputs = [
            "session-id.data",
            "setup-status.children",
            "pipeline-status.children",
            "figures-store.data",
            "figures-container.children",
            "filter-summary.children",
            "experiment-dropdown.options",
            "current-experiment-banner.children",
            "raw-upload-status.children",
            "layout-upload-status.children",
            "layout-validation-status.children",
            "run-pipeline-btn.disabled",
            "setup-ingest-btn.disabled",
        ]
        for output in critical_outputs:
            assert output in keys, f"Callback output {output!r} not registered"

    def test_callback_count_minimum(self, dash_app):
        # 7 callback modules + designer → at least 15 callbacks total
        assert len(dash_app.callback_map) >= 15, (
            f"Only {len(dash_app.callback_map)} callbacks registered — "
            "expected at least 15"
        )


# ===================================================================
# Tier 2 — Direct callback invocation
# ===================================================================


class TestSessionCallback:
    def test_new_session_gets_uuid(self, dash_app):
        cb = _find_callback(dash_app, "session-id.data")
        result = cb(None)
        assert isinstance(result, str)
        assert len(result) == 36  # UUID format

    def test_existing_session_preserved(self, dash_app):
        cb = _find_callback(dash_app, "session-id.data")
        assert cb("my-session") == "my-session"


class TestEnableButtons:
    """Test enable_setup_button which controls setup + validate buttons."""

    def _get_cb(self, app):
        return _find_callback(app, "setup-ingest-btn.disabled")

    def test_both_disabled_when_no_uploads(self, dash_app):
        setup_dis, validate_dis = self._get_cb(dash_app)(None, None, "exp1")
        assert setup_dis is True
        assert validate_dis is True

    def test_validate_enabled_with_uploads(self, dash_app):
        setup_dis, validate_dis = self._get_cb(dash_app)("raw_key", "layout_key", "")
        assert validate_dis is False
        assert setup_dis is True  # no experiment name yet

    def test_setup_enabled_with_all_inputs(self, dash_app):
        setup_dis, validate_dis = self._get_cb(dash_app)("raw_key", "layout_key", "exp1")
        assert setup_dis is False
        assert validate_dis is False

    def test_setup_disabled_with_blank_name(self, dash_app):
        setup_dis, _ = self._get_cb(dash_app)("raw_key", "layout_key", "   ")
        assert setup_dis is True


class TestEnablePipelineButton:
    def _get_cb(self, app):
        return _find_callback(app, "run-pipeline-btn.disabled")

    def test_disabled_when_not_setup(self, dash_app):
        assert self._get_cb(dash_app)(False) is True

    def test_enabled_when_setup_complete(self, dash_app):
        assert self._get_cb(dash_app)(True) is False


class TestFilterSummary:
    def _get_cb(self, app):
        return _find_callback(app, "filter-summary.children")

    def test_no_wells_selected(self, dash_app):
        summary, wells = self._get_cb(dash_app)([])
        assert wells == []
        assert "No wells" in str(summary)

    def test_wells_selected(self, dash_app):
        summary, wells = self._get_cb(dash_app)(["A1", "B2"])
        assert wells == ["A1", "B2"]
        assert "2 wells" in str(summary)


class TestExperimentBanner:
    def _get_cb(self, app):
        return _find_callback(app, "current-experiment-banner.children")

    def test_no_experiment(self, dash_app):
        result = self._get_cb(dash_app)(None)
        assert result is not None

    def test_with_experiment(self, dash_app):
        result = self._get_cb(dash_app)("TSA_042")
        assert "TSA_042" in str(result)


class TestFigureDisplay:
    """Test display_current_figure callback."""

    def _get_cb(self, app):
        return _find_callback(app, "figures-container.children")

    def test_no_figures_shows_placeholder(self, dash_app):
        container, nav_style, options, value, counter = self._get_cb(dash_app)(None, 0)
        assert nav_style == {"display": "none"}
        assert options == []
        assert counter == ""

    def test_with_figures(self, dash_app, sample_figures_data):
        container, nav_style, options, value, counter = self._get_cb(dash_app)(
            sample_figures_data, 1
        )
        assert nav_style == {"display": "block"}
        assert len(options) == 3
        assert value == 1
        assert "2 of 3" in counter

    def test_out_of_bounds_index_clamped(self, dash_app, sample_figures_data):
        _, _, _, value, counter = self._get_cb(dash_app)(sample_figures_data, 99)
        assert value == 0
        assert "1 of 3" in counter


class TestFigureNavigation:
    """Test navigate_previous / navigate_next / dropdown select."""

    def test_prev_at_start_stays_at_zero(self, dash_app, sample_figures_data):
        cb = _find_callback(dash_app, "current-figure-index.data", input_id="fig-prev-btn")
        assert cb(1, 0, sample_figures_data) == 0

    def test_prev_decrements(self, dash_app, sample_figures_data):
        cb = _find_callback(dash_app, "current-figure-index.data", input_id="fig-prev-btn")
        assert cb(1, 2, sample_figures_data) == 1

    def test_prev_no_click_raises(self, dash_app, sample_figures_data):
        cb = _find_callback(dash_app, "current-figure-index.data", input_id="fig-prev-btn")
        with pytest.raises(PreventUpdate):
            cb(0, 0, sample_figures_data)

    def test_next_at_end_stays(self, dash_app, sample_figures_data):
        cb = _find_callback(dash_app, "current-figure-index.data", input_id="fig-next-btn")
        assert cb(1, 2, sample_figures_data) == 2

    def test_next_increments(self, dash_app, sample_figures_data):
        cb = _find_callback(dash_app, "current-figure-index.data", input_id="fig-next-btn")
        assert cb(1, 0, sample_figures_data) == 1

    def test_next_no_click_raises(self, dash_app, sample_figures_data):
        cb = _find_callback(dash_app, "current-figure-index.data", input_id="fig-next-btn")
        with pytest.raises(PreventUpdate):
            cb(0, 0, sample_figures_data)

    def test_dropdown_select(self, dash_app, sample_figures_data):
        cb = _find_callback(
            dash_app, "current-figure-index.data", input_id="figure-selector-dropdown"
        )
        assert cb(2, sample_figures_data) == 2

    def test_dropdown_none_raises(self, dash_app, sample_figures_data):
        cb = _find_callback(
            dash_app, "current-figure-index.data", input_id="figure-selector-dropdown"
        )
        with pytest.raises(PreventUpdate):
            cb(None, sample_figures_data)


class TestValidateLayout:
    """Test the layout validation callback with cached data."""

    def _get_cb(self, app):
        return _find_callback(
            app, "layout-validation-status.children", input_id="validate-layout-btn"
        )

    def test_valid_layout(self, dash_app, sample_raw_df, sample_layout_df):
        cache = dash_app.cache
        cache.set("sess_raw.csv", sample_raw_df)
        cache.set("sess_layout.csv", sample_layout_df)

        result = self._get_cb(dash_app)(
            1, "sess_raw.csv", "sess_layout.csv", "|",
            "concentration,ligand,protein,buffer", "^", "Temperature",
        )
        assert "Validation successful" in str(result)

    def test_missing_uploads(self, dash_app):
        result = self._get_cb(dash_app)(
            1, None, None, "|", "concentration,ligand,protein,buffer", "^", "Temperature"
        )
        assert "Upload both" in str(result) or "upload" in str(result).lower()

    def test_no_click_raises(self, dash_app):
        with pytest.raises(PreventUpdate):
            self._get_cb(dash_app)(0, None, None, "|", "a,b,c,d", "^", "Temperature")

    def test_bad_separator_reports_error(self, dash_app, sample_raw_df, sample_layout_df):
        cache = dash_app.cache
        cache.set("r", sample_raw_df)
        cache.set("l", sample_layout_df)
        result = self._get_cb(dash_app)(1, "r", "l", "", "a,b,c,d", "^", "Temperature")
        assert "alert-danger" in str(result) or "error" in str(result).lower()

    def test_wrong_temperature_column(self, dash_app, sample_raw_df, sample_layout_df):
        cache = dash_app.cache
        cache.set("r", sample_raw_df)
        cache.set("l", sample_layout_df)
        result = self._get_cb(dash_app)(
            1, "r", "l", "|", "concentration,ligand,protein,buffer", "^", "NonExistent"
        )
        assert "NonExistent" in str(result) or "missing" in str(result).lower()


class TestSetupAndPipeline:
    """End-to-end: setup_and_ingest → run_pipeline using a real cache and tmp_path."""

    def _cache_dataframes(self, cache, raw_df, layout_df, session="test_session"):
        raw_key = f"{session}_raw.csv"
        layout_key = f"{session}_layout.csv"
        cache.set(raw_key, raw_df)
        cache.set(layout_key, layout_df)
        return raw_key, layout_key

    def _get_setup_cb(self, app):
        return _find_callback(app, "setup-status.children", input_id="setup-ingest-btn")

    def _get_pipeline_cb(self, app):
        return _find_callback(app, "pipeline-status.children", input_id="run-pipeline-btn")

    @pytest.mark.integration
    def test_setup_and_ingest(self, dash_app, sample_raw_df, sample_layout_df):
        cache = dash_app.cache
        raw_key, layout_key = self._cache_dataframes(cache, sample_raw_df, sample_layout_df)

        status, exp_name, setup_complete, filter_style = self._get_setup_cb(dash_app)(
            1, raw_key, layout_key, "integration_test", "|",
            "concentration,ligand,protein,buffer", "^", "NPC",
        )

        assert setup_complete is True
        assert exp_name == "integration_test"
        assert "alert-success" in str(status)

        # Verify experiment directory and ingested data file exist
        exp_dir = dash_app.experiments_root / "integration_test"
        assert exp_dir.exists()
        assert (exp_dir / StepFiles.EXPERIMENT_CONTEXT.value).exists()
        assert (exp_dir / StepFiles.INGESTED_DATA.value).exists()

    @pytest.mark.integration
    def test_full_pipeline_flow(self, dash_app, sample_raw_df, sample_layout_df):
        """Run setup_and_ingest then run_pipeline, verify all output files."""
        cache = dash_app.cache
        raw_key, layout_key = self._cache_dataframes(cache, sample_raw_df, sample_layout_df)

        # Step 1: Setup & ingest
        self._get_setup_cb(dash_app)(
            1, raw_key, layout_key, "full_pipeline_test", "|",
            "concentration,ligand,protein,buffer", "^", "NPC",
        )

        # Step 2: Run full pipeline (no wells filtered)
        status, returned_exp, filter_style, last_exp = self._get_pipeline_cb(dash_app)(
            1, "full_pipeline_test", [],
        )

        assert "alert-success" in str(status)
        assert returned_exp == "full_pipeline_test"
        assert last_exp == "full_pipeline_test"

        # Verify all pipeline output files were created
        exp_dir = dash_app.experiments_root / "full_pipeline_test"
        expected_files = [
            StepFiles.INGESTED_DATA,
            StepFiles.FILTERED_DATA,
            StepFiles.AVERAGED_DATA,
            StepFiles.BG_SUB_DATA,
            StepFiles.MIN_MAX_SCALED_DATA,
            StepFiles.DERIVATIVE_DATA,
            StepFiles.MIN_TEMPERATURES_DATA,
        ]
        for sf in expected_files:
            assert (exp_dir / sf.value).exists(), f"Missing: {sf.value}"

    @pytest.mark.integration
    def test_pipeline_with_filtered_wells(self, dash_app, sample_raw_df, sample_layout_df):
        """Pipeline succeeds when filtering out wells."""
        cache = dash_app.cache
        raw_key, layout_key = self._cache_dataframes(cache, sample_raw_df, sample_layout_df)

        self._get_setup_cb(dash_app)(
            1, raw_key, layout_key, "filter_test", "|",
            "concentration,ligand,protein,buffer", "^", "NPC",
        )

        status, *_ = self._get_pipeline_cb(dash_app)(1, "filter_test", ["A1"])

        assert "alert-success" in str(status)
        exp_dir = dash_app.experiments_root / "filter_test"
        assert (exp_dir / StepFiles.MIN_TEMPERATURES_DATA.value).exists()

    @pytest.mark.integration
    def test_setup_cache_expired(self, dash_app):
        """Setup reports error when cached data has expired."""
        status, exp_name, setup_complete, _ = self._get_setup_cb(dash_app)(
            1, "gone_raw", "gone_layout", "exp", "|", "a,b,c,d", "^", "NPC"
        )
        assert setup_complete is False
        assert exp_name is None
        assert "expired" in str(status).lower() or "upload" in str(status).lower()

    @pytest.mark.integration
    def test_pipeline_without_setup_warns(self, dash_app):
        """Pipeline warns when no experiment has been set up."""
        status, *_ = self._get_pipeline_cb(dash_app)(1, None, [])
        assert "Setup" in str(status) or "setup" in str(status).lower()
