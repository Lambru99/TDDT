"""Markdown exporter — human-readable report with section headings per spec §10.2."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tddt.core.entity import EntityGraph

# Map section heading → entity type names that belong to it
_SECTIONS: list[tuple[str, list[str]]] = [
    ("Identity", ["Username", "FullName", "Phone", "Organization"]),
    ("DNS", ["Domain", "Subdomain", "DNSRecord", "IPAddress", "Port", "Certificate", "WHOISRecord"]),
    ("Attack Surface", ["URL", "Technology", "TakeoverFinding", "Finding", "Service", "Website", "Bucket", "TrackerID", "CVE"]),
    ("Emails", ["Email"]),
    ("Secrets", ["Secret"]),
]


def export_markdown(graph: "EntityGraph", scan_meta: dict, path: Path) -> None:
    """Write a Markdown report to *path*."""
    raw = graph.export()
    by_type = raw["by_type"]

    lines: list[str] = ["# TDDT Scan Report\n"]
    mode = scan_meta.get("mode", "")
    seed = scan_meta.get("seed", {})
    lines.append(f"**Mode:** {mode}  ")
    lines.append(f"**Seed:** {seed}  ")
    started = scan_meta.get("started_at", "")
    if started:
        lines.append(f"**Started:** {started}  ")
    lines.append("")

    for section_name, type_names in _SECTIONS:
        lines.append(f"## {section_name}\n")
        section_has_content = False
        for type_name in type_names:
            entities = by_type.get(type_name, [])
            if not entities:
                continue
            section_has_content = True
            lines.append(f"### {type_name} ({len(entities)})\n")
            for ent in entities:
                value = ent["value"]
                conf = ent.get("confidence", 0.0)
                lines.append(f"- `{value}` (confidence: {conf:.2f})")
            lines.append("")
        if not section_has_content:
            lines.append("_None found._\n")

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
