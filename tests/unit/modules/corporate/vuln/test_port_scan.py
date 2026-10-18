"""Tests for vuln.port_scan module."""

from unittest.mock import MagicMock, patch
import pytest

from tddt.core.config import Settings
from tddt.core.entity import IPAddress, Port
from tddt.core.http import HttpClient
from tddt.modules.corporate.vuln.port_scan import PortScanModule


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


def test_port_scan_active_attribute(http_client):
    mod = PortScanModule(http_client, Settings())
    assert mod.active is True


def test_port_scan_finds_open_ports(http_client):
    mod = PortScanModule(http_client, Settings())
    ip = IPAddress(value="192.168.1.10")

    def mock_connect_ex(addr):
        host, port = addr
        if port in (80, 443):
            return 0  # open
        return 111  # connection refused

    mock_socket_instance = MagicMock()
    mock_socket_instance.connect_ex.side_effect = mock_connect_ex

    with patch("socket.socket", return_value=mock_socket_instance):
        entities = list(mod._probe_ports(ip, [22, 80, 443, 8080]))

    ports = [e for e in entities if isinstance(e, Port)]
    port_vals = {p.value for p in ports}
    assert port_vals == {"80", "443"}
    assert all(p.metadata.get("verified") is True for p in ports)
    assert all(p.confidence == 1.0 for p in ports)
