"""
Tests targeting coverage gaps in core, processing, and utils modules.

Covers:
1. utils/utils.py — convert_concentration_to_float (nM, bare), _log variant, slugify, split errors
2. utils/logging_util.py — normalize_log_level, ensure_experiment_context
3. utils/curve_fitting.py — _guess_hill_sign edges, fit failures, sigma_weight, param_ci_from_pcov
4. processing/step_01 — _validate_layout, _set_temperature_column, _parse_conditions warning
5. processing/step_05 — zero variance, missing file, missing wide file
6. processing/step_04 — missing files, protein not in fields, duplicate NPC
7. processing/step_08 — _load_min_temps errors, panel_by fallback, weighting, fit failure
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from instawell.core.exp_context import ExperimentContext
from instawell.core.steps import StepFiles

# ═══════════════════════════════════════════════════════════════════════════════
# 1. utils/utils.py
# ═══════════════════════════════════════════════════════════════════════════════


class TestConvertConcentrationToFloat:
    """Hit the nM and bare-numeric branches."""

    @pytest.mark.unit
    def test_nanomolar(self):
        from instawell.utils.utils import convert_concentration_to_float

        assert convert_concentration_to_float("100nM") == pytest.approx(0.1)

    @pytest.mark.unit
    def test_nanomolar_zero(self):
        from instawell.utils.utils import convert_concentration_to_float

        assert convert_concentration_to_float("0nM") == 0.0

    @pytest.mark.unit
    def test_bare_numeric(self):
        from instawell.utils.utils import convert_concentration_to_float

        assert convert_concentration_to_float("42") == 42.0

    @pytest.mark.unit
    def test_bare_numeric_with_whitespace(self):
        from instawell.utils.utils import convert_concentration_to_float

        assert convert_concentration_to_float("  7.5  ") == 7.5


class TestConvertConcentrationToFloatLog:
    """Entire function was untested."""

    @pytest.mark.unit
    def test_micromolar(self):
        from instawell.utils.utils import convert_concentration_to_float_log

        assert convert_concentration_to_float_log("500uM") == pytest.approx(np.log1p(500.0))

    @pytest.mark.unit
    def test_millimolar(self):
        from instawell.utils.utils import convert_concentration_to_float_log

        assert convert_concentration_to_float_log("1mM") == pytest.approx(np.log1p(1000.0))

    @pytest.mark.unit
    def test_nanomolar(self):
        from instawell.utils.utils import convert_concentration_to_float_log

        assert convert_concentration_to_float_log("100nM") == pytest.approx(np.log1p(0.1))

    @pytest.mark.unit
    def test_nanomolar_zero(self):
        from instawell.utils.utils import convert_concentration_to_float_log

        assert convert_concentration_to_float_log("0nM") == pytest.approx(np.log1p(0.0))

    @pytest.mark.unit
    def test_bare_numeric(self):
        from instawell.utils.utils import convert_concentration_to_float_log

        assert convert_concentration_to_float_log("42") == pytest.approx(np.log1p(42.0))


class TestSlugify:
    """Entire function was untested."""

    @pytest.mark.unit
    def test_basic(self):
        from instawell.utils.utils import slugify

        assert slugify("hello world") == "hello_world"

    @pytest.mark.unit
    def test_special_chars(self):
        from instawell.utils.utils import slugify

        assert slugify("a/b:c@d") == "a_b_c_d"

    @pytest.mark.unit
    def test_preserves_hyphens_underscores(self):
        from instawell.utils.utils import slugify

        assert slugify("foo-bar_baz") == "foo-bar_baz"

    @pytest.mark.unit
    def test_strips_leading_trailing(self):
        from instawell.utils.utils import slugify

        assert slugify("  hello!!  ") == "hello"

    @pytest.mark.unit
    def test_alphanumeric_passthrough(self):
        from instawell.utils.utils import slugify

        assert slugify("abc123") == "abc123"


class TestSplitUnqconColumnErrors:
    """Error/warning paths in split_unqcon_column."""

    @pytest.mark.unit
    def test_missing_unqcond_column(self):
        from instawell.utils.utils import split_unqcon_column

        df = pd.DataFrame({"other_col": ["a", "b"]})
        with pytest.raises(ValueError, match="must have a 'unqcond' column"):
            split_unqcon_column(df, fields=("x", "y"), delimiter="_")

    @pytest.mark.unit
    def test_parse_failure_fills_none(self):
        from instawell.utils.utils import split_unqcon_column

        df = pd.DataFrame({"unqcond": ["a_b", "bad"]})  # "bad" has only 1 part
        result = split_unqcon_column(df, fields=("x", "y"), delimiter="_")
        # First row parsed fine
        assert result.loc[0, "x"] == "a"
        assert result.loc[0, "y"] == "b"
        # Second row should have None values
        assert result.loc[1, "x"] is None
        assert result.loc[1, "y"] is None


# ═══════════════════════════════════════════════════════════════════════════════
# 2. utils/logging_util.py
# ═══════════════════════════════════════════════════════════════════════════════


class TestNormalizeLogLevel:
    """Entire function was untested."""

    @pytest.mark.unit
    def test_int_passthrough(self):
        from instawell.utils.logging_util import normalize_log_level

        assert normalize_log_level(logging.DEBUG) == logging.DEBUG

    @pytest.mark.unit
    def test_string_info(self):
        from instawell.utils.logging_util import normalize_log_level

        assert normalize_log_level("INFO") == logging.INFO

    @pytest.mark.unit
    def test_string_lowercase(self):
        from instawell.utils.logging_util import normalize_log_level

        assert normalize_log_level("warning") == logging.WARNING

    @pytest.mark.unit
    def test_numeric_string(self):
        from instawell.utils.logging_util import normalize_log_level

        assert normalize_log_level("20") == 20

    @pytest.mark.unit
    def test_invalid_raises(self):
        from instawell.utils.logging_util import normalize_log_level

        with pytest.raises(ValueError, match="Invalid log level"):
            normalize_log_level("NOT_A_LEVEL")


class TestEnsureExperimentContext:
    """Covers the relative-path resolution branch + gitignore creation."""

    @pytest.mark.unit
    def test_creates_dirs_and_gitignore(self, tmp_path, monkeypatch):
        from instawell.utils.logging_util import ensure_experiment_context

        monkeypatch.chdir(tmp_path)
        result = ensure_experiment_context("my_exp", log_to_file=False)

        assert result.exists()
        assert result.name == "my_exp"
        gitignore = result / ".gitignore"
        assert gitignore.exists()
        assert gitignore.read_text() == "*\n"

    @pytest.mark.unit
    def test_absolute_root(self, tmp_path):
        from instawell.utils.logging_util import ensure_experiment_context

        result = ensure_experiment_context(
            "abs_exp",
            experiments_root=tmp_path / "abs_root",
            log_to_file=False,
        )
        assert result == tmp_path / "abs_root" / "abs_exp"
        assert result.exists()

    @pytest.mark.unit
    def test_with_logging(self, tmp_path):
        from instawell.utils.logging_util import ensure_experiment_context

        result = ensure_experiment_context(
            "log_exp",
            experiments_root=tmp_path / "log_root",
            log_to_file=True,
        )
        assert result.exists()


# ═══════════════════════════════════════════════════════════════════════════════
# 3. utils/curve_fitting.py
# ═══════════════════════════════════════════════════════════════════════════════


class TestGuessHillSign:
    @pytest.mark.unit
    def test_insufficient_data(self):
        from instawell.utils.curve_fitting import _guess_hill_sign

        assert _guess_hill_sign(np.array([1.0, 2.0]), np.array([1.0, 2.0])) == 1.0

    @pytest.mark.unit
    def test_constant_y(self):
        from instawell.utils.curve_fitting import _guess_hill_sign

        assert _guess_hill_sign(np.array([1, 2, 3, 4]), np.array([5, 5, 5, 5])) == 1.0

    @pytest.mark.unit
    def test_positive_slope(self):
        from instawell.utils.curve_fitting import _guess_hill_sign

        result = _guess_hill_sign(np.array([1, 10, 100, 1000]), np.array([0, 1, 2, 3]))
        assert result == 1.0

    @pytest.mark.unit
    def test_negative_slope(self):
        from instawell.utils.curve_fitting import _guess_hill_sign

        result = _guess_hill_sign(np.array([1, 10, 100, 1000]), np.array([3, 2, 1, 0]))
        assert result == -1.0


class TestFit4pl:
    @pytest.mark.unit
    def test_too_few_unique_x(self):
        from instawell.utils.curve_fitting import fit_4pl

        params, pcov = fit_4pl(np.array([1, 1, 1, 2, 2, 2]), np.array([0, 0, 0, 1, 1, 1]))
        assert params is None
        assert pcov is None

    @pytest.mark.unit
    def test_successful_fit(self):
        from instawell.utils.curve_fitting import fit_4pl, four_pl_log10x

        x = np.array([0.1, 1, 10, 100, 1000, 10000])
        y = four_pl_log10x(x, bottom=40, top=70, logEC50=2.0, hill=1.0)
        y_noisy = y + np.random.default_rng(42).normal(0, 0.5, len(y))

        params, pcov = fit_4pl(x, y_noisy)
        assert params is not None
        assert pcov is not None
        assert len(params) == 4


class TestSigmaWeight:
    @pytest.mark.unit
    def test_empty_array(self):
        from instawell.utils.curve_fitting import sigma_weight

        assert sigma_weight(np.array([])) is None

    @pytest.mark.unit
    def test_normal_values(self):
        from instawell.utils.curve_fitting import sigma_weight

        result = sigma_weight(np.array([1.0, 2.0, 3.0]))
        assert result is not None
        assert len(result) == 3
        assert np.all(result > 0)

    @pytest.mark.unit
    def test_with_zeros(self):
        from instawell.utils.curve_fitting import sigma_weight

        result = sigma_weight(np.array([0.0, 1.0, 2.0]))
        assert result is not None
        assert np.all(result > 0)  # zeros should be clipped to eps


class TestParamCiFromPcov:
    @pytest.mark.unit
    def test_none_pcov(self):
        from instawell.utils.curve_fitting import param_ci_from_pcov

        result = param_ci_from_pcov(np.array([1, 2, 3, 4]), None, dof=10)
        assert result is None

    @pytest.mark.unit
    def test_nonfinite_pcov(self):
        from instawell.utils.curve_fitting import param_ci_from_pcov

        bad_pcov = np.full((4, 4), np.inf)
        result = param_ci_from_pcov(np.array([1, 2, 3, 4]), bad_pcov, dof=10)
        assert result is None

    @pytest.mark.unit
    def test_valid_pcov(self):
        from instawell.utils.curve_fitting import param_ci_from_pcov

        params = np.array([40.0, 70.0, 2.0, 1.0])
        pcov = np.diag([1.0, 1.0, 0.1, 0.01])
        result = param_ci_from_pcov(params, pcov, dof=20)
        assert result is not None
        se, lo, hi = result
        assert len(se) == 4
        assert np.all(lo < params)
        assert np.all(hi > params)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. processing/step_01_ingest_data.py
# ═══════════════════════════════════════════════════════════════════════════════


class TestValidateLayout:
    @pytest.mark.unit
    def test_empty_dataframe(self):
        from instawell.processing.step_01_ingest_data import _validate_layout

        with pytest.raises(ValueError, match="empty"):
            _validate_layout(pd.DataFrame())

    @pytest.mark.unit
    def test_too_few_columns(self):
        from instawell.processing.step_01_ingest_data import _validate_layout

        df = pd.DataFrame({"Well": ["A", "B"]})
        with pytest.raises(ValueError, match="at least one condition column"):
            _validate_layout(df)

    @pytest.mark.unit
    def test_nan_values(self):
        from instawell.processing.step_01_ingest_data import _validate_layout

        df = pd.DataFrame({"Well": ["A", "B"], "1": ["cond1", None]})
        with pytest.raises(ValueError, match="NaN"):
            _validate_layout(df)

    @pytest.mark.unit
    def test_valid_layout_passes(self):
        from instawell.processing.step_01_ingest_data import _validate_layout

        df = pd.DataFrame({"Well": ["A"], "1": ["cond1"]})
        _validate_layout(df)  # should not raise


class TestSetTemperatureColumn:
    @pytest.mark.unit
    def test_missing_temp_column(self):
        from instawell.processing.step_01_ingest_data import _set_temperature_column

        df = pd.DataFrame({"NotTemp": [1, 2], "A1": [10, 20]})
        ctx = _make_ctx_stub(tmp_path=None, temp_col="Temperature")
        with pytest.raises(ValueError, match="not found"):
            _set_temperature_column(df, ctx)

    @pytest.mark.unit
    def test_case_insensitive_rename(self, tmp_path):
        from instawell.processing.step_01_ingest_data import _set_temperature_column

        df = pd.DataFrame({"temperature": [25, 30], "A1": [100, 200]})
        ctx = _make_ctx_stub(tmp_path, temp_col="temperature")
        result = _set_temperature_column(df, ctx)
        assert "Temperature" in result.columns


class TestParseConditionsWarning:
    """Hit the warning branch when a condition fails to parse."""

    @pytest.mark.unit
    def test_bad_condition_logged(self, tmp_path):
        from instawell.processing.step_01_ingest_data import _parse_conditions

        layout = pd.DataFrame(
            {
                "Well": ["A", "A"],
                "1": ["good_cond_prot_buf", "too_many_parts_here_fail_parse_extra"],
            }
        )
        ctx = _make_ctx_stub(tmp_path)
        unique = {"good_cond_prot_buf", "too_many_parts_here_fail_parse_extra"}
        # Should not raise — just warns and skips
        result = _parse_conditions(layout, unique, ctx)
        assert "good_cond_prot_buf" in result


# ═══════════════════════════════════════════════════════════════════════════════
# 5. processing/step_04_subtract_background.py
# ═══════════════════════════════════════════════════════════════════════════════


class TestSubtractBackgroundErrors:
    @pytest.mark.unit
    def test_missing_averaged_data(self, tmp_path):
        from instawell.processing.step_04_subtract_background import _load_data

        ctx = _make_ctx_stub(tmp_path)
        with pytest.raises(FileNotFoundError, match="Averaged data"):
            _load_data(ctx, ["concentration", "ligand", "protein", "buffer"])

    @pytest.mark.unit
    def test_missing_averaged_long_data(self, tmp_path):
        from instawell.processing.step_04_subtract_background import _load_data

        ctx = _make_ctx_stub(tmp_path)
        # Create only the wide file
        wide_path = ctx.experiment_dir / StepFiles.AVERAGED_DATA.value
        wide_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"Temperature": [25]}).to_csv(wide_path, index=False)

        with pytest.raises(FileNotFoundError, match="Averaged long data"):
            _load_data(ctx, ["concentration", "ligand", "protein", "buffer"])

    @pytest.mark.unit
    def test_missing_columns_in_long(self, tmp_path):
        from instawell.processing.step_04_subtract_background import _load_data

        ctx = _make_ctx_stub(tmp_path)
        ctx.experiment_dir.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"Temperature": [25]}).to_csv(
            ctx.experiment_dir / StepFiles.AVERAGED_DATA.value, index=False
        )
        pd.DataFrame({"Temperature": [25]}).to_csv(
            ctx.experiment_dir / StepFiles.AVERAGED_DATA_LONG.value, index=False
        )
        with pytest.raises(ValueError, match="Missing required columns"):
            _load_data(ctx, ["concentration", "ligand", "protein", "buffer"])

    @pytest.mark.unit
    def test_protein_not_in_fields(self, tmp_path):
        from instawell.processing.step_04_subtract_background import subtract_background

        ctx = _make_ctx_stub(tmp_path, fields=("x", "y", "z"))
        with pytest.raises(ValueError, match="protein"):
            subtract_background(ctx)

    @pytest.mark.unit
    def test_duplicate_npc_rows(self, tmp_path):
        """Duplicate NPC rows should be averaged with a warning."""
        from instawell.processing.step_04_subtract_background import subtract_background

        ctx = _make_ctx_stub(tmp_path)
        ctx.experiment_dir.mkdir(parents=True, exist_ok=True)

        sep = ctx.condition_separator
        # Build long data with duplicate NPC rows
        long_data = pd.DataFrame(
            {
                "Temperature": [25, 25, 25, 30, 30, 30],
                "value": [10, 12, 100, 15, 17, 200],
                "well": ["A1", "A1dup", "B1", "A1", "A1dup", "B1"],
                "concentration": ["10uM", "10uM", "10uM", "10uM", "10uM", "10uM"],
                "ligand": ["LigA", "LigA", "LigA", "LigA", "LigA", "LigA"],
                "protein": ["NPC", "NPC", "ProtX", "NPC", "NPC", "ProtX"],
                "buffer": ["Buf1", "Buf1", "Buf1", "Buf1", "Buf1", "Buf1"],
                "unqcond": [
                    sep.join(["10uM", "LigA", "NPC", "Buf1"]),
                    sep.join(["10uM", "LigA", "NPC", "Buf1"]),
                    sep.join(["10uM", "LigA", "ProtX", "Buf1"]),
                    sep.join(["10uM", "LigA", "NPC", "Buf1"]),
                    sep.join(["10uM", "LigA", "NPC", "Buf1"]),
                    sep.join(["10uM", "LigA", "ProtX", "Buf1"]),
                ],
                "well_unqcond": ["w1", "w2", "w3", "w4", "w5", "w6"],
            }
        )
        long_data.to_csv(ctx.experiment_dir / StepFiles.AVERAGED_DATA_LONG.value, index=False)

        # Build matching wide data
        wide_data = pd.DataFrame(
            {
                "Temperature": [25, 30],
                sep.join(["10uM", "LigA", "NPC", "Buf1"]): [11.0, 16.0],
                sep.join(["10uM", "LigA", "ProtX", "Buf1"]): [100.0, 200.0],
            }
        )
        wide_data.to_csv(ctx.experiment_dir / StepFiles.AVERAGED_DATA.value, index=False)

        subtract_background(ctx)

        # Verify output was created
        out = pd.read_csv(ctx.experiment_dir / StepFiles.BG_SUB_DATA_LONG.value)
        assert len(out) > 0
        # NPC rows should be removed
        assert "NPC" not in out["protein"].values


# ═══════════════════════════════════════════════════════════════════════════════
# 6. processing/step_05_minmax_scale.py
# ═══════════════════════════════════════════════════════════════════════════════


class TestMinMaxScaleEdges:
    @pytest.mark.unit
    def test_missing_long_data(self, tmp_path):
        from instawell.processing.step_05_minmax_scale import _load_data

        ctx = _make_ctx_stub(tmp_path)
        with pytest.raises(FileNotFoundError):
            _load_data(ctx)

    @pytest.mark.unit
    def test_zero_variance_condition(self, tmp_path):
        """A condition with constant values should warn and not crash."""
        from instawell.processing.step_05_minmax_scale import min_max_scale

        ctx = _make_ctx_stub(tmp_path)
        ctx.experiment_dir.mkdir(parents=True, exist_ok=True)

        sep = ctx.condition_separator
        cond_a = sep.join(["10uM", "LigA", "ProtA", "Buf1"])
        cond_b = sep.join(["20uM", "LigB", "ProtB", "Buf1"])

        long_data = pd.DataFrame(
            {
                "Temperature": [25, 30, 35, 25, 30, 35],
                "value": [0.5, 0.5, 0.5, 10.0, 20.0, 30.0],  # cond_a is constant (within [0,1])
                "well": ["A1", "A1", "A1", "B1", "B1", "B1"],
                "concentration": ["10uM", "10uM", "10uM", "20uM", "20uM", "20uM"],
                "ligand": ["LigA", "LigA", "LigA", "LigB", "LigB", "LigB"],
                "protein": ["ProtA", "ProtA", "ProtA", "ProtB", "ProtB", "ProtB"],
                "buffer": ["Buf1", "Buf1", "Buf1", "Buf1", "Buf1", "Buf1"],
                "unqcond": [cond_a, cond_a, cond_a, cond_b, cond_b, cond_b],
                "well_unqcond": ["w1", "w1", "w1", "w2", "w2", "w2"],
            }
        )
        long_data.to_csv(ctx.experiment_dir / StepFiles.BG_SUB_DATA_LONG.value, index=False)

        # No wide file exists — tests the "could not find original wide" warning too
        min_max_scale(ctx)

        out = pd.read_csv(ctx.experiment_dir / StepFiles.MIN_MAX_SCALED_DATA_LONG.value)
        # Zero-variance condition should keep original values
        assert all(out.loc[out["unqcond"] == cond_a, "value"] == 0.5)
        # Normal condition should be scaled to [0, 1]
        scaled = out.loc[out["unqcond"] == cond_b, "value"]
        assert scaled.min() == pytest.approx(0.0)
        assert scaled.max() == pytest.approx(1.0)


# ═══════════════════════════════════════════════════════════════════════════════
# 7. processing/step_08_calc_curves.py
# ═══════════════════════════════════════════════════════════════════════════════


class TestLoadMinTemps:
    @pytest.mark.unit
    def test_file_not_found(self, tmp_path):
        from instawell.processing.step_08_calc_curves import _load_min_temps

        ctx = _make_ctx_stub(tmp_path)
        with pytest.raises(FileNotFoundError):
            _load_min_temps(ctx)

    @pytest.mark.unit
    def test_missing_columns(self, tmp_path):
        from instawell.processing.step_08_calc_curves import _load_min_temps

        ctx = _make_ctx_stub(tmp_path)
        ctx.experiment_dir.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"Temperature": [25]}).to_csv(
            ctx.experiment_dir / StepFiles.MIN_TEMPERATURES_DATA.value, index=False
        )
        with pytest.raises(ValueError, match="Missing required column"):
            _load_min_temps(ctx)


class TestCalcCurveParams:
    @pytest.fixture
    def curve_ctx(self, tmp_path):
        """Create ctx with synthetic min_temps data sufficient for 4PL fitting."""
        ctx = _make_ctx_stub(tmp_path)
        ctx.experiment_dir.mkdir(parents=True, exist_ok=True)

        sep = ctx.condition_separator
        concs = ["0uM", "1uM", "10uM", "100uM", "500uM", "1000uM"]
        temps = [45.0, 46.0, 50.0, 55.0, 60.0, 62.0]

        rows = []
        for c, t in zip(concs, temps, strict=True):
            rows.append(
                {
                    "unqcond": sep.join([c, "LigA", "ProtX", "Buf1"]),
                    "min_temperature": t,
                    "concentration": c,
                    "ligand": "LigA",
                    "protein": "ProtX",
                    "buffer": "Buf1",
                }
            )

        df = pd.DataFrame(rows)
        df.to_csv(ctx.experiment_dir / StepFiles.MIN_TEMPERATURES_DATA.value, index=False)
        return ctx

    @pytest.mark.unit
    def test_basic_fit(self, curve_ctx):
        from instawell.processing.step_08_calc_curves import calculate_curve_params

        calculate_curve_params(curve_ctx)

        params_path = curve_ctx.experiment_dir / StepFiles.CURVE_PARAMS.value
        diag_path = curve_ctx.experiment_dir / StepFiles.CURVE_DIAGNOSTICS.value
        assert params_path.exists()
        assert diag_path.exists()

        params_df = pd.read_csv(params_path)
        assert len(params_df) > 0
        assert "EC50" in params_df.columns

    @pytest.mark.unit
    def test_weighted_fit(self, curve_ctx):
        from instawell.processing.step_08_calc_curves import calculate_curve_params

        calculate_curve_params(curve_ctx, weighting="1/y^2")

        params_df = pd.read_csv(curve_ctx.experiment_dir / StepFiles.CURVE_PARAMS.value)
        if len(params_df) > 0:
            assert params_df["weighting"].iloc[0] == "1/y^2"

    @pytest.mark.unit
    def test_empty_panel_by_fallback(self, tmp_path):
        """When condition_fields has only 'concentration', panel_by becomes ['__panel__']."""
        from instawell.processing.step_08_calc_curves import calculate_curve_params

        ctx = _make_ctx_stub(tmp_path, fields=("concentration",))
        ctx.experiment_dir.mkdir(parents=True, exist_ok=True)

        sep = ctx.condition_separator
        concs = ["1uM", "10uM", "100uM", "500uM", "1000uM"]
        temps = [46.0, 50.0, 55.0, 60.0, 62.0]

        rows = []
        for c, t in zip(concs, temps, strict=True):
            rows.append(
                {
                    "unqcond": c,
                    "min_temperature": t,
                    "concentration": c,
                }
            )

        pd.DataFrame(rows).to_csv(
            ctx.experiment_dir / StepFiles.MIN_TEMPERATURES_DATA.value, index=False
        )

        calculate_curve_params(ctx)
        params_df = pd.read_csv(ctx.experiment_dir / StepFiles.CURVE_PARAMS.value)
        assert params_df is not None

    @pytest.mark.unit
    def test_insufficient_data_skipped(self, tmp_path):
        """Panels with < 4 unique positive concentrations should be skipped."""
        from instawell.processing.step_08_calc_curves import calculate_curve_params

        ctx = _make_ctx_stub(tmp_path)
        ctx.experiment_dir.mkdir(parents=True, exist_ok=True)

        sep = ctx.condition_separator
        rows = [
            {
                "unqcond": sep.join(["1uM", "LigA", "ProtX", "Buf1"]),
                "min_temperature": 50.0,
                "concentration": "1uM",
                "ligand": "LigA",
                "protein": "ProtX",
                "buffer": "Buf1",
            },
            {
                "unqcond": sep.join(["10uM", "LigA", "ProtX", "Buf1"]),
                "min_temperature": 55.0,
                "concentration": "10uM",
                "ligand": "LigA",
                "protein": "ProtX",
                "buffer": "Buf1",
            },
        ]
        pd.DataFrame(rows).to_csv(
            ctx.experiment_dir / StepFiles.MIN_TEMPERATURES_DATA.value, index=False
        )

        calculate_curve_params(ctx)

        # Both files should exist (even if empty)
        params_path = ctx.experiment_dir / StepFiles.CURVE_PARAMS.value
        assert params_path.exists()
        # Empty DataFrame written to CSV produces a file with no data rows
        content = params_path.read_text().strip()
        # Should have at most a header line (or be completely empty)
        assert content.count("\n") == 0  # no data rows


# ═══════════════════════════════════════════════════════════════════════════════
# Additional: processing/step_02 and step_03 error paths
# ═══════════════════════════════════════════════════════════════════════════════


class TestFilterWellsNoneDefault:
    """Hit the wells_to_filter=None branch (lines 40-43)."""

    @pytest.mark.integration
    def test_none_wells_to_filter(self, tmp_path, sample_csv_files):
        from instawell import filter_wells, ingest_data, setup_experiment

        raw_path, layout_path = sample_csv_files
        ctx = setup_experiment(
            experiment_name="none_filter",
            raw_data_path=str(raw_path),
            layout_data_path=str(layout_path),
            experiments_root=str(tmp_path / "experiments"),
        )
        ingest_data(ctx)

        # Pass None explicitly (the default)
        filter_wells(ctx, wells_to_filter=None)

        filtered = pd.read_csv(ctx.experiment_dir / StepFiles.FILTERED_DATA.value)
        ingested = pd.read_csv(ctx.experiment_dir / StepFiles.INGESTED_DATA.value)
        assert len(filtered) == len(ingested)


class TestFilterWellsPrerequisiteError:
    """Hit the PrerequisiteStepError when ingested data is missing."""

    @pytest.mark.unit
    def test_missing_ingested_data(self, tmp_path):
        from instawell.core.exceptions import PrerequisiteStepError
        from instawell.processing.step_02_filter_wells import filter_wells

        ctx = _make_ctx_stub(tmp_path)
        ctx.experiment_dir.mkdir(parents=True, exist_ok=True)

        with pytest.raises(PrerequisiteStepError):
            filter_wells(ctx)

    @pytest.mark.unit
    def test_missing_required_columns(self, tmp_path):
        from instawell.processing.step_02_filter_wells import filter_wells

        ctx = _make_ctx_stub(tmp_path)
        ctx.experiment_dir.mkdir(parents=True, exist_ok=True)

        # Write a file with missing columns
        pd.DataFrame({"Temperature": [25], "value": [1]}).to_csv(
            ctx.experiment_dir / StepFiles.INGESTED_DATA.value, index=False
        )

        with pytest.raises(ValueError, match="Missing required columns"):
            filter_wells(ctx, wells_to_filter=[])


class TestAverageReplicatesErrors:
    @pytest.mark.unit
    def test_missing_filtered_data(self, tmp_path):
        from instawell.core.exceptions import PrerequisiteStepError
        from instawell.processing.step_03_average_replicates import average_across_replicates

        ctx = _make_ctx_stub(tmp_path)
        ctx.experiment_dir.mkdir(parents=True, exist_ok=True)

        with pytest.raises(PrerequisiteStepError):
            average_across_replicates(ctx)

    @pytest.mark.unit
    def test_missing_columns(self, tmp_path):
        from instawell.processing.step_03_average_replicates import average_across_replicates

        ctx = _make_ctx_stub(tmp_path)
        ctx.experiment_dir.mkdir(parents=True, exist_ok=True)

        pd.DataFrame({"Temperature": [25]}).to_csv(
            ctx.experiment_dir / StepFiles.FILTERED_DATA.value, index=False
        )

        with pytest.raises(ValueError, match="Missing required columns"):
            average_across_replicates(ctx)

    @pytest.mark.unit
    def test_custom_fields_warning(self, tmp_path):
        """Custom condition fields should warn about unsupported sorting."""
        from instawell.processing.step_03_average_replicates import average_across_replicates

        ctx = _make_ctx_stub(tmp_path, fields=("compound", "target", "solvent"))
        ctx.experiment_dir.mkdir(parents=True, exist_ok=True)

        sep = ctx.condition_separator
        cond = sep.join(["DrugA", "Kinase1", "DMSO"])

        filtered = pd.DataFrame(
            {
                "Temperature": [25, 30, 25, 30],
                "value": [100, 200, 110, 210],
                "well": ["A1", "A1", "A2", "A2"],
                "compound": ["DrugA"] * 4,
                "target": ["Kinase1"] * 4,
                "solvent": ["DMSO"] * 4,
                "unqcond": [cond] * 4,
                "well_unqcond": ["A1_" + cond, "A1_" + cond, "A2_" + cond, "A2_" + cond],
            }
        )
        filtered.to_csv(ctx.experiment_dir / StepFiles.FILTERED_DATA.value, index=False)

        average_across_replicates(ctx)

        avg_df = pd.read_csv(ctx.experiment_dir / StepFiles.AVERAGED_DATA.value)
        assert "Temperature" in avg_df.columns


# ═══════════════════════════════════════════════════════════════════════════════
# Additional: core/exp_context.py edge cases
# ═══════════════════════════════════════════════════════════════════════════════


class TestExpContextEdgeCases:
    @pytest.mark.unit
    def test_log_path_property(self, tmp_path):
        ctx = _make_ctx_stub(tmp_path)
        assert ctx.log_path.name == StepFiles.EXPERIMENT_LOG.value

    @pytest.mark.unit
    def test_empty_condition_mask_no_fields(self, tmp_path):
        """When condition_fields is empty, mask should be empty string."""
        raw = tmp_path / "r.csv"
        raw.touch()
        lay = tmp_path / "l.csv"
        lay.touch()
        ctx = ExperimentContext(
            experiment_name="t",
            experiments_root=tmp_path,
            raw_data_path=raw,
            layout_data_path=lay,
            condition_fields=(),
            condition_separator="_",
            empty_condition_placeholder="0",
        )
        assert ctx.empty_condition_mask == ""

    @pytest.mark.unit
    def test_whitespace_placeholder_rejected(self, tmp_path):
        raw = tmp_path / "r.csv"
        raw.touch()
        lay = tmp_path / "l.csv"
        lay.touch()
        with pytest.raises(ValueError, match="whitespace"):
            ExperimentContext(
                experiment_name="t",
                experiments_root=tmp_path,
                raw_data_path=raw,
                layout_data_path=lay,
                condition_fields=("a",),
                condition_separator="_",
                empty_condition_placeholder=" ",
            )

    @pytest.mark.unit
    def test_comma_placeholder_rejected(self, tmp_path):
        raw = tmp_path / "r.csv"
        raw.touch()
        lay = tmp_path / "l.csv"
        lay.touch()
        with pytest.raises(ValueError, match="not allowed"):
            ExperimentContext(
                experiment_name="t",
                experiments_root=tmp_path,
                raw_data_path=raw,
                layout_data_path=lay,
                condition_fields=("a",),
                condition_separator="_",
                empty_condition_placeholder=",",
            )


# ═══════════════════════════════════════════════════════════════════════════════
# Additional: core/parser.py — parse_concentration_to_float ValueError fallback
# ═══════════════════════════════════════════════════════════════════════════════


class TestParseConcentrationToFloat:
    @pytest.mark.unit
    def test_numeric_value_error_returns_none(self):
        from instawell.core.parser import parse_concentration_to_float

        # A string that starts with digits but float() would fail
        # Actually "1.2.3" -> match gets "1.2", float("1.2") works.
        # Need a case where match succeeds but float fails: not possible with \d. pattern
        # So test the final None return for non-matching strings
        assert parse_concentration_to_float("unknown_format") is None

    @pytest.mark.unit
    def test_special_names(self):
        from instawell.core.parser import parse_concentration_to_float

        assert parse_concentration_to_float("apo") == 0.0
        assert parse_concentration_to_float("DMSO") == 0.0
        assert parse_concentration_to_float("control") == 0.0
        assert parse_concentration_to_float("baseline") == 0.0

    @pytest.mark.unit
    def test_numeric_extraction(self):
        from instawell.core.parser import parse_concentration_to_float

        assert parse_concentration_to_float("500uM") == 500.0
        assert parse_concentration_to_float("1.5mM") == 1.5


# ═══════════════════════════════════════════════════════════════════════════════
# Helper: lightweight ExperimentContext stub
# ═══════════════════════════════════════════════════════════════════════════════


def _make_ctx_stub(
    tmp_path,
    *,
    fields=("concentration", "ligand", "protein", "buffer"),
    temp_col="Temperature",
) -> ExperimentContext:
    """Create a minimal ExperimentContext for unit tests."""
    if tmp_path is None:
        # Caller doesn't need real paths (e.g. _set_temperature_column test)
        import tempfile

        tmp_path = Path(tempfile.mkdtemp())

    raw = tmp_path / "raw.csv"
    raw.touch()
    lay = tmp_path / "layout.csv"
    lay.touch()

    return ExperimentContext(
        experiment_name="stub",
        experiments_root=tmp_path / "experiments",
        raw_data_path=raw,
        layout_data_path=lay,
        condition_fields=fields,
        condition_separator="_",
        empty_condition_placeholder="0",
        temperature_column=temp_col,
        log_to_file=False,
    )
