"""
UI layout components for the Dash app.
"""

import dash_bootstrap_components as dbc
from dash import dcc, html

from .designer import designer_card


def navbar():
    """Create navigation bar."""
    return dbc.Navbar(
        dbc.Container(
            [
                dbc.Row(
                    [
                        dbc.Col(
                            html.A(
                                dbc.Row(
                                    [
                                        dbc.Col(
                                            html.Img(
                                                src="/assets/instawell-icon-256.png",
                                                style={"height": "32px", "width": "32px"},
                                                alt="InstaWell logo",
                                            )
                                        ),
                                        dbc.Col(
                                            dbc.NavbarBrand("InstaWell", className="ms-2")
                                        ),
                                    ],
                                    align="center",
                                    className="g-0",
                                ),
                                href="/",
                                style={"textDecoration": "none"},
                            ),
                            width="auto",
                        ),
                        dbc.Col(
                            html.Div(
                                "Differential Scanning Fluorimetry Analysis",
                                className="text-muted small",
                            ),
                            className="ms-3",
                        ),
                    ],
                    align="center",
                ),
            ],
            fluid=True,
        ),
        color="dark",
        dark=True,
        className="mb-4",
    )


def experiment_browser_card():
    """Create experiment browser section."""
    return dbc.Card(
        [
            dbc.CardHeader(
                html.H5(
                    [html.I(className="fa fa-folder-open me-2"), "Existing Experiments"],
                    className="mb-0",
                )
            ),
            dbc.CardBody(
                [
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    dcc.Dropdown(
                                        id="experiment-dropdown",
                                        placeholder="Select an experiment to view...",
                                        className="mb-2",
                                    ),
                                    dbc.ButtonGroup(
                                        [
                                            dbc.Button(
                                                [html.I(className="fa fa-sync me-2"), "Refresh"],
                                                id="refresh-experiments-btn",
                                                color="secondary",
                                                size="sm",
                                            ),
                                            dbc.Button(
                                                [html.I(className="fa fa-times me-2"), "Clear"],
                                                id="clear-experiment-btn",
                                                color="warning",
                                                size="sm",
                                                outline=False,
                                            ),
                                        ],
                                        size="sm",
                                    ),
                                ],
                                width=12,
                                md=8,
                            ),
                            dbc.Col(
                                html.Div(id="experiment-info", className="small text-muted"),
                                width=12,
                                md=4,
                            ),
                        ]
                    ),
                ]
            ),
        ],
        className="mb-4",
    )


def well_filter_card():
    """Create well filtering section."""
    return dbc.Card(
        [
            dbc.CardHeader(
                html.H5(
                    [html.I(className="fa fa-filter me-2"), "Filter Wells (Optional)"],
                    className="mb-0",
                )
            ),
            dbc.CardBody(
                [
                    html.P(
                        "Select wells to exclude from analysis (e.g., wells with errors, contamination)",
                        className="text-muted small mb-3",
                    ),
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    html.Div(
                                        id="well-filter-content",
                                        children=[
                                            html.Div(
                                                [
                                                    html.I(
                                                        className="fa fa-info-circle fa-2x text-muted mb-2"
                                                    ),
                                                    html.P(
                                                        "Upload data files to see available wells",
                                                        className="text-muted",
                                                    ),
                                                ],
                                                className="text-center py-4",
                                            )
                                        ],
                                    ),
                                ],
                                width=12,
                            ),
                        ]
                    ),
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    html.Div(
                                        id="filter-summary",
                                        className="small text-muted mt-2",
                                    ),
                                ],
                                width=12,
                            ),
                        ]
                    ),
                ]
            ),
        ],
        className="mb-4",
        id="well-filter-card",
        style={"display": "none"},  # Hidden until data is uploaded
    )


