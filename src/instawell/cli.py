"""
Command-line interface for InstaWell.

Provides an intuitive CLI for running DSF data analysis pipelines.
"""

import json
import sys
from pathlib import Path

import click

from instawell import (
    StepFiles,
    average_accross_replicates,
    calculate_derivative,
    filter_wells,
    find_min_temperature,
    ingest_data,
    load_experiment_context,
    min_max_scale,
    setup_experiment,
    subtract_background,
)


@click.group()
@click.version_option(package_name="instawell")
def cli():
    """
    InstaWell - Differential Scanning Fluorimetry (DSF) Data Analysis.

    A powerful toolkit for processing thermal shift assay experiments.

    \b
    Quick Start:
        1. Create experiment:    instawell init my_exp --raw data.csv --layout layout.csv
        2. Run full pipeline:    instawell run my_exp --all
        3. View results:         instawell info my_exp

    \b
    Common Workflows:
        # Run specific steps
        instawell run my_exp --steps ingest,filter,average

        # Filter wells interactively
        instawell filter my_exp --wells A1,B2,C3

        # List all experiments
        instawell list
    """
    pass


@cli.command()
@click.argument("experiment_name")
@click.option("--raw", "-r", "raw_data_path", required=True, type=click.Path(exists=True),
              help="Path to raw fluorescence data CSV file")
@click.option("--layout", "-l", "layout_path", required=True, type=click.Path(exists=True),
              help="Path to plate layout CSV file")
@click.option("--root", default="experiments", type=click.Path(),
              help="Root directory for experiments (default: ./experiments)")
@click.option("--separator", default="_", type=str,
              help="Condition separator character (default: _)")
@click.option("--fields", default="concentration,ligand,protein,buffer", type=str,
              help="Comma-separated field order (default: concentration,ligand,protein,buffer)")
@click.option("--temp-col", default="Temperature", type=str,
              help="Temperature column name (default: Temperature)")
def init(experiment_name, raw_data_path, layout_path, root, separator, fields, temp_col):
    """
    Initialize a new experiment.

    Creates experiment directory and copies data files.

    \b
    Example:
        instawell init TSA_001 --raw raw.csv --layout layout.csv
        instawell init TSA_002 -r data.csv -l plate.csv --separator '|'
    """
    click.echo(f"🔬 Initializing experiment: {click.style(experiment_name, fg='cyan', bold=True)}")

    try:
        # Parse fields
        fields_tuple = tuple(f.strip() for f in fields.split(","))

        # Validate separator
        if len(separator) != 1:
            raise click.BadParameter("Separator must be exactly one character")

        # Setup experiment
        ctx = setup_experiment(
            experiment_name=experiment_name,
            raw_data_path=raw_data_path,
            layout_data_path=layout_path,
            experiments_root=root,
            condition_separator=separator,
            fields=fields_tuple,
            temperature_column=temp_col,
        )

        click.echo(f"✅ Experiment created at: {click.style(str(ctx.experiment_dir), fg='green')}")
        click.echo(f"   📁 Raw data: {ctx.raw_data_path.name}")
        click.echo(f"   📁 Layout: {ctx.layout_data_path.name}")
        click.echo(f"   ⚙️  Separator: '{separator}'")
        click.echo(f"   ⚙️  Fields: {', '.join(fields_tuple)}")
        click.echo()
        click.echo(f"💡 Next step: Run pipeline with 'instawell run {experiment_name} --all'")

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("experiment_name")
@click.option("--all", "-a", "run_all", is_flag=True,
              help="Run all pipeline steps")
@click.option("--steps", "-s", type=str,
              help="Comma-separated list of steps: ingest,filter,average,background,scale,derivative,min_temp")
@click.option("--filter-wells", type=str,
              help="Comma-separated list of wells to filter (e.g., A1,B2)")
@click.option("--root", default="experiments", type=click.Path(),
              help="Root directory for experiments")
