"""Unit tests for tddt.cli main() entrypoint — Task 2.1."""

from pathlib import Path
from unittest.mock import patch

import pytest

from tddt.core.entity import Domain, Email, EntityGraph, FullName
from tddt.core.module import MODULE_REGISTRY, BaseModule


def _empty_graph() -> EntityGraph:
    return EntityGraph()


def _scan_arg(mock_engine, key: str, *, pos: int | None = None, default=None):
    """Retrieve a positional-or-keyword arg from the most-recent scan() call."""
    ca = mock_engine.return_value.scan.call_args
    if ca is None:
        return default
    if key in ca.kwargs:
        return ca.kwargs[key]
    if pos is not None and pos < len(ca.args):
        return ca.args[pos]
    return default


# ── corp ──────────────────────────────────────────────────────────────────────


def test_corp_requires_domain():
    from tddt.cli import main

    with pytest.raises(SystemExit) as exc_info:
        main(["corp"])
    assert exc_info.value.code == 2


def test_corp_domain_launches_scan(tmp_path):
    from tddt.cli import main

    graph = _empty_graph()
    with (
        patch("tddt.cli.CorrelationEngine") as MockEngine,
        patch("tddt.cli.export_json"),
        patch("tddt.cli.load_settings"),
        patch("tddt.cli.get_client"),
    ):
        MockEngine.return_value.scan.return_value = graph
        ret = main(["corp", "example.com", "-o", str(tmp_path / "out.json")])
    assert ret == 0
    seeds = _scan_arg(MockEngine, "seeds", pos=0, default=[])
    assert any(isinstance(s, Domain) and s.value == "example.com" for s in seeds)


# ── user ──────────────────────────────────────────────────────────────────────


def test_user_requires_at_least_one_input(capsys):
    from tddt.cli import main

    with pytest.raises(SystemExit) as exc_info:
        main(["user"])
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    combined = (captured.out + captured.err).lower()
    assert any(kw in combined for kw in ("email", "username", "name", "phone"))


def test_user_accepts_multi_input(tmp_path):
    from tddt.cli import main

    graph = _empty_graph()
    with (
        patch("tddt.cli.CorrelationEngine") as MockEngine,
        patch("tddt.cli.export_json"),
        patch("tddt.cli.load_settings"),
        patch("tddt.cli.get_client"),
    ):
        MockEngine.return_value.scan.return_value = graph
        ret = main(
            [
                "user",
                "--email",
                "x@y.com",
                "--name",
                "Mario Rossi",
                "-o",
                str(tmp_path / "out.json"),
            ]
        )
    assert ret == 0
    seeds = _scan_arg(MockEngine, "seeds", pos=0, default=[])
    type_names = {type(s).__name__ for s in seeds}
    assert "Email" in type_names
    assert "FullName" in type_names


# ── flags ─────────────────────────────────────────────────────────────────────


def test_light_flag_sets_allow_active_false(tmp_path):
    from tddt.cli import main

    graph = _empty_graph()
    with (
        patch("tddt.cli.CorrelationEngine") as MockEngine,
        patch("tddt.cli.export_json"),
        patch("tddt.cli.load_settings"),
        patch("tddt.cli.get_client"),
    ):
        MockEngine.return_value.scan.return_value = graph
        main(["corp", "example.com", "--light", "-o", str(tmp_path / "out.json")])
    allow_active = _scan_arg(MockEngine, "allow_active", pos=2, default=True)
    assert allow_active is False


def test_only_keyless_flag_sets_filter(tmp_path):
    from tddt.cli import main

    graph = _empty_graph()
    with (
        patch("tddt.cli.CorrelationEngine") as MockEngine,
        patch("tddt.cli.export_json"),
        patch("tddt.cli.load_settings"),
        patch("tddt.cli.get_client"),
    ):
        MockEngine.return_value.scan.return_value = graph
        main(
            ["corp", "example.com", "--only-keyless", "-o", str(tmp_path / "out.json")]
        )
    keyless_only = _scan_arg(MockEngine, "keyless_only", pos=3, default=False)
    assert keyless_only is True


# ── list-modules ──────────────────────────────────────────────────────────────


