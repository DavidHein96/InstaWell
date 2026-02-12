"""
Tests for the InstaWell Dash application modules.

Covers:
- utils.py — pure utility functions (well parsing, validation, upload, experiments)
- constants.py — mapping consistency checks
- designer.py — plate grid helpers (get_row_labels, infer_plate_from_raw)
- callbacks/_helpers.py — upload handler and refresh helper
"""

import base64
import json
from unittest.mock import MagicMock

import pandas as pd
import pytest

from instawell import StepFiles

# ──────────────────────────────────────────────────────────────────────
# utils.py
# ──────────────────────────────────────────────────────────────────────
from instawell.dash_app.utils import (
    WELL_PATTERN,
    get_experiment_list,
    get_experiment_status,
    get_well_grid_dimensions,
    normalize_well,
    parse_upload,
    parse_well_name,
    validate_separator_placeholder,
)


class TestWellPattern:
    """Tests for the precompiled WELL_PATTERN regex."""

    @pytest.mark.parametrize(
        "inp,row,col",
        [
            ("A1", "A", "1"),
            ("B12", "B", "12"),
            ("A01", "A", "1"),
            ("H08", "H", "8"),
            ("  C3  ", "C", "3"),
            ("AA24", "AA", "24"),
        ],
    )
    def test_valid_wells(self, inp, row, col):
        m = WELL_PATTERN.match(inp)
        assert m is not None
        assert m.group(1).upper() == row
        assert str(int(m.group(2))) == col

    @pytest.mark.parametrize("inp", ["", "1A", "123", "!"])
    def test_invalid_wells(self, inp):
        assert WELL_PATTERN.match(inp) is None


class TestNormalizeWell:
    """Tests for normalize_well()."""

    @pytest.mark.parametrize(
        "inp,expected",
        [
            ("A01", "A1"),
            ("B12", "B12"),
            ("a1", "A1"),
            ("H008", "H8"),
            ("  C03 ", "C3"),
        ],
    )
    def test_normal_cases(self, inp, expected):
        assert normalize_well(inp) == expected

    def test_invalid_returns_stripped(self):
        assert normalize_well("Temperature") == "Temperature"

    def test_non_string_input(self):
        assert normalize_well(42) == "42"


class TestParseWellName:
    """Tests for parse_well_name()."""

    @pytest.mark.parametrize(
        "inp,expected",
        [
            ("A1", ("A", 1)),
            ("B12", ("B", 12)),
            ("H8", ("H", 8)),
            ("AA24", ("AA", 24)),
        ],
    )
    def test_valid(self, inp, expected):
        assert parse_well_name(inp) == expected

    @pytest.mark.parametrize("inp", ["", "123", "bad", "!", "1A"])
    def test_invalid(self, inp):
        assert parse_well_name(inp) == (None, None)


class TestGetWellGridDimensions:
    """Tests for get_well_grid_dimensions()."""

    def test_basic(self):
        rows, cols = get_well_grid_dimensions(["A1", "A2", "B1", "B2"])
        assert rows == ["A", "B"]
        assert cols == [1, 2]

    def test_non_contiguous(self):
        rows, cols = get_well_grid_dimensions(["A1", "C3", "A3"])
        assert rows == ["A", "C"]
        assert cols == [1, 3]

    def test_empty_list(self):
        assert get_well_grid_dimensions([]) == ([], [])

    def test_invalid_wells_only(self):
        assert get_well_grid_dimensions(["bad", "nope"]) == ([], [])

    def test_mixed_valid_invalid(self):
        rows, cols = get_well_grid_dimensions(["A1", "bad", "B2"])
        assert rows == ["A", "B"]
        assert cols == [1, 2]