def run(experiment_name, run_all, steps, filter_wells, root):
    """
    Run processing pipeline steps.

    \b
    Steps:
        ingest      - Parse layout and organize raw data
        filter      - Remove problematic wells
        average     - Average technical replicates
        background  - Subtract background signal
        scale       - Normalize to 0-1 range
        derivative  - Calculate -dY/dT
        min_temp    - Find melting temperatures

    \b
    Examples:
        # Run entire pipeline
        instawell run TSA_001 --all

        # Run specific steps
        instawell run TSA_001 --steps ingest,filter,average

        # Run with well filtering
        instawell run TSA_001 --all --filter-wells A1,B2,G20
    """
    try:
        # Load experiment
        ctx = load_experiment_context(experiment_name, experiments_root=root)
        click.echo(f"🔬 Running pipeline for: {click.style(experiment_name, fg='cyan', bold=True)}")

        # Parse filter wells
        wells_to_filter = []
        if filter_wells:
            wells_to_filter = [w.strip() for w in filter_wells.split(",")]

        # Determine which steps to run
        if run_all:
            step_names = ["ingest", "filter", "average", "background", "scale", "derivative", "min_temp"]
        elif steps:
            step_names = [s.strip() for s in steps.split(",")]
        else:
            click.echo("❌ Error: Must specify --all or --steps", err=True)
            sys.exit(1)

        # Step mapping
        step_map = {
            "ingest": ("Ingesting data", lambda: ingest_data(ctx)),
            "filter": ("Filtering wells", lambda: filter_wells(ctx, wells_to_filter=wells_to_filter)),
            "average": ("Averaging replicates", lambda: average_accross_replicates(ctx)),
            "background": ("Subtracting background", lambda: subtract_background(ctx)),
            "scale": ("Min-max scaling", lambda: min_max_scale(ctx)),
            "derivative": ("Calculating derivative", lambda: calculate_derivative(ctx)),
            "min_temp": ("Finding min temperatures", lambda: find_min_temperature(ctx)),
        }

        # Run steps
        click.echo()
        for step_name in step_names:
            if step_name not in step_map:
                click.echo(f"⚠️  Warning: Unknown step '{step_name}', skipping", err=True)
                continue

            description, func = step_map[step_name]
            click.echo(f"  ▶️  {description}...", nl=False)

            try:
                func()
                click.echo(click.style(" ✓", fg="green"))
            except Exception as e:
                click.echo(click.style(f" ✗ ({e})", fg="red"))
                raise

        click.echo()
        click.echo(click.style("✅ Pipeline completed successfully!", fg="green", bold=True))
        click.echo(f"   📁 Results: {ctx.experiment_dir}")
        click.echo()
        click.echo(f"💡 View results with: instawell info {experiment_name}")

    except FileNotFoundError:
        click.echo(f"❌ Error: Experiment '{experiment_name}' not found in {root}", err=True)
        click.echo(f"   Run 'instawell list' to see available experiments", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--root", default="experiments", type=click.Path(),
              help="Root directory for experiments")
def list(root):
    """
    List all experiments.

    Shows all initialized experiments in the experiments directory.

    \b
    Example:
        instawell list
        instawell list --root /path/to/experiments
    """
    experiments_root = Path(root)

    if not experiments_root.exists():
        click.echo(f"📁 No experiments directory found at: {experiments_root}")
        click.echo(f"   Create your first experiment with 'instawell init'")
        return

    # Find all experiment directories (ones with experiment.json)
    experiments = []
    for item in experiments_root.iterdir():
        if item.is_dir() and (item / "experiment.json").exists():
            experiments.append(item)

    if not experiments:
        click.echo(f"📁 No experiments found in: {experiments_root}")
        click.echo(f"   Create your first experiment with 'instawell init'")
        return

    # Display experiments
    click.echo(f"📊 Experiments in {click.style(str(experiments_root), fg='cyan')}:")
    click.echo()

    for exp_dir in sorted(experiments):
        # Load metadata
        try:
            with open(exp_dir / "experiment.json") as f:
                metadata = json.load(f)

            name = metadata.get("experiment_name", exp_dir.name)
            created = metadata.get("created_at_iso", "Unknown")

            # Check which steps have been completed
            completed_steps = []
            if (exp_dir / StepFiles.INGESTED_DATA).exists():
                completed_steps.append("ingest")
            if (exp_dir / StepFiles.FILTERED_DATA).exists():
                completed_steps.append("filter")
            if (exp_dir / StepFiles.AVERAGED_DATA).exists():
                completed_steps.append("average")
            if (exp_dir / StepFiles.MIN_TEMPERATURES_DATA).exists():
                completed_steps.append("complete")

            status = " → ".join(completed_steps) if completed_steps else "initialized"

            click.echo(f"  • {click.style(name, fg='cyan', bold=True)}")
            click.echo(f"    Created: {created}")
            click.echo(f"    Status:  {status}")
            click.echo()

        except Exception as e:
            click.echo(f"  • {exp_dir.name} (error reading metadata: {e})")
            click.echo()


@cli.command()
@click.argument("experiment_name")
@click.option("--root", default="experiments", type=click.Path(),
              help="Root directory for experiments")
@click.option("--verbose", "-v", is_flag=True,
              help="Show detailed information")
