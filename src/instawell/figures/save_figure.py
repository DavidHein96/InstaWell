import logging
from pathlib import Path

import plotly.graph_objects as go

from instawell.core.exp_context import ExperimentContext
from instawell.core.steps import StepFiles
from instawell.utils.utils import slugify

logger = logging.getLogger(__name__)


def save_figure(
    ctx: ExperimentContext,
    fig: go.Figure,
    group_keys: dict[str, str],
    plot_dir_enum: StepFiles,
    html_include_plotlyjs: str = "cdn",
) -> None:
    """
    Saves a Plotly figure to the appropriate experiment subdirectory.

    Args:
        ctx: The experiment context.
        fig: The Plotly figure object to save.
        group_keys: A dictionary of the keys that define the group for this plot
                    (e.g., {'ligand': 'ATP', 'protein': 'ABC'}). Used to create a filename.
        plot_dir_enum: The StepFiles enum member for the plot directory
                       (e.g., StepFiles.RAW_PLOTS).
        html_include_plotlyjs: How to include Plotly.js in the HTML file.
                               Defaults to "cdn".
    """
    # Create a slug from the group keys for a safe filename
    slug = slugify("__".join(f"{k}_{v}" for k, v in group_keys.items()))

    # Get the target directory from the StepFiles enum
    plot_dir = ctx.experiment_dir / plot_dir_enum.value
    plot_dir.mkdir(parents=True, exist_ok=True)

    # Construct the full path for the HTML file
    html_path = plot_dir / f"{slug}.html"

    # Save the figure
    try:
        fig.write_html(html_path, include_plotlyjs=html_include_plotlyjs)
        logger.info("Saved figure to %s", html_path)
    except Exception as e:
        logger.error("Failed to save figure to %s: %s", html_path, e)
