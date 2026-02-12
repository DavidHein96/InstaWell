"""
Layout validation callbacks.
"""

import logging

import pandas as pd
from dash import Input, Output, State, html
from dash.exceptions import PreventUpdate

from instawell.core.parser import parse_condition_string

from ..utils import validate_separator_placeholder

logger = logging.getLogger("instawell.dash_app.validation")


def register_validation_callbacks(app, cache):
    """Register layout validation callbacks."""

    @app.callback(
        Output("layout-validation-status", "children"),
        Input("validate-layout-btn", "n_clicks"),
        State("raw-data-store", "data"),
        State("layout-data-store", "data"),
        State("separator-input", "value"),
        State("fields-input", "value"),
        State("empty-placeholder-input", "value"),
        State("temp-col-input", "value"),
        prevent_initial_call=True,
    )
    def validate_layout(
        n_clicks,
        raw_data_key,
        layout_data_key,
        separator,
        fields_str,
        empty_placeholder,
        temperature_column,
    ):
        """Validate uploaded raw/layout files against provided parsing settings."""
        if not n_clicks:
            raise PreventUpdate

        if not raw_data_key or not layout_data_key:
            return html.Div(
                [
                    html.I(className="fa fa-exclamation-triangle me-2"),
                    "Upload both raw and layout CSV files before validating.",
                ],
                className="alert alert-warning",
            )

        try:
            fields = tuple(f.strip() for f in fields_str.split(",") if f.strip())
            if not fields:
                raise ValueError("Field order cannot be empty.")

            separator, empty_placeholder = validate_separator_placeholder(
                separator, empty_placeholder
            )

            layout_df = cache.get(layout_data_key)
            raw_df = cache.get(raw_data_key)

            if layout_df is None or raw_df is None:
                return html.Div(
                    "Uploaded data has expired from cache. Please upload again.",
                    className="alert alert-danger",
                )

            temp_col = (temperature_column or "Temperature").strip()
            if temp_col not in raw_df.columns:
                match = next(
                    (c for c in raw_df.columns if c.lower() == temp_col.lower()),
                    None,
                )
                if match:
                    temp_col = match
                else:
                    raise ValueError(
                        f"Raw data is missing temperature column '{temp_col}'."
                    )

            well_cols = [c for c in layout_df.columns if c.lower().startswith("well")]
            if not well_cols:
                raise ValueError(
                    "Layout file must contain a column starting with 'Well'."
                )
            well_col = well_cols[0]

            mask = separator.join(empty_placeholder for _ in fields)
            errors: list[str] = []
            unique_conditions = set()

            for _, row in layout_df.iterrows():
                well_label = str(row[well_col]).strip()
                for col in layout_df.columns:
                    if col == well_col:
                        continue
                    val = row[col]
                    if pd.isna(val):
                        continue
                    condition_str = str(val).strip()
                    if not condition_str or condition_str == mask:
                        continue
                    try:
                        parse_condition_string(
                            condition_str,
                            delimiter=separator,
                            fields=fields,
                        )
                        unique_conditions.add(condition_str)
                    except ValueError as exc:
                        errors.append(f"{well_label}{col}: {exc}")

            if errors:
                preview = html.Ul(
                    [html.Li(err) for err in errors[:5]],
                    className="mb-0",
                )
                children = [
                    html.Div(
                        [
                            html.I(className="fa fa-exclamation-triangle me-2"),
                            "Layout validation failed. Fix the issues below:",
                        ],
                        className="alert alert-danger mb-2",
                    ),
                    preview,
                ]
                max_preview = 5
                if len(errors) > max_preview:
                    children.append(
                        html.Small(
                            f"+{len(errors) - max_preview} more issues",
                            className="text-muted",
                        )
                    )
                return html.Div(children)

            num_wells = len([c for c in raw_df.columns if c != temp_col])
            return html.Div(
                [
                    html.I(className="fa fa-check-circle me-2"),
                    f"Validation successful! Parsed {len(unique_conditions)} conditions across {num_wells} wells.",
                ],
                className="alert alert-success",
            )
        except Exception as exc:
            return html.Div(
                [
                    html.I(className="fa fa-exclamation-triangle me-2"),
                    f"Validation error: {exc}",
                ],
                className="alert alert-danger",
            )
