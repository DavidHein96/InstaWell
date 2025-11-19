# instawell/figures/notebook.py
from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from functools import wraps
from typing import Callable, Union

import ipywidgets as W
import plotly.graph_objects as go
from IPython.display import clear_output, display
from typing_extensions import ParamSpec

from instawell.figures.min_temp_fig import min_temp_figure_generator
from instawell.figures.processed_data_fig import processed_figure_generator
from instawell.figures.raw_data_fig import raw_figure_generator

FiguresLike = Union[Sequence[go.Figure], Iterable[go.Figure], Iterator[go.Figure]]
P = ParamSpec("P")


def _extract_title(fig: go.Figure, default: str) -> str:
    # Prefer dict-like access (stable for typing)
    try:
        t = fig.layout.to_plotly_json().get("title", None)
        if isinstance(t, dict):
            txt = t.get("text")
            if txt:
                return str(txt)
        elif isinstance(t, str):
            return t
    except Exception:
        pass

    # Fallbacks for odd cases
    t_attr = getattr(fig.layout, "title", None)
    if isinstance(t_attr, str) and t_attr:
        return t_attr
    txt = getattr(t_attr, "text", None) if t_attr is not None else None
    return str(txt) if txt else default


def widgetize_generator(gen_func: Callable[P, FiguresLike]) -> Callable[P, W.VBox]:
    """
    Wrap a figure-generator to return a widget, preserving the original
    signature & docstring (so help() / Shift-Tab work in notebooks).

    Extra keyword controls (intercepted, not passed to gen_func):
      - show: bool = False
      - show_help: bool = False
    """

    @wraps(gen_func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> W.VBox:
        # Pull widget-only kwargs without polluting gen_func call signature
        show = bool(kwargs.pop("show", False))
        show_help = bool(kwargs.pop("show_help", False))

        figs: FiguresLike = gen_func(*args, **kwargs)
        ui = figures_widget(figs, show=False)

        if show_help and (doc := (gen_func.__doc__ or "").strip()):
            help_box = W.Accordion(
                children=[W.HTML(f"<pre style='white-space:pre-wrap'>{doc}</pre>")]
            )
            help_box.set_title(0, f"Help: {gen_func.__name__}")
            ui = W.VBox([help_box, ui])

        if show:
            display(ui)
        return ui

    return wrapper


def figures_widget(figs: FiguresLike, show: bool = False) -> W.VBox:
    """
    Build a Jupyter widget to browse Plotly figures.

    Parameters
    ----------
    figs : Sequence[go.Figure] | Iterable[go.Figure] | Iterator[go.Figure]
        A list or generator of Plotly figures.
    show : bool, optional
        If True, display() the widget immediately. Returns the widget either way.

    Returns
    -------
    ipywidgets.VBox
        An interactive browser for the figures (slider + dropdown + prev/next).
    """
    # materialize if needed (generators/iterables)
    if not isinstance(figs, (list, tuple)):
        figs = list(figs)

    if not figs:
        raise ValueError("No figures to display.")

    titles: list[str] = []
    for i, f in enumerate(figs, start=1):
        titles.append(_extract_title(f, default=f"Figure {i}"))

    # controls
    idx = W.IntSlider(min=0, max=len(figs) - 1, step=1, value=0, description="Index")
    dd = W.Dropdown(options=[(t, i) for i, t in enumerate(titles)], value=0, description="Select")
    prev_btn = W.Button(icon="chevron-left", tooltip="Previous")
    next_btn = W.Button(icon="chevron-right", tooltip="Next")
    out = W.Output()

    def render(i: int) -> None:
        with out:
            clear_output(wait=True)
            figs[i].show()

    def on_idx_change(change):
        if change["name"] == "value":
            dd.value = change["new"]
            render(change["new"])

    def on_dd_change(change):
        if change["name"] == "value":
            idx.value = change["new"]  # triggers render via slider handler

    def on_prev(_):
        if idx.value > idx.min:
            idx.value -= 1

    def on_next(_):
        if idx.value < idx.max:
            idx.value += 1

    idx.observe(on_idx_change, names="value")
    dd.observe(on_dd_change, names="value")
    prev_btn.on_click(on_prev)
    next_btn.on_click(on_next)

    # first render
    render(0)

    ui = W.VBox([W.HBox([prev_btn, next_btn]), idx, dd, out])

    if show:
        display(ui)
    return ui


raw_figures_widget = widgetize_generator(raw_figure_generator)
processed_figures_widget = widgetize_generator(processed_figure_generator)
min_temp_figures_widget = widgetize_generator(min_temp_figure_generator)