def info(experiment_name, root, verbose):
    """
    Show experiment information.

    Displays configuration, status, and output files.

    \b
    Example:
        instawell info TSA_001
        instawell info TSA_001 --verbose
    """
    try:
        ctx = load_experiment_context(experiment_name, experiments_root=root)

        click.echo(f"🔬 Experiment: {click.style(experiment_name, fg='cyan', bold=True)}")
        click.echo(f"   📁 Location: {ctx.experiment_dir}")
        click.echo()

        # Configuration
        click.echo(click.style("⚙️  Configuration:", fg="yellow", bold=True))
        click.echo(f"   Separator: '{ctx.condition_separator}'")
        click.echo(f"   Fields: {', '.join(ctx.fields)}")
        click.echo(f"   Temperature column: {ctx.temperature_column}")
        click.echo(f"   NPC marker: {ctx.non_protein_control_marker}")
        click.echo()

        # Files
        click.echo(click.style("📄 Output Files:", fg="yellow", bold=True))
        step_files = [
            (StepFiles.INGESTED_DATA, "Raw organized data"),
            (StepFiles.FILTERED_DATA, "Filtered data"),
            (StepFiles.AVERAGED_DATA, "Averaged replicates"),
            (StepFiles.BG_SUB_DATA, "Background subtracted"),
            (StepFiles.MIN_MAX_SCALED_DATA, "Min-max scaled"),
            (StepFiles.DERIVATIVE_DATA, "Derivative"),
            (StepFiles.MIN_TEMPERATURES_DATA, "Min temperatures"),
        ]

        for file_name, description in step_files:
            file_path = ctx.experiment_dir / file_name
            if file_path.exists():
                size = file_path.stat().st_size / 1024  # KB
                status = click.style("✓", fg="green")
                size_str = f"({size:.1f} KB)"
            else:
                status = click.style("✗", fg="red")
                size_str = ""

            click.echo(f"   {status} {description:<25} {size_str}")

        # Filtered wells
        filtered_wells_path = ctx.experiment_dir / StepFiles.FILTERED_WELLS
        if filtered_wells_path.exists():
            with open(filtered_wells_path) as f:
                wells = [w.strip() for w in f.readlines() if w.strip()]
            if wells:
                click.echo()
                click.echo(click.style("🚫 Filtered Wells:", fg="yellow", bold=True))
                click.echo(f"   {', '.join(wells)}")

        # Verbose: show min temperatures summary
        if verbose:
            min_temp_path = ctx.experiment_dir / StepFiles.MIN_TEMPERATURES_DATA
            if min_temp_path.exists():
                import pandas as pd

                df = pd.read_csv(min_temp_path)
                click.echo()
                click.echo(click.style("🌡️  Min Temperatures Summary:", fg="yellow", bold=True))
                click.echo(f"   Total conditions: {len(df)}")
                click.echo(f"   Temp range: {df['min_temperature'].min():.1f}°C - {df['min_temperature'].max():.1f}°C")
                click.echo(f"   Mean Tm: {df['min_temperature'].mean():.1f}°C")

    except FileNotFoundError:
        click.echo(f"❌ Error: Experiment '{experiment_name}' not found", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("experiment_name")
@click.argument("wells", nargs=-1)
@click.option("--root", default="experiments", type=click.Path(),
              help="Root directory for experiments")
def filter(experiment_name, wells, root):
    """
    Filter wells from an experiment.

    Add wells to the filter list and re-filter the data.

    \b
    Examples:
        instawell filter TSA_001 A1 B2 G20
        instawell filter TSA_001 C3
    """
    try:
        ctx = load_experiment_context(experiment_name, experiments_root=root)

        # Check if data has been ingested
        if not (ctx.experiment_dir / StepFiles.INGESTED_DATA).exists():
            click.echo("❌ Error: Data not ingested yet. Run 'instawell run ... --steps ingest' first", err=True)
            sys.exit(1)

        if not wells:
            click.echo("❌ Error: No wells specified", err=True)
            sys.exit(1)

        # Convert wells to list
        wells_to_filter = list(wells)

        click.echo(f"🚫 Filtering wells from {click.style(experiment_name, fg='cyan', bold=True)}")
        click.echo(f"   Wells: {', '.join(wells_to_filter)}")

        # Run filter
        filter_wells(ctx, wells_to_filter=wells_to_filter)

        click.echo(click.style("✅ Wells filtered successfully!", fg="green"))
        click.echo(f"   📁 Filtered data: {ctx.experiment_dir / StepFiles.FILTERED_DATA}")

    except FileNotFoundError:
        click.echo(f"❌ Error: Experiment '{experiment_name}' not found", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