def upload_pipeline_card():
    """Create upload and pipeline configuration section."""
    return dbc.Card(
        [
            dbc.CardHeader(
                dbc.Row(
                    [
                        dbc.Col(
                            html.H5(
                                [html.I(className="fa fa-upload me-2"), "New Experiment"],
                                className="mb-0",
                            ),
                            width="auto",
                        ),
                        dbc.Col(
                            dbc.Button(
                                "Hide New Experiment",
                                id="new-experiment-toggle-btn",
                                color="secondary",
                                size="sm",
                                outline=True,
                            ),
                            className="text-end",
                        ),
                    ],
                    align="center",
                )
            ),
            dbc.Collapse(
                dbc.CardBody(
                [
                    # Upload section
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    html.Label("Raw Data CSV", className="fw-bold"),
                                    dcc.Upload(
                                        id="upload-raw",
                                        children=html.Div(
                                            [
                                                html.I(className="fa fa-cloud-upload me-2"),
                                                "Drag and Drop or Click to Select Raw Data",
                                            ]
                                        ),
                                        style={
                                            "width": "100%",
                                            "height": "60px",
                                            "lineHeight": "60px",
                                            "borderWidth": "2px",
                                            "borderStyle": "dashed",
                                            "borderRadius": "5px",
                                            "textAlign": "center",
                                            "cursor": "pointer",
                                        },
                                        multiple=False,
                                    ),
                                    html.Div(id="raw-upload-status", className="small mt-1"),
                                ],
                                width=12,
                                md=6,
                                className="mb-3",
                            ),
                            dbc.Col(
                                [
                                    html.Label("Layout CSV", className="fw-bold"),
                                    dcc.Upload(
                                        id="upload-layout",
                                        children=html.Div(
                                            [
                                                html.I(className="fa fa-cloud-upload me-2"),
                                                "Drag and Drop or Click to Select Layout",
                                            ]
                                        ),
                                        style={
                                            "width": "100%",
                                            "height": "60px",
                                            "lineHeight": "60px",
                                            "borderWidth": "2px",
                                            "borderStyle": "dashed",
                                            "borderRadius": "5px",
                                            "textAlign": "center",
                                            "cursor": "pointer",
                                        },
                                        multiple=False,
                                    ),
                                    html.Div(id="layout-upload-status", className="small mt-1"),
                                ],
                                width=12,
                                md=6,
                                className="mb-3",
                            ),
                        ]
                    ),
                    html.Hr(),
                    # Configuration section
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    html.Label("Experiment Name", className="fw-bold"),
                                    dbc.Input(
                                        id="experiment-name-input",
                                        placeholder="e.g., TSA_001",
                                        type="text",
                                    ),
                                ],
                                width=12,
                                md=4,
                                className="mb-3",
                            ),
                            dbc.Col(
                                [
                                    html.Label("Condition Separator", className="fw-bold"),
                                    dbc.Input(
                                        id="separator-input",
                                        placeholder="|",
                                        value="|",
                                        type="text",
                                        maxLength=1,
                                    ),
                                ],
                                width=12,
                                md=2,
                                className="mb-3",
                            ),
                            dbc.Col(
                                [
                                    html.Label("Missing Condition Placeholder", className="fw-bold"),
                                    dbc.Input(
                                        id="empty-placeholder-input",
                                        placeholder="^",
                                        value="^",
                                        type="text",
                                        maxLength=1,
                                    ),
                                ],
                                width=12,
                                md=2,
                                className="mb-3",
                            ),
                            dbc.Col(
                                [
                                    html.Label("Temperature Column", className="fw-bold"),
                                    dbc.Input(
                                        id="temp-col-input",
                                        placeholder="Temperature",
                                        value="Temperature",
                                        type="text",
                                    ),
                                ],
                                width=12,
                                md=4,
                                className="mb-3",
                            ),
                        ]
                    ),
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    html.Label("Field Order", className="fw-bold"),
                                    dbc.Input(
                                        id="fields-input",
                                        placeholder="concentration,ligand,protein,buffer",
                                        value="concentration,ligand,protein,buffer",
                                        type="text",
                                    ),
                                    html.Small(
                                        "Comma-separated field order for parsing layout",
                                        className="text-muted",
                                    ),
                                ],
                                width=12,
                                className="mb-3",
                            ),
                        ]
                    ),
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    html.Label("Non-Protein Control Marker", className="fw-bold"),
                                    dbc.Input(
                                        id="npc-input",
                                        placeholder="NPC",
                                        value="NPC",
                                        type="text",
                                    ),
                                ],
                                width=12,
                                md=4,
                                className="mb-3",
                            ),
                        ]
                    ),
                    # Buttons for two-stage workflow
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    dbc.Button(
                                        [
                                            html.I(className="fa fa-clipboard-check me-2"),
                                            "Validate Layout",
                                        ],
                                        id="validate-layout-btn",
                                        color="secondary",
                                        size="lg",
                                        disabled=True,
                                        className="me-2",
                                    ),
                                    dbc.Button(
                                        [
                                            html.I(className="fa fa-cog me-2"),
                                            "Setup & View Raw Data",
                                        ],
                                        id="setup-ingest-btn",
                                        color="info",
                                        size="lg",
                                        disabled=True,
                                        className="me-2",
                                    ),
                                    dbc.Button(
                                        [
                                            html.I(className="fa fa-play me-2"),
                                            "Run Full Pipeline",
                                        ],
                                        id="run-pipeline-btn",
                                        color="primary",
                                        size="lg",
                                        disabled=True,
                                    ),
                                    html.Div(id="layout-validation-status", className="mt-2"),
                                    html.Div(id="setup-status", className="mt-2"),
                                    html.Div(id="pipeline-status", className="mt-2"),
                                ],
                                width=12,
                            ),
                        ]
                    ),
                ]
                ),
                id="new-experiment-collapse",
                is_open=True,
            ),
        ],
        className="mb-4",
    )