class TestValidateSeparatorPlaceholder:
    """Tests for validate_separator_placeholder()."""

    def test_valid(self):
        assert validate_separator_placeholder("|", "^") == ("|", "^")
        assert validate_separator_placeholder("_", "0") == ("_", "0")

    def test_empty_separator_raises(self):
        with pytest.raises(ValueError, match="separator"):
            validate_separator_placeholder("", "^")

    def test_empty_placeholder_raises(self):
        with pytest.raises(ValueError, match="placeholder"):
            validate_separator_placeholder("|", "")

    def test_multi_char_separator_raises(self):
        with pytest.raises(ValueError, match="separator"):
            validate_separator_placeholder("||", "^")

    def test_multi_char_placeholder_raises(self):
        with pytest.raises(ValueError, match="placeholder"):
            validate_separator_placeholder("|", "^^")

    def test_same_char_raises(self):
        with pytest.raises(ValueError, match="different"):
            validate_separator_placeholder("|", "|")


class TestParseUpload:
    """Tests for parse_upload()."""

    def _encode_csv(self, csv_text: str) -> str:
        """Encode CSV text as a data URI like Dash produces."""
        b64 = base64.b64encode(csv_text.encode()).decode()
        return f"data:text/csv;base64,{b64}"

    def test_valid_csv(self):
        csv = "Temperature,A1,A2\n25.0,100,101\n30.0,105,106\n"
        df = parse_upload(self._encode_csv(csv), "data.csv")
        assert list(df.columns) == ["Temperature", "A1", "A2"]
        assert len(df) == 2

    def test_non_csv_raises(self):
        with pytest.raises(ValueError, match="CSV"):
            parse_upload("data:;base64,abc", "data.xlsx")

    def test_single_column_csv(self):
        csv = "col1\nval1\nval2\n"
        df = parse_upload(self._encode_csv(csv), "one.csv")
        assert len(df.columns) == 1
        assert len(df) == 2


class TestGetExperimentList:
    """Tests for get_experiment_list()."""

    def test_no_directory(self, tmp_path):
        missing = tmp_path / "nonexistent"
        assert get_experiment_list(missing) == []

    def test_empty_directory(self, tmp_path):
        assert get_experiment_list(tmp_path) == []

    def test_dirs_without_experiment_json(self, tmp_path):
        (tmp_path / "exp1").mkdir()
        assert get_experiment_list(tmp_path) == []

    def test_valid_experiments(self, tmp_path):
        for name in ["zeta", "alpha", "beta"]:
            d = tmp_path / name
            d.mkdir()
            (d / "experiment.json").write_text("{}")
        assert get_experiment_list(tmp_path) == ["alpha", "beta", "zeta"]

    def test_mixed_valid_invalid(self, tmp_path):
        valid = tmp_path / "good"
        valid.mkdir()
        (valid / "experiment.json").write_text("{}")
        (tmp_path / "bad_dir").mkdir()  # no experiment.json
        (tmp_path / "some_file.txt").write_text("hi")  # not a dir
        assert get_experiment_list(tmp_path) == ["good"]


class TestGetExperimentStatus:
    """Tests for get_experiment_status()."""

    def test_empty_experiment_dir(self, tmp_path):
        status = get_experiment_status(tmp_path)
        assert status["completed_steps"] == []
        assert status["total_conditions"] == 0

    def test_ingest_step(self, tmp_path):
        (tmp_path / StepFiles.INGESTED_DATA.value).write_text("data")
        status = get_experiment_status(tmp_path)
        assert "ingest" in status["completed_steps"]

    def test_filter_step(self, tmp_path):
        (tmp_path / StepFiles.FILTERED_DATA.value).write_text("data")
        status = get_experiment_status(tmp_path)
        assert "filter" in status["completed_steps"]

    def test_average_step(self, tmp_path):
        (tmp_path / StepFiles.AVERAGED_DATA.value).write_text("data")
        status = get_experiment_status(tmp_path)
        assert "average" in status["completed_steps"]

    def test_complete_step(self, tmp_path):
        (tmp_path / StepFiles.MIN_TEMPERATURES_DATA.value).write_text("data")
        status = get_experiment_status(tmp_path)
        assert "complete" in status["completed_steps"]

    def test_all_steps(self, tmp_path):
        for sf in [
            StepFiles.INGESTED_DATA,
            StepFiles.FILTERED_DATA,
            StepFiles.AVERAGED_DATA,
            StepFiles.MIN_TEMPERATURES_DATA,
        ]:
            (tmp_path / sf.value).write_text("data")
        status = get_experiment_status(tmp_path)
        assert status["completed_steps"] == ["ingest", "filter", "average", "complete"]

    def test_experiment_info_json(self, tmp_path):
        info = {"cond1": {}, "cond2": {}, "cond3": {}}
        (tmp_path / "experiment_info.json").write_text(json.dumps(info))
        status = get_experiment_status(tmp_path)
        assert status["total_conditions"] == 3


