"""JSON exporter — writes the stable schema defined in spec §10.2."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tddt.core.entity import EntityGraph


# Keys copied from `graph.metadata` into `output["scan"]` so engine-level
# termination state travels into the report (Review Focus #2).
_SCAN_METADATA_KEYS = ("terminated_reason", "iterations", "elapsed_s")


def export_json(
    graph: "EntityGraph",
    scan_meta: dict,
    path: Path,
    profile: dict | None = None,
    cross_mode_results: dict | None = None,
) -> None:
    """Write *graph* + *scan_meta* to *path* as a JSON file.

    Top-level schema (stable, exactly three keys):
        {
            "scan": {
                ...,  # mode, seed, timing, flags
                "terminated_reason": "converged"|"max_iterations"|"max_runtime",
                "iterations": int,
                "elapsed_s": float,
                "cross_mode_results": {...}  # optional, nested here (not top-level)
            },
            "entities": {
                "by_type": {"Domain": [...], ...},
                "graph_edges": [{"parent_id": ..., "child_id": ..., "type": ...}, ...]
            },
            "profile": null | {...}  # populated by ProfileAggregator in user mode
        }
    """
    raw = graph.export()
    graph_metadata = raw.get("metadata", {}) or {}

    scan: dict = dict(scan_meta)
    for key in _SCAN_METADATA_KEYS:
        if key in graph_metadata:
            scan[key] = graph_metadata[key]
    if cross_mode_results is not None:
        scan["cross_mode_results"] = cross_mode_results

    output: dict = {
        "scan": scan,
        "entities": {
            "by_type": raw["by_type"],
            "graph_edges": raw.get("edges", []),
        },
        "profile": profile,
    }

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