def figures_card():
    """Create figure display section."""
    return dbc.Card(
        [
            dbc.CardHeader(
                dbc.Row(
                    [
                        dbc.Col(
                            html.H5(
                                [html.I(className="fa fa-chart-line me-2"), "Figures"],
                                className="mb-0",
                            ),
                            width="auto",
                        ),
                        dbc.Col(
                            dbc.ButtonGroup(
                                [
                                    dbc.Button(
                                        "Raw",
                                        id="fig-btn-raw",
                                        color="primary",
                                        size="sm",
                                        outline=True,
                                    ),
                                    dbc.Button(
                                        "Averaged",
                                        id="fig-btn-averaged",
                                        color="primary",
                                        size="sm",
                                        outline=True,
                                    ),
                                    dbc.Button(
                                        "BG Sub",
                                        id="fig-btn-bgsub",
                                        color="primary",
                                        size="sm",
                                        outline=True,
                                    ),
                                    dbc.Button(
                                        "Normalized",
                                        id="fig-btn-minmax",
                                        color="primary",
                                        size="sm",
                                        outline=True,
                                    ),
                                    dbc.Button(
                                        "Derivative",
                                        id="fig-btn-deriv",
                                        color="primary",
                                        size="sm",
                                        outline=True,
                                    ),
                                    dbc.Button(
                                        "Tm",
                                        id="fig-btn-tm",
                                        color="primary",
                                        size="sm",
                                        outline=True,
                                    ),
                                ],
                                size="sm",
                            ),
                            className="text-end",
                        ),
                    ],
                    align="center",
                )
            ),
            dbc.CardBody(
                [
                    # Figure navigation controls
                    html.Div(
                        [
                            dbc.Row(
                                [
                                    dbc.Col(
                                        dbc.ButtonGroup(
                                            [
                                                dbc.Button(
                                                    [html.I(className="fa fa-chevron-left")],
                                                    id="fig-prev-btn",
                                                    color="secondary",
                                                    size="sm",
                                                    outline=True,
                                                ),
                                                dbc.Button(
                                                    [html.I(className="fa fa-chevron-right")],
                                                    id="fig-next-btn",
                                                    color="secondary",
                                                    size="sm",
                                                    outline=True,
                                                ),
                                            ],
                                            className="me-3",
                                        ),
                                        width="auto",
                                    ),
                                    dbc.Col(
                                        dcc.Dropdown(
                                            id="figure-selector-dropdown",
                                            placeholder="Select a figure...",
                                            clearable=False,
                                        ),
                                        width=True,
                                    ),
                                    dbc.Col(
                                        html.Div(
                                            id="figure-counter",
                                            className="text-muted small text-end",
                                        ),
                                        width="auto",
                                    ),
                                ],
                                align="center",
                                className="mb-3",
                            ),
                        ],
                        id="figure-nav-controls",
                        style={"display": "none"},  # Hidden until figures are loaded
                    ),
                    # Figure display area
                    dcc.Loading(
                        id="loading-figures",
                        type="default",
                        children=html.Div(
                            id="figures-container",
                            children=[
                                html.Div(
                                    [
                                        html.I(
                                            className="fa fa-info-circle fa-3x text-muted mb-3"
                                        ),
                                        html.P(
                                            "Select an experiment or upload data to view figures",
                                            className="text-muted",
                                        ),
                                    ],
                                    className="text-center py-5",
                                )
                            ],
                        ),
                    ),
                ]
            ),
        ]
    )


def create_layout():
    """Create the main application layout."""
    return dbc.Container(
        [
            # Store components for state management
            dcc.Store(id="session-id", storage_type="session"),
            # Stores for uploaded data references (now storing keys, not data)
            dcc.Store(id="raw-data-store", storage_type="session"),
            dcc.Store(id="layout-data-store", storage_type="session"),
            dcc.Store(id="current-experiment-store"),
            dcc.Store(id="filtered-wells-store", data=[]),  # Store filtered wells
            dcc.Store(id="setup-complete-store", data=False),  # Track if setup/ingest done
            # Stores for figure navigation
            dcc.Store(id="figures-store"),  # Store all figures and their titles
            dcc.Store(id="current-figure-index", data=0),  # Track current figure index
            # Store for well grid selection
            dcc.Store(id="selected-wells-grid", data=[]),  # Track selected wells in grid
            # UI components
            navbar(),
            # Currently viewing banner (shows when experiment is loaded)
            html.Div(id="current-experiment-banner"),
            experiment_browser_card(),
            designer_card(),  # Layout designer
            upload_pipeline_card(),
            well_filter_card(),  # Well filtering
            figures_card(),
        ],
        fluid=True,
        className="py-3",
    )
