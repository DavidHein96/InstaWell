# instawell/logging_util.py
import logging
from logging import FileHandler, Formatter
from pathlib import Path


def setup_experiment_logging(
    experiment_dir: Path,
    filename: str = "experiment.log",
    level: int = logging.INFO,
) -> Path:
    """
    Attach a file handler for this experiment to the `instawell` logger.
    Safe to call multiple times; it won't duplicate handlers for the same file.
    """
    experiment_dir.mkdir(parents=True, exist_ok=True)
    log_path = experiment_dir / filename

    pkg_logger = logging.getLogger("instawell")
    pkg_logger.setLevel(level)

    # Don't add duplicate handlers for the same file
    for h in pkg_logger.handlers:
        if isinstance(h, FileHandler) and getattr(h, "baseFilename", None) == str(log_path):
            return log_path

    fh = FileHandler(log_path, encoding="utf-8")
    fh.setLevel(level)
    fh.setFormatter(Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    pkg_logger.addHandler(fh)

    pkg_logger.propagate = True
    return log_path


def ensure_experiment_context(
    experiment_name: str,
    *,
    experiments_root: str | Path = "experiments",
    log_to_file: bool = True,
    log_level: int = logging.INFO,
) -> Path:
    """
    Common setup used by all step entrypoints.

    - Creates a top-level experiments_root directory (default: ./experiments)
    - Creates this experiment's directory under it
    - Ensures a .gitignore in the experiment directory
    - Optionally wires all `instawell` loggers to experiment.log

    Returns
    -------
    experiment_dir : Path
        The path to this experiment's directory.
    """
    # Resolve the base experiments directory
    experiments_root_path = Path(experiments_root)

    # If relative, anchor to current working directory
    if not experiments_root_path.is_absolute():
        experiments_root_path = Path.cwd() / experiments_root_path

    experiments_root_path.mkdir(parents=True, exist_ok=True)

    # Now the specific experiment directory, e.g. ./experiments/exp_001
    experiment_dir = experiments_root_path / experiment_name
    experiment_dir.mkdir(parents=True, exist_ok=True)

    # Keep experiment artifacts out of git by default
    gitignore = experiment_dir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("*\n", encoding="utf-8")

    if log_to_file:
        setup_experiment_logging(experiment_dir=experiment_dir, level=log_level)

    # check if any .csv files exist in the experiment directory
    csv_files = list(experiment_dir.glob("*.csv"))

    return experiment_dir
