"""DriftGuard CLI — schema drift detection for data pipelines."""
import sys, json
import click
from rich.console import Console
from rich.table import Table
from driftguard import snapshot_sqlite, snapshot_csv, snapshot_json, diff_schemas, save_snapshot, load_snapshot

console = Console()
SEV_COLOR = {"breaking": "red bold", "silent_corruption": "yellow bold", "info": "cyan"}


def _detect_fmt(src):
    for ext, fmt in [(".db", "sqlite"), (".sqlite", "sqlite"), (".csv", "csv"), (".json", "json")]:
        if src.endswith(ext):
            return fmt
    return None


def _take_snapshot(source, table, fmt):
    fmt = fmt or _detect_fmt(source)
    if fmt == "sqlite":
        if not table:
            console.print("[red]Error: --table required for sqlite[/]")
            sys.exit(1)
        return snapshot_sqlite(source, table)
    if fmt == "csv":
        return snapshot_csv(source)
    if fmt == "json":
        return snapshot_json(source)
    console.print(f"[red]Cannot detect format for '{source}'. Use --format.[/]")
    sys.exit(1)


@click.group()
@click.version_option("0.1.0")
def cli():
    """DriftGuard — catch schema drift before it corrupts your data."""


@cli.command()
@click.argument("source")
@click.option("--table", "-t", default=None, help="Table name (required for databases)")
@click.option("--format", "-f", "fmt", type=click.Choice(["sqlite", "csv", "json"]), default=None)
def snapshot(source, table, fmt):
    """Take a baseline schema snapshot."""
    schema = _take_snapshot(source, table, fmt)
    save_snapshot(schema)
    console.print(f"[green]\u2713[/] Snapshot: [bold]{schema.table}[/] | {len(schema.columns)} cols | fp={schema.fingerprint}")


@cli.command()
@click.argument("source")
@click.option("--table", "-t", default=None)
@click.option("--format", "-f", "fmt", type=click.Choice(["sqlite", "csv", "json"]), default=None)
@click.option("--output", "-o", type=click.Choice(["table", "json"]), default="table")
def check(source, table, fmt, output):
    """Check for schema drift against last snapshot."""
    current = _take_snapshot(source, table, fmt)
    previous = load_snapshot(current.table)
    if not previous:
        save_snapshot(current)
        console.print("[yellow]No previous snapshot found. Saved baseline.[/]")
        return
    if current.fingerprint == previous.fingerprint:
        console.print("[green]\u2713 No drift detected.[/]")
        return
    drifts = diff_schemas(previous, current)
    if output == "json":
        click.echo(json.dumps([{"kind": d.kind, "column": d.column, "severity": d.severity,
                                "detail": d.detail, "fix": d.fix} for d in drifts], indent=2))
    else:
        t = Table(title="\U0001f6a8 Schema Drift Report")
        for col in ["Severity", "Kind", "Column", "Detail", "Fix"]:
            t.add_column(col)
        for d in drifts:
            c = SEV_COLOR.get(d.severity, "white")
            t.add_row(f"[{c}]{d.severity}[/]", d.kind, d.column, d.detail, d.fix or "-")
        console.print(t)
    save_snapshot(current)
    breaking = sum(1 for d in drifts if d.severity == "breaking")
    silent = sum(1 for d in drifts if d.severity == "silent_corruption")
    if breaking:
        console.print(f"\n[red]\u26a0 {breaking} BREAKING + {silent} SILENT CORRUPTION drifts detected[/]")
        sys.exit(2)
    elif silent:
        console.print(f"\n[yellow]\u26a0 {silent} silent corruption risks detected[/]")
        sys.exit(1)



@cli.command()
@click.option("--source", "-s", required=True, help="Source name to check blast radius for")
@click.option("--config", "-c", "config_path", default="dag_config.yaml", help="Path to DAG config YAML")
@click.option("--event", "-e", default=None, help="Drift event description")
def blast(source, config_path, event):
    """Show blast radius of a schema change on downstream assets."""
    from driftguard.dag import load_dag, blast_radius, render_blast_radius

    try:
        dag = load_dag(config_path)
    except FileNotFoundError:
        console.print(f"[red]Error: Config file not found: {config_path}[/]")
        sys.exit(1)
    except ValueError as e:
        console.print(f"[red]Error: {e}[/]")
        sys.exit(1)

    try:
        affected = blast_radius(dag, source, event)
    except ValueError as e:
        console.print(f"[red]Error: {e}[/]")
        sys.exit(1)

    output = render_blast_radius(affected, source_name=source, dag=dag, drift_event=event)
    console.print(output)

    if affected:
        console.print(f"[yellow]\u26a0 {len(affected)} downstream asset(s) affected[/]")
    else:
        console.print("[green]\u2713 No downstream assets affected[/]")


if __name__ == "__main__":
    cli()
