from typing import Dict, List

import dash_bootstrap_components as dbc
from dash import dcc, html

from .config import TITLE


def navbar(num_conditions: int):
    return dbc.Navbar(
        [
            dbc.NavbarBrand(TITLE, className="ms-2"),
            dbc.Nav(
                [dbc.Badge(f"{num_conditions} conditions", color="info", className="ms-2")],
                className="ms-auto",
                navbar=True,
            ),
        ],
        color="dark",
        dark=True,
        className="mb-3 rounded",
    )


def controls(plot_options: List[Dict]):
    return dbc.Card(
        dbc.Stack(
            [
                html.H4("Select Conditions"),
                dcc.Dropdown(
                    id="plot-selector",
                    options=plot_options,
                    value=([plot_options[0]["value"]] if plot_options else []),
                    multi=True,
                    placeholder="Pick one or more...",
                    className="mb-2",
                ),
                dbc.Accordion(
                    id="replicate-accordion",
                    start_collapsed=True,
                    always_open=False,
                    className="mb-2",
                ),
                html.H5("Processing"),
                dbc.Checklist(
                    id="bg-subtract-toggle",
                    options=[{"label": " Background subtraction (NPC)", "value": "BG"}],
                    value=[],
                    switch=True,
                    className="mb-1",
                ),
                dbc.Checklist(
                    id="normalize-toggle",
                    options=[{"label": " Normalize average to 0–1 (secondary Y)", "value": "NORM"}],
                    value=[],
                    switch=True,
                    className="mb-1",
                ),
                dbc.Checklist(
                    id="derivative-toggle",
                    options=[{"label": " Plot -dY/dT (normalized, secondary Y)", "value": "DERIV"}],
                    value=[],
                    switch=True,
                    className="mb-3",
                ),
                html.H5("Downloads"),
                dbc.Button(
                    "Processed Figure (HTML)",
                    id="btn-download-avg-fig",
                    className="me-2 mb-2",
                    color="primary",
                ),
                dbc.Button(
                    "Processed Data (CSV)",
                    id="btn-download-avg-csv",
                    className="me-2 mb-2",
                    color="secondary",
                ),
                dbc.Button(
                    "Metadata (CSV)",
                    id="btn-download-metadata-csv",
                    className="mb-2",
                    color="secondary",
                ),
                dcc.Download(id="download-avg-fig-html"),
                dcc.Download(id="download-avg-data-csv"),
                dcc.Download(id="download-metadata-csv"),
            ],
            gap=2,
        ),
        body=True,
        className="shadow-sm",
    )


def plot_card():
    return dbc.Card(
        [
            dbc.CardHeader(
                [
                    html.Div(
                        [
                            html.H4("Interactive Multi-Plot Viewer", className="m-0"),
                            html.Small(
                                "Averaging, background subtraction, normalization & derivative",
                                className="text-muted",
                            ),
                        ]
                    )
                ]
            ),
            dbc.CardBody(dcc.Graph(id="dynamic-subplot-graph", style={"height": "84vh"})),
        ],
        className="shadow-sm",
    )


def dataset_picker(options: List[Dict], active: str):
    return dbc.Card(
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.Label("Dataset", className="fw-bold"),
                        dcc.Dropdown(
                            id="dataset-select", options=options, value=active, clearable=False
                        ),
                    ],
                    md=6,
                ),
                dbc.Col(
                    [
                        html.Label("Upload new dataset", className="fw-bold"),
                        dbc.Input(
                            id="dataset-name",
                            placeholder="Name (e.g., 2025-10-TSV-runA)",
                            className="mb-2",
                        ),
                        dbc.Row(
                            [
                                dbc.Col(
                                    dcc.Upload(
                                        id="upload-layout",
                                        children=html.Div(
                                            [
                                                html.Span("📄 layout.csv", className="upload-filename"),
                                                html.Span(
                                                    "Drag & drop or click to choose layout",
                                                    className="upload-help",
                                                ),
                                            ]
                                        ),
                                        multiple=False,
                                        accept=".csv",
                                        className="upload-zone",
                                    ),
                                    md=6,
                                ),
                                dbc.Col(
                                    dcc.Upload(
                                        id="upload-raw",
                                        children=html.Div(
                                            [
                                                html.Span("📈 raw.csv", className="upload-filename"),
                                                html.Span(
                                                    "Drag & drop or click to choose raw readings",
                                                    className="upload-help",
                                                ),
                                            ]
                                        ),
                                        multiple=False,
                                        accept=".csv",
                                        className="upload-zone",
                                    ),
                                    md=6,
                                ),
                            ],
                            className="g-2",
                        ),
                        dbc.Button(
                            "Add dataset", id="btn-add-dataset", color="success", className="mt-2"
                        ),
                        html.Div(id="upload-status", className="text-muted mt-2"),
                        html.Div(
                            [
                                html.A(
                                    "Download layout template",
                                    id="download-layout-template",
                                    href="#",
                                    className="me-3",
                                ),
                                html.A(
                                    "Download raw template", id="download-raw-template", href="#"
                                ),
                            ],
                            className="mt-2 small",
                        ),
                    ],
                    md=6,
                ),
            ],
            className="g-3",
        ),
        body=True,
        className="shadow-sm",
    )