def test_list_modules_prints_registered(capsys):
    from tddt.cli import main

    orig = dict(MODULE_REGISTRY)

    class _FakeA(BaseModule):
        name = "fake.list_a"
        consumes = [Domain]
        produces = []
        active = False
        requires_key = None
        mode = ["corporate"]

        def run(self, entities):
            return []

    class _FakeB(BaseModule):
        name = "fake.list_b"
        consumes = [Domain]
        produces = []
        active = False
        requires_key = None
        mode = ["corporate"]

        def run(self, entities):
            return []

    MODULE_REGISTRY["fake.list_a"] = _FakeA
    MODULE_REGISTRY["fake.list_b"] = _FakeB
    try:
        main(["list-modules"])
        captured = capsys.readouterr()
        assert "fake.list_a" in captured.out
        assert "fake.list_b" in captured.out
    finally:
        MODULE_REGISTRY.clear()
        MODULE_REGISTRY.update(orig)


# ── output default path ───────────────────────────────────────────────────────


def test_output_default_path_pattern(tmp_path, monkeypatch):
    """No -o flag → report file named report-example.com-<timestamp>.json."""
    from tddt.cli import main

    monkeypatch.chdir(tmp_path)
    graph = _empty_graph()
    with (
        patch("tddt.cli.CorrelationEngine") as MockEngine,
        patch("tddt.cli.export_json") as mock_export,
        patch("tddt.cli.load_settings"),
        patch("tddt.cli.get_client"),
    ):
        MockEngine.return_value.scan.return_value = graph
        main(["corp", "example.com"])

    assert mock_export.called
    ca = mock_export.call_args
    # export_json(graph, scan_meta, path)
    output_path: Path = ca.args[2] if len(ca.args) >= 3 else ca.kwargs.get("path")
    assert output_path is not None, "export_json must be called with a path argument"
    assert output_path.name.startswith("report-example.com-")
    assert output_path.name.endswith(".json")


# ── clear-cache ───────────────────────────────────────────────────────────────


def test_clear_cache_removes_file(tmp_path):
    from tddt.cli import main

    cache_file = tmp_path / "http.sqlite"
    cache_file.write_text("dummy")

    with patch("tddt.cli.get_cache_path", return_value=cache_file):
        ret = main(["clear-cache"])

    assert ret == 0
    assert not cache_file.exists()


# ── update-wmn-db ─────────────────────────────────────────────────────────────


# ── C1: _run_scan triggers autodiscover() ─────────────────────────────────────


def test_corp_scan_calls_autodiscover(tmp_path):
    """A real scan must trigger module autodiscovery or MODULE_REGISTRY stays
    empty and the correlation engine runs with zero plugins."""
    from tddt.cli import main

    graph = _empty_graph()
    with (
        patch("tddt.cli.autodiscover") as mock_auto,
        patch("tddt.cli.CorrelationEngine") as MockEngine,
        patch("tddt.cli.export_json"),
        patch("tddt.cli.load_settings"),
        patch("tddt.cli.get_client"),
    ):
        MockEngine.return_value.scan.return_value = graph
        main(["corp", "example.com", "-o", str(tmp_path / "out.json")])
    mock_auto.assert_called()


def test_user_scan_calls_autodiscover(tmp_path):
    from tddt.cli import main

    graph = _empty_graph()
    with (
        patch("tddt.cli.autodiscover") as mock_auto,
        patch("tddt.cli.CorrelationEngine") as MockEngine,
        patch("tddt.cli.export_json"),
        patch("tddt.cli.load_settings"),
        patch("tddt.cli.get_client"),
    ):
        MockEngine.return_value.scan.return_value = graph
        main(["user", "--username", "foo", "-o", str(tmp_path / "out.json")])
    mock_auto.assert_called()


# ── C2: --format dispatches all exporters ─────────────────────────────────────


def test_format_json_dispatches_only_export_json(tmp_path):
    """Default -f rich,json fires export_json; md/html exporters stay silent."""
    from tddt.cli import main

    graph = _empty_graph()
    with (
        patch("tddt.cli.CorrelationEngine") as MockEngine,
        patch("tddt.cli.export_json") as mock_json,
        patch("tddt.cli.export_markdown") as mock_md,
        patch("tddt.cli.export_html") as mock_html,
        patch("tddt.cli.load_settings"),
        patch("tddt.cli.get_client"),
    ):
        MockEngine.return_value.scan.return_value = graph
        main(["corp", "example.com", "-o", str(tmp_path / "out.json")])
    assert mock_json.called
    assert not mock_md.called
    assert not mock_html.called


