from __future__ import annotations

import pytest
import responses

from tddt.core.config import Settings
from tddt.core.entity import Secret, URL
from tddt.core.http import HttpClient
from tddt.modules.corporate.secrets.js_secrets import JsSecretsModule, shannon_entropy


@pytest.fixture
def http_client(tmp_path):
    s = Settings(cache_enabled=False)
    return HttpClient(s, cache_path=tmp_path / "cache.sqlite")


def test_shannon_entropy():
    # Low entropy repeating strings
    assert shannon_entropy("aaaaaaaaaaaa") < 1.0
    assert shannon_entropy("placeholder") < 3.5
    # High entropy strings (random tokens/keys)
    assert shannon_entropy("AKIAIOSFODNN7EXAMPLE") >= 3.5
    assert shannon_entropy("c2VjcmV0X3Rva2VuX3dpdGhfcmFuZG9tX2NoYXJzXzEyMzQ1") >= 3.5


@responses.activate
def test_js_secrets_placeholder_rejected_real_key_accepted(http_client):
    """Bug §2.10: placeholder password yields ZERO secrets; real AWS key yields ONE secret."""
    page_url = "https://app.example.com"
    html = """
    <html>
      <head>
        <script src="/static/bundle.js"></script>
        <script src="https://evilexample.com.attacker.site/malicious.js"></script>
      </head>
      <body></body>
    </html>
    """
    js_content = """
    const config = {
      password: "placeholder",
      dev_key: "your-key-here",
      test_user: "demo",
      aws_key: "AKIAIOSFODNN7EXAMPLE"
    };
    """
    responses.add(responses.GET, page_url, body=html, status=200)
    responses.add(responses.GET, "https://app.example.com/static/bundle.js", body=js_content, status=200)

    mod = JsSecretsModule(http_client, Settings())
    url_ent = URL(
        value=page_url,
        metadata={"domain": "example.com", "body": html},
    )
    results = list(mod.run([url_ent]))

    secrets = [r for r in results if isinstance(r, Secret)]
    # Exactly ONE secret (the AWS Access Key), placeholders rejected
    assert len(secrets) == 1
    assert "AKIAIOSFODNN7" in secrets[0].value
    assert secrets[0].metadata["type"] == "AWS Access Key"

    # Verify strict netloc: evilexample.com.attacker.site was NOT requested!
    requested_urls = [call.request.url for call in responses.calls]
    assert not any("attacker.site" in u for u in requested_urls)


def test_js_secrets_deny_list(http_client):
    mod = JsSecretsModule(http_client, Settings())
    assert mod.is_denied("placeholder") is True
    assert mod.is_denied("your-key") is True
    assert mod.is_denied("changeme") is True
    assert mod.is_denied("AKIAIOSFODNN7EXAMPLE") is False
