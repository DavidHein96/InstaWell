# Development & Documentation

![InstaWell icon](assets/instawell-icon-256.png){: style="width:90px"}

This project ships both a Python package and a Dash application. The following sections explain how to set up a development environment, run tests, and preview the MkDocs site introduced here.

## Environment

We recommend [uv](https://docs.astral.sh/uv/) or a virtual environment:

```bash
uv sync
# or
python -m venv .venv
source .venv/bin/activate
pip install -e ".[notebook,dash,dev]"
```

## Running Tests

```bash
pytest
```

Use markers (`unit`, `integration`) to narrow the scope:

```bash
pytest -m unit
```

## Formatting & Linting

```bash
ruff check src tests
mypy src
```

Pre-commit hooks are configured; run `pre-commit install` to enable them.

## Building Docs

The MkDocs site lives in the root `mkdocs.yml` and the `docs/` directory. Install the documentation extra and serve locally:

```bash
pip install 'instawell[docs]'
mkdocs serve
```

This spins up a preview at `http://127.0.0.1:8000`. To produce static HTML, run:

```bash
mkdocs build
```

## Contributing Documentation

- Keep README concise—link to the appropriate MkDocs page for longer guides.
- Use relative links (`[Pipeline](pipeline.md)`) so that Markdown works both locally and in the hosted site.
- Store shared assets in `docs/assets/`.
- After editing docs, run `mkdocs serve` and follow the console output for broken links or syntax errors.
