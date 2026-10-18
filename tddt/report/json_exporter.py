"""JSON exporter — writes the stable schema defined in spec §10.2."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tddt.core.entity import EntityGraph


def export_json(graph: "EntityGraph", scan_meta: dict, path: Path) -> None:
    """Write *graph* + *scan_meta* to *path* as a JSON file.

    Schema (top-level keys are stable):
    {
        "scan": {...},
        "entities": {
            "by_type": {"Domain": [...], ...},
            "graph_edges": [{"parent_id": ..., "child_id": ..., "type": ...}, ...]
        },
        "profile": null  # populated by ProfileAggregator in user mode
    }

    Each entity dict carries: type, value, id, confidence, source_module,
    parent_id, discovered_at, metadata — as defined in spec §10.2.
    """
    raw = graph.export()
    output = {
        "scan": scan_meta,
        "entities": {
            "by_type": raw["by_type"],
            "graph_edges": raw.get("edges", []),
        },
        "profile": None,
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
