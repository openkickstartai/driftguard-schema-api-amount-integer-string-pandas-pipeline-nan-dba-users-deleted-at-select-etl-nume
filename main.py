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
@click.argument("source", required=False, default=None)
@click.option("--table", "-t", default=None, help="Table name (required for databases)")
@click.option("--format", "-f", "fmt", type=click.Choice(["sqlite", "csv", "json"]), default=None)
@click.option("--source", "source_type", type=click.Choice(["csv", "rest", "postgres"]), default=None, help="Connector type")
@click.option("--path", "source_path", default=None, help="File path for connector")
@click.option("--url", default=None, help="URL for REST API connector")
def snapshot(source, table, fmt, source_type, source_path, url):
    """Take a baseline schema snapshot."""
    if source_type:
        from driftguard.connectors import CSVConnector, RestAPIConnector, PostgresConnector
        connector_map = {"csv": CSVConnector, "rest": RestAPIConnector, "postgres": PostgresConnector}
        conn = connector_map[source_type]()
        config = {}
        if source_path:
            config["path"] = source_path
        if url:
            config["url"] = url
        conn.connect(config)
        snap = conn.snapshot()
        conn.close()
        tbl = Table(title=f"Schema Snapshot: {snap.source_name}")
        tbl.add_column("Column", style="cyan")
        tbl.add_column("Type", style="green")
        for c in snap.columns:
            tbl.add_row(c.name, c.dtype)
        console.print(tbl)
        console.print(f"[green]\u2713[/] Snapshot: {len(snap.columns)} columns from {snap.source_name}")
        return
    if not source:
        console.print("[red]Error: provide SOURCE argument or use --source/--path options[/]")
        sys.exit(1)
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


if __name__ == "__main__":
    cli()
