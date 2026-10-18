"""JSON exporter — stub; full implementation in Task 2.2."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tddt.core.entity import EntityGraph


def export_json(graph: "EntityGraph", scan_meta: dict, path: Path) -> None:
    """Write graph + scan_meta to *path* as a JSON file (Task 2.2 spec shape)."""
    output = {
        "scan": scan_meta,
        "entities": {"by_type": {}, "graph_edges": []},
        "profile": None,
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