# ──────────────────────────────────────────────────────────────────────
# constants.py
# ──────────────────────────────────────────────────────────────────────
from instawell.dash_app.constants import (
    CACHE_KEY_FORMAT,
    FIGURE_BUTTON_MAP,
    FIGURE_STEP_FILES,
    STEP_ICONS,
)


class TestConstants:
    """Verify internal consistency of constant mappings."""

    def test_all_button_map_values_in_step_files(self):
        """Every figure type referenced by a button must have a StepFiles mapping."""
        for btn_id, fig_type in FIGURE_BUTTON_MAP.items():
            assert fig_type in FIGURE_STEP_FILES, (
                f"Button {btn_id!r} maps to {fig_type!r} which is missing from FIGURE_STEP_FILES"
            )

    def test_step_files_values_are_stepfiles_enum(self):
        """Every value in FIGURE_STEP_FILES should be a StepFiles enum member."""
        for fig_type, sf in FIGURE_STEP_FILES.items():
            assert isinstance(sf, StepFiles), (
                f"FIGURE_STEP_FILES[{fig_type!r}] = {sf!r} is not a StepFiles member"
            )

    def test_step_icons_keys_match_known_steps(self):
        """STEP_ICONS keys should be recognized pipeline steps."""
        known_steps = {"ingest", "filter", "average", "complete"}
        assert set(STEP_ICONS.keys()) == known_steps

    def test_cache_key_format_has_placeholders(self):
        """CACHE_KEY_FORMAT should accept session_id and filename."""
        result = CACHE_KEY_FORMAT.format(session_id="sess123", filename="data.csv")
        assert "sess123" in result
        assert "data.csv" in result


# ──────────────────────────────────────────────────────────────────────
# designer.py
# ──────────────────────────────────────────────────────────────────────
from instawell.dash_app.designer import (
    PLATE_TYPES,
    get_row_labels,
    infer_plate_from_raw,
)


class TestGetRowLabels:
    """Tests for get_row_labels()."""

    def test_8_rows(self):
        assert get_row_labels(8) == ["A", "B", "C", "D", "E", "F", "G", "H"]

    def test_16_rows(self):
        labels = get_row_labels(16)
        assert len(labels) == 16
        assert labels[0] == "A"
        assert labels[-1] == "P"

    def test_zero_rows(self):
        assert get_row_labels(0) == []

    def test_single_row(self):
        assert get_row_labels(1) == ["A"]


class TestInferPlateFromRaw:
    """Tests for infer_plate_from_raw()."""

    def test_96_well_plate(self):
        cols = ["Temperature"] + [f"{r}{c}" for r in "ABCDEFGH" for c in range(1, 13)]
        df = pd.DataFrame({col: [0.0] for col in cols})
        plate_type, rows, cols_count, wells = infer_plate_from_raw(df)
        assert plate_type == "96"
        assert rows == 8
        assert cols_count == 12
        assert len(wells) == 96

    def test_small_plate_inferred_as_96(self):
        df = pd.DataFrame({"Temperature": [25.0], "A1": [100.0], "A2": [101.0], "B1": [200.0]})
        plate_type, _rows, _cols_count, wells = infer_plate_from_raw(df)
        assert plate_type == "96"
        assert set(wells) == {"A1", "A2", "B1"}

    def test_384_well_plate(self):
        # If we have wells beyond H12, it must be 384
        cols = ["Temperature", "A1", "P24"]
        df = pd.DataFrame({col: [0.0] for col in cols})
        plate_type, rows, cols_count, _wells = infer_plate_from_raw(df)
        assert plate_type == "384"
        assert rows == 16
        assert cols_count == 24

    def test_wells_are_sorted_and_unique(self):
        df = pd.DataFrame({"Temperature": [25.0], "B2": [1.0], "A1": [2.0], "B2 ": [3.0]})
        _, _, _, wells = infer_plate_from_raw(df)
        assert wells == sorted(set(wells))


