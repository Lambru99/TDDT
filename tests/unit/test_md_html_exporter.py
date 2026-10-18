"""Unit tests for Markdown + HTML exporters — Task 2.3."""

from __future__ import annotations

import re

from tddt.core.entity import (
    DNSRecord,
    Domain,
    Email,
    EntityGraph,
    Secret,
    Subdomain,
    Technology,
    URL,
)


def _build_graph():
    g = EntityGraph()
    g.add(Domain(value="example.com"))
    g.add(Subdomain(value="www.example.com"))
    g.add(Email(value="info@example.com"))
    g.add(DNSRecord(value="MX 10 mail.example.com"))
    g.add(Technology(value="nginx"))
    g.add(URL(value="https://www.example.com"))
    full_secret = "AKIA" + "B" * 100
    g.add(Secret(value=full_secret))
    return g, full_secret


_SCAN_META = {"mode": "corporate", "seed": {"Domain": "example.com"}}


# ── Markdown ──────────────────────────────────────────────────────────────────


def test_markdown_has_section_per_group(tmp_path):
    from tddt.report.markdown_exporter import export_markdown

    graph, _ = _build_graph()
    path = tmp_path / "report.md"
    export_markdown(graph, _SCAN_META, path)

    text = path.read_text()
    for heading in ("## Identity", "## DNS", "## Attack Surface", "## Emails", "## Secrets"):
        assert heading in text, f"Missing heading: {heading!r}"


def test_markdown_no_full_secret(tmp_path):
    from tddt.report.markdown_exporter import export_markdown

    graph, full_secret = _build_graph()
    path = tmp_path / "report.md"
    export_markdown(graph, _SCAN_META, path)

    text = path.read_text()
    assert full_secret not in text, "Full secret value leaked into Markdown output"


# ── HTML ──────────────────────────────────────────────────────────────────────


def test_html_self_contained(tmp_path):
    from tddt.report.html_exporter import export_html

    graph, _ = _build_graph()
    path = tmp_path / "report.html"
    export_html(graph, _SCAN_META, path)

    html = path.read_text()
    assert "<html" in html.lower(), "Output lacks <html> tag"
    assert not re.search(r'<link[^>]+href=["\']https://', html), "External CDN link found"


def test_html_includes_summary_table(tmp_path):
    from tddt.report.html_exporter import export_html

    graph, _ = _build_graph()
    path = tmp_path / "report.html"
    export_html(graph, _SCAN_META, path)

    html = path.read_text()
    # Rich renders tables as pre-formatted ASCII art with a title; check the title is present
    assert "Scan Summary" in html, "Summary table title not in HTML output"
    assert "Domain" in html, "Entity types not listed in HTML output"
