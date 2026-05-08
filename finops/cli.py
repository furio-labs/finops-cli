from __future__ import annotations
import os
import sys
import json
from datetime import date, datetime, timezone
from pathlib import Path

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from finops.auth import get_credential, AuthMethod
from finops.config import load_config
from finops.collectors.cost import CostCollector
from finops.collectors.resources import ResourceCollector
from finops.collectors.invoices import InvoiceCollector
from finops.analyzers.untagged import UntaggedAnalyzer
from finops.analyzers.idle import IdleAnalyzer
from finops.analyzers.wrong_sku import WrongSkuAnalyzer
from finops.analyzers.dev_in_prod import DevInProdAnalyzer
from finops.analyzers.scheduling import SchedulingAnalyzer
from finops.models import SubscriptionData, Severity
from finops.reporters.models import Report, report_to_json, report_from_json
from finops.ai.analyzer import AiAnalyzer
from finops.reporters.excel import ExcelReporter
from finops.reporters.html import HtmlReporter
from finops.reporters.markdown import MarkdownReporter
from azure.core.exceptions import HttpResponseError

load_dotenv()

console = Console()

_ALL_ANALYZERS = {
    "untagged": UntaggedAnalyzer,
    "idle": IdleAnalyzer,
    "wrong_sku": WrongSkuAnalyzer,
    "dev_in_prod": DevInProdAnalyzer,
    "scheduling": SchedulingAnalyzer,
}


@click.group()
def cli() -> None:
    """FinOps CLI — Azure cost analysis and optimization. Built by Furio Labs (furiolabs.com)."""


@cli.command()
@click.option("--subscriptions", "-s", multiple=True, help="Override subscription IDs from config")
@click.option("--analyzers", "-a", multiple=True, help="Limit analyzers (untagged,idle,wrong_sku,dev_in_prod,scheduling)")
@click.option("--from", "date_from", default=None, help="Start date YYYY-MM-DD (default: first day of current month)")
@click.option("--to", "date_to", default=None, help="End date YYYY-MM-DD (default: today)")
@click.option("--granularity", "-g", default="daily",
              type=click.Choice(["daily", "monthly"], case_sensitive=False),
              show_default=True,
              help="Cost data granularity. 'monthly' is ~10x faster for long date ranges.")
@click.option("--output", "-o", default="./reports", show_default=True, help="Output directory")
@click.option("--config", "-c", default="subscriptions.yaml", show_default=True, help="Config file")
@click.option("--with-ai", "with_ai", is_flag=True, default=False,
              help="AI-powered cost analysis via Claude (requires ANTHROPIC_API_KEY)")
