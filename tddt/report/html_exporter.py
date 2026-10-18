"""HTML exporter — self-contained report via Rich console recording."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console
from rich.table import Table

if TYPE_CHECKING:
    from tddt.core.entity import EntityGraph


def export_html(graph: "EntityGraph", scan_meta: dict, path: Path) -> None:
    """Write a self-contained HTML report to *path*."""
    raw = graph.export()
    by_type = raw["by_type"]

    console = Console(record=True, width=120)

    # Summary table
    summary = Table(title="Scan Summary", show_header=True, header_style="bold")
    summary.add_column("Entity Type")
    summary.add_column("Count", justify="right")
    for type_name, entities in sorted(by_type.items()):
        summary.add_row(type_name, str(len(entities)))
    console.print(summary)

    mode = scan_meta.get("mode", "unknown")
    seed = scan_meta.get("seed", {})
    console.print(f"\n[bold]Mode:[/bold] {mode}   [bold]Seed:[/bold] {seed}\n")

    # Per-type detail tables
    for type_name, entities in sorted(by_type.items()):
        detail = Table(title=type_name, show_header=True, header_style="dim")
        detail.add_column("Value")
        detail.add_column("Confidence", justify="right")
        detail.add_column("Source")
        for ent in entities:
            detail.add_row(
                ent["value"],
                f"{ent.get('confidence', 0.0):.2f}",
                ent.get("source_module") or "",
            )
        console.print(detail)

    html = console.export_html(inline_styles=True)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