class TestPlateTypes:
    """Sanity checks for PLATE_TYPES constant."""

    def test_96_dimensions(self):
        assert PLATE_TYPES["96"] == (8, 12)

    def test_384_dimensions(self):
        assert PLATE_TYPES["384"] == (16, 24)


# ──────────────────────────────────────────────────────────────────────
# callbacks/_helpers.py
# ──────────────────────────────────────────────────────────────────────
from instawell.dash_app.callbacks._helpers import _handle_upload, _refresh_keep


class TestRefreshKeep:
    """Tests for _refresh_keep() helper."""

    def test_returns_correct_length(self):
        result = _refresh_keep(["opt1"], "val1")
        assert len(result) == 16

    def test_first_two_are_passed_through(self):
        result = _refresh_keep(["opt1", "opt2"], "selected")
        assert result[0] == ["opt1", "opt2"]
        assert result[1] == "selected"

    def test_remaining_are_no_update(self):
        from dash import no_update

        result = _refresh_keep([], None)
        for item in result[2:]:
            assert item is no_update


class TestHandleUpload:
    """Tests for _handle_upload() helper."""

    def _make_csv_contents(self, csv_text: str) -> str:
        b64 = base64.b64encode(csv_text.encode()).decode()
        return f"data:text/csv;base64,{b64}"

    def test_none_contents_returns_empty(self):
        status, key = _handle_upload(None, "f.csv", "sess", MagicMock(), lambda df: None)
        assert status == ""
        assert key is None

    def test_successful_upload(self):
        cache = MagicMock()
        csv = "Temperature,A1\n25.0,100\n"
        status, key = _handle_upload(
            self._make_csv_contents(csv), "raw.csv", "sess123", cache, lambda df: None
        )
        assert key == "sess123_raw.csv"
        assert "raw.csv" in status.children[1]
        cache.set.assert_called_once()

    def test_validator_rejects(self):
        cache = MagicMock()
        csv = "col1\nval\n"
        status, key = _handle_upload(
            self._make_csv_contents(csv), "bad.csv", "sess", cache, lambda df: "Nope"
        )
        assert key is None
        assert "Nope" in status.children
        cache.set.assert_not_called()

    def test_non_csv_file(self):
        cache = MagicMock()
        b64 = base64.b64encode(b"binary").decode()
        contents = f"data:application/octet-stream;base64,{b64}"
        status, key = _handle_upload(contents, "data.xlsx", "sess", cache, lambda df: None)
        assert key is None
        assert "text-danger" in status.className

    def test_cache_error(self):
        cache = MagicMock()
        cache.set.side_effect = RuntimeError("cache full")
        csv = "Temperature,A1\n25.0,100\n"
        status, key = _handle_upload(
            self._make_csv_contents(csv), "raw.csv", "sess", cache, lambda df: None
        )
        assert key is None
        assert "caching" in status.children.lower() or "cache" in str(status.children).lower()

    def test_none_session_generates_uuid(self):
        cache = MagicMock()
        csv = "Temperature,A1\n25.0,100\n"
        _status, key = _handle_upload(
            self._make_csv_contents(csv), "raw.csv", None, cache, lambda df: None
        )
        assert key is not None
        assert "_raw.csv" in key
        # UUID is 36 chars
        session_part = key.replace("_raw.csv", "")
        assert len(session_part) == 36