def test_format_json_md_html_dispatches_all_three(tmp_path):
    """-f json,md,html must dispatch to each exporter with a path matching the format."""
    from tddt.cli import main

    graph = _empty_graph()
    with (
        patch("tddt.cli.CorrelationEngine") as MockEngine,
        patch("tddt.cli.export_json") as mock_json,
        patch("tddt.cli.export_markdown") as mock_md,
        patch("tddt.cli.export_html") as mock_html,
        patch("tddt.cli.load_settings"),
        patch("tddt.cli.get_client"),
    ):
        MockEngine.return_value.scan.return_value = graph
        main(
            [
                "corp",
                "example.com",
                "-f",
                "json,md,html",
                "-o",
                str(tmp_path / "report.json"),
            ]
        )
    assert mock_json.called
    assert mock_md.called
    assert mock_html.called
    # Each exporter must get a path with the matching extension.
    md_path: Path = mock_md.call_args.args[2]
    html_path: Path = mock_html.call_args.args[2]
    assert md_path.suffix == ".md"
    assert html_path.suffix == ".html"


# ── C3: profile wiring ────────────────────────────────────────────────────────


def test_user_mode_passes_profile_to_export(tmp_path):
    """User scan calls build_profile(graph) and passes it as profile= to export_json."""
    from tddt.cli import main

    graph = _empty_graph()
    sentinel_profile = {"primary": {"services": []}, "alternates": []}
    with (
        patch("tddt.cli.CorrelationEngine") as MockEngine,
        patch("tddt.cli.export_json") as mock_export,
        patch("tddt.cli.load_settings"),
        patch("tddt.cli.get_client"),
        patch("tddt.cli.build_profile", return_value=sentinel_profile) as mock_build,
    ):
        MockEngine.return_value.scan.return_value = graph
        ret = main(["user", "--username", "foo", "-o", str(tmp_path / "out.json")])
    assert ret == 0
    assert mock_build.called
    call = mock_export.call_args
    assert call.kwargs.get("profile") == sentinel_profile


def test_corp_mode_does_not_build_profile(tmp_path):
    """Corporate scan does not call build_profile."""
    from tddt.cli import main

    graph = _empty_graph()
    with (
        patch("tddt.cli.CorrelationEngine") as MockEngine,
        patch("tddt.cli.export_json") as mock_export,
        patch("tddt.cli.load_settings"),
        patch("tddt.cli.get_client"),
        patch("tddt.cli.build_profile") as mock_build,
    ):
        MockEngine.return_value.scan.return_value = graph
        main(["corp", "example.com", "-o", str(tmp_path / "out.json")])
    assert not mock_build.called
    call = mock_export.call_args
    assert call.kwargs.get("profile") is None


# ── update-wmn-db ─────────────────────────────────────────────────────────────


def test_update_wmn_db_downloads_json(tmp_path):
    import json
    import responses
    from tddt.cli import main
    from tddt.core import http as http_module
    from tddt.core.config import Settings

    target_file = tmp_path / "wmn.json"
    dummy_payload = json.dumps({"sites": [{"name": "Site1"}, {"name": "Site2"}]})

    http_module.reset_client()
    no_cache_settings = Settings()
    no_cache_settings.cache_enabled = False

    with (
        responses.RequestsMock() as rsps,
        patch("tddt.cli._wmn_db_path", return_value=target_file),
        patch("tddt.cli.load_settings", return_value=no_cache_settings),
    ):
        rsps.add(
            responses.GET,
            "https://raw.githubusercontent.com/WebBreacher/WhatsMyName/main/wmn-data.json",
            body=dummy_payload,
            status=200,
        )
        ret = main(["update-wmn-db"])

    assert ret == 0
    assert target_file.is_file()
    assert "Site1" in target_file.read_text()


def test_update_wmn_db_uses_shared_http_client(tmp_path):
    """update-wmn-db must route through the shared HttpClient so --insecure,
    --proxy and cache settings apply. Bare `requests.get` bypasses all of that."""
    from tddt.cli import main
    from unittest.mock import MagicMock

    target_file = tmp_path / "wmn.json"
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b'{"sites": [{"name": "A"}]}'
    mock_resp.json.return_value = {"sites": [{"name": "A"}]}
    mock_client.get.return_value = mock_resp

    with (
        patch("tddt.cli._wmn_db_path", return_value=target_file),
        patch("tddt.cli.load_settings"),
        patch("tddt.cli.init_client", return_value=mock_client),
        patch("tddt.cli.get_client", return_value=mock_client),
    ):
        ret = main(["update-wmn-db"])

    assert ret == 0
    mock_client.get.assert_called_once()
    call_url = mock_client.get.call_args.args[0]
    assert "WhatsMyName" in call_url
    assert target_file.is_file()
    assert "A" in target_file.read_text()
