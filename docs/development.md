# Development & Documentation


This project ships both a Python package and a Dash application. The following sections explain how to set up a development environment, run tests, and release new versions.

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
uv run pytest
```

Use markers (`unit`, `integration`) to narrow the scope:

```bash
uv run pytest -m unit
```

Some integration tests require real TSA data files that are not committed to the repository. These are skipped automatically in CI. To run the full suite locally (including real-data tests), ensure `tests/test_data/TSA_042/` and `tests/test_data/TSA_067/` are populated.

See the [Fuzz Testing](fuzz_testing.md) page for details on the synthetic data test suite.

## Linting & Type Checking

```bash
uv run ruff check src tests
uv run ty check
```

Pre-commit hooks are configured; run `pre-commit install` to enable them.

## Dependency Auditing

Check installed packages against known vulnerabilities:

```bash
uv run pip-audit
```

If vulnerabilities are found in transitive dependencies, update the lock file:

```bash
uv lock --upgrade
```

## Building Docs

The Quarto site lives in the `docs/` directory. Serve locally with:

```bash
quarto preview docs
```

This spins up a live preview. To produce static HTML, run:

```bash
quarto render docs
```

## CI Pipeline

Every push to `dev` and every pull request targeting `dev` runs four jobs in GitHub Actions:

| Job | What it checks |
|---|---|
| **lint** | `ruff check` + `ty check` |
| **test** | `pytest` on Python 3.10 and 3.12 (skips real-data integration tests) |
| **audit** | `pip-audit` for known dependency vulnerabilities |
| **docs** | `quarto render docs` for broken links or syntax errors |

## Releasing

### Day-to-day workflow

1. Work on a feature branch (e.g., `WIP/my-feature`).
2. Open a PR to `dev` &mdash; CI runs automatically.
3. Merge once all checks pass.

### Publishing a release

1. Update the version in `pyproject.toml` (e.g., `0.3.0b2` &rarr; `0.4.0`).
2. Update the `[Unreleased]` section in `CHANGELOG.md` with the version and date.
3. Commit on `dev`.
4. Tag and push:
    ```bash
    git tag v0.4.0
    git push origin dev --tags
    ```
5. The release workflow runs: **lint &rarr; test &rarr; build &rarr; TestPyPI &rarr; (manual approval) &rarr; PyPI**.
6. Approve the `pypi` environment deployment in GitHub when prompted.

The release pipeline uses [Trusted Publishers](https://docs.pypi.org/trusted-publishers/) &mdash; no API tokens or secrets needed. Authentication is handled via OpenID Connect between GitHub Actions and PyPI.

## Contributing Documentation

- Keep README concise&mdash;link to the appropriate Quarto page for longer guides.
- Use relative links (`[Pipeline](pipeline.md)`) so that Markdown works both locally and in the hosted site.
- Store shared assets in `docs/assets/`.
- After editing docs, run `quarto preview docs` and check the console output for broken links or syntax errors.