def run(
    subscriptions: tuple[str, ...],
    analyzers: tuple[str, ...],
    date_from: str | None,
    date_to: str | None,
    granularity: str,
    output: str,
    config: str,
    with_ai: bool,
) -> None:
    """Analyze Azure subscriptions and generate cost reports."""
    cfg = load_config(config)
    if subscriptions:
        cfg = cfg.with_subscription_override(list(subscriptions))

    today = date.today()
    try:
        start = date.fromisoformat(date_from) if date_from else today.replace(day=1)
        end = date.fromisoformat(date_to) if date_to else today
    except ValueError as exc:
        raise click.BadParameter(f"Invalid date format: {exc}. Use YYYY-MM-DD.")
    if start > end:
        raise click.UsageError(f"--from ({start}) must be before --to ({end})")

    try:
        credential, method = get_credential()
        console.print(f"[dim]Auth: {method.value} · Granularidad: {granularity}[/dim]")
    except Exception as exc:
        console.print(f"[red]Auth failed: {exc}[/red]")
        console.print("[yellow]Set AZURE_TENANT_ID/AZURE_CLIENT_ID/AZURE_CLIENT_SECRET or run 'az login'[/yellow]")
        sys.exit(1)

    if analyzers:
        unknown = set(analyzers) - set(_ALL_ANALYZERS)
        if unknown:
            raise click.BadParameter(
                f"Unknown analyzers: {unknown}. Valid: {sorted(_ALL_ANALYZERS)}",
                param_hint="--analyzers",
            )
    active_analyzers = [
        cls(cfg) for name, cls in _ALL_ANALYZERS.items()
        if not analyzers or name in analyzers
    ]

    cost_col = CostCollector(credential)
    res_col = ResourceCollector(credential)
    inv_col = InvoiceCollector(credential)

    results: list[SubscriptionData] = []

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as progress:
        for sub_entry in cfg.subscriptions:
            task = progress.add_task(f"[cyan]{sub_entry.name}[/cyan]...", total=None)
            try:
                resources = res_col.collect(sub_entry.id)
                costs = cost_col.collect(sub_entry.id, start, end, granularity.capitalize())
                invoices = inv_col.collect(sub_entry.id)
                findings = []
                for analyzer in active_analyzers:
                    findings.extend(analyzer.analyze(sub_entry.id, resources, costs))
                results.append(SubscriptionData(
                    subscription_id=sub_entry.id,
                    subscription_name=sub_entry.name,
                    resources=resources,
                    costs=costs,
                    invoices=invoices,
                    findings=findings,
                ))
                total = sum(c.total_cost for c in costs)
                console.print(
                    f"[green]✓[/green] {sub_entry.name} — "
                    f"{len(resources)} recursos, ${total:,.2f}, {len(findings)} hallazgos"
                )
            except HttpResponseError as exc:
                if exc.status_code == 403:
                    console.print(f"[yellow]⚠ {sub_entry.name} — sin permisos, omitida[/yellow]")
                    results.append(SubscriptionData(
                        subscription_id=sub_entry.id,
                        subscription_name=sub_entry.name,
                        resources=[], costs=[], invoices=[],
                        skipped=True, skip_reason="Insufficient permissions (403)",
                    ))
                else:
                    console.print(f"[red]✗ {sub_entry.name} — error: {exc}[/red]")
                    results.append(SubscriptionData(
                        subscription_id=sub_entry.id,
                        subscription_name=sub_entry.name,
                        resources=[], costs=[], invoices=[],
                        skipped=True, skip_reason=f"API error: {exc.status_code}",
                    ))
            finally:
                progress.remove_task(task)

    if with_ai:
        if not os.getenv("ANTHROPIC_API_KEY"):
            console.print("[yellow]⚠ --with-ai ignorado: ANTHROPIC_API_KEY no configurado[/yellow]")
        else:
            ai = AiAnalyzer()
            for sub_data in results:
                if not sub_data.skipped:
                    try:
                        sub_data.ai_insights = ai.analyze(sub_data, start, end)
                        console.print(
                            f"[dim]IA: {len(sub_data.ai_insights)} insights — {sub_data.subscription_name}[/dim]"
                        )
                    except Exception as exc:
                        console.print(f"[yellow]⚠ IA falló para {sub_data.subscription_name}: {exc}[/yellow]")

    report = Report(
        generated_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        date_from=start.isoformat(),
        date_to=end.isoformat(),
        subscriptions=results,
    )

    _write_reports(report, Path(output) / today.isoformat())
    _print_summary(report)


@cli.command()
@click.option("--from-cache", required=True, type=click.Path(exists=True), help="Path to directory with data.json")
@click.option("--output", "-o", default=None, help="Output directory (default: same as --from-cache)")
def report(from_cache: str, output: str | None) -> None:
    """Re-render reports from cached data.json without making API calls."""
    cache_path = Path(from_cache)
    data_file = cache_path / "data.json"
    if not data_file.exists():
        console.print(f"[red]data.json not found in {from_cache}[/red]")
        sys.exit(1)

    loaded_report = report_from_json(data_file.read_text())
    out_dir = Path(output) if output else cache_path
    _write_reports(loaded_report, out_dir)


@cli.command("list-subscriptions")
@click.option("--config", "-c", default="subscriptions.yaml", show_default=True)
def list_subscriptions(config: str) -> None:
    """List subscriptions defined in the config file."""
    cfg = load_config(config)
    table = Table(title="Configured Subscriptions")
    table.add_column("ID", style="dim")
    table.add_column("Name")
    table.add_column("Tags")
    for sub in cfg.subscriptions:
        tags_str = ", ".join(f"{k}={v}" for k, v in sub.tags.items())
        table.add_row(sub.id, sub.name, tags_str or "—")
    console.print(table)


def _write_reports(report: Report, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "data.json").write_text(report_to_json(report), encoding="utf-8")
    (out_dir / "report.html").write_text(HtmlReporter().render(report), encoding="utf-8")
    (out_dir / "report.md").write_text(MarkdownReporter().render(report), encoding="utf-8")
    (out_dir / "report.xlsx").write_bytes(ExcelReporter().render(report))
    console.print(f"[green]Reports written to: {out_dir}[/green]")


def _print_summary(report: Report) -> None:
    by_sev = report.findings_by_severity()
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="bold")
    table.add_column(justify="right")
    table.add_column(style="green")
    for sev_name in ("CRITICAL", "HIGH", "MEDIUM", "INFO"):
        findings = by_sev.get(sev_name, [])
        savings = sum(f.estimated_monthly_savings_usd for f in findings)
        table.add_row(sev_name, str(len(findings)), f"~${savings:,.2f}/mes" if savings else "")
    console.rule()
    console.print(table)
    console.rule()
