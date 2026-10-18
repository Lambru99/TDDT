"""JavaScript secrets crawler and scanner module.

Crawls linked JS files on discovered pages looking for leaked credentials,
API keys, tokens, endpoints, and internal email addresses.
Fixes bug §2.10:
  - Shannon entropy threshold (>= 3.5) on extracted secrets.
  - Deny-list filter for dummy / placeholder values.
  - Strict netloc comparison (domain or subdomain) to prevent following attacker domains.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from tddt.core.entity import BaseEntity, Email, Secret, URL
from tddt.core.module import BaseModule, register_module

DENY_PLACEHOLDERS = {
    "xxxxx",
    "your-key",
    "your-key-here",
    "example",
    "null",
    "undefined",
    "placeholder",
    "changeme",
    "test",
    "demo",
    "password",
    "secret",
}

SECRET_PATTERNS = {
    "AWS Access Key": r"AKIA[0-9A-Z]{16}",
    "AWS Secret Key": r"(?i)aws.{0,20}secret.{0,20}['\"]([A-Za-z0-9+/]{40})",
    "Google API Key": r"AIza[0-9A-Za-z\-_]{35}",
    "Google OAuth": r"[0-9]+-[0-9A-Za-z_]{32}\.apps\.googleusercontent\.com",
    "JWT Token": r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}",
    "Bearer Token": r"(?i)bearer\s+([A-Za-z0-9\-._~+/]{20,})",
    "Password in code": r"(?i)(?:password|passwd|pwd)\s*[:=]\s*['\"]([^'\"]{6,})['\"]",
    "Secret in code": r"(?i)(?:secret|api_secret|client_secret)\s*[:=]\s*['\"]([^'\"]{8,})['\"]",
    "Token in code": r"(?i)(?:token|access_token|auth_token)\s*[:=]\s*['\"]([^'\"]{8,})['\"]",
    "Stripe Live Key": r"sk_live_[0-9a-zA-Z]{24}",
    "GitHub Token": r"ghp_[A-Za-z0-9]{36}",
    "Slack Token": r"xox[baprs]-[0-9A-Za-z]{10,48}",
    "Twilio Account SID": r"AC[a-z0-9]{32}",
    "SendGrid API Key": r"SG\.[A-Za-z0-9\-_]{22}\.[A-Za-z0-9\-_]{43}",
    "Mailgun API Key": r"key-[0-9a-zA-Z]{32}",
    "Private Key Header": r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
}

ENDPOINT_PATTERNS = [
    r"['\"](/api/[^'\"?\s]{3,})",
    r"['\"](/v\d+/[^'\"?\s]{3,})",
    r"['\"](/internal/[^'\"?\s]{3,})",
    r"['\"](/admin/[^'\"?\s]{3,})",
    r"['\"](/graphql[^'\"?\s]*)",
    r"['\"](/swagger[^'\"?\s]*)",
    r"['\"](/debug[^'\"?\s]*)",
    r"['\"](/_[^'\"?\s]{3,})",
]

EMAIL_REGEX = r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"


def shannon_entropy(s: str) -> float:
    """Calculate Shannon entropy of a string."""
    if not s:
        return 0.0
    counts = Counter(s)
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


@register_module(
    name="corporate.secrets.js_secrets",
    mode=["corporate"],
    consumes=[URL],
    produces=[Secret, URL, Email],
    active=False,
    requires_key=None,
)
class JsSecretsModule(BaseModule):
    """Scans JavaScript files and page bodies for exposed secrets and endpoints."""

    def is_denied(self, val: str) -> bool:
        low = val.lower().strip()
        if low in DENY_PLACEHOLDERS:
            return True
        if any(low.startswith(p) for p in ("your-key", "xxxxx")):
            return True
        return False

    def _scan_text(
        self, text: str, source_url: str, domain: str, parent_id: str
    ) -> list[BaseEntity]:
        discovered: list[BaseEntity] = []

        # 1. Secrets
        for name, pattern in SECRET_PATTERNS.items():
            matches = re.findall(pattern, text)
            for m in matches:
                secret_str = m if isinstance(m, str) else m[0]
                secret_str = secret_str.strip()
                if not secret_str or self.is_denied(secret_str):
                    continue
                # Entropy verification
                if name != "Private Key Header" and shannon_entropy(secret_str) < 3.5:
                    continue
                discovered.append(
                    Secret(
                        value=secret_str,
                        parent_id=parent_id,
                        source_module=self.name,
                        metadata={"type": name, "source_url": source_url},
                    )
                )

        # 2. Hidden endpoints
        for pattern in ENDPOINT_PATTERNS:
            for ep in re.findall(pattern, text):
                if isinstance(ep, str) and ep.startswith("/"):
                    full_url = urljoin(source_url, ep)
                    discovered.append(
                        URL(
                            value=full_url,
                            parent_id=parent_id,
                            source_module=self.name,
                            metadata={"discovered_in": source_url, "endpoint": ep},
                        )
                    )

        # 3. Emails
        for e in re.findall(EMAIL_REGEX, text):
            low_e = e.lower().strip()
            if domain and low_e.endswith("@" + domain):
                discovered.append(
                    Email(
                        value=low_e,
                        parent_id=parent_id,
                        source_module=self.name,
                        metadata={"source_url": source_url},
                    )
                )

        return discovered

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, URL):
                continue

            page_url = entity.value
            domain = entity.metadata.get("domain", "")
            if not domain:
                parsed_root = urlparse(page_url)
                domain = (parsed_root.hostname or "").strip().lower()

            body: str = entity.metadata.get("body", "")
            if not body:
                try:
                    resp = self.client.get(page_url)
                    body = resp.text
                except Exception:
                    self.log.debug("js_secrets failed to fetch %s", page_url)
                    continue

            # Scan the page itself
            for res in self._scan_text(body, page_url, domain, entity.id):
                yield res

            # Extract script links
            js_urls: list[str] = []
            try:
                soup = BeautifulSoup(body, "html.parser")
                for tag in soup.find_all("script", src=True):
                    src = tag["src"].strip()
                    if src:
                        absolute = urljoin(page_url, src)
                        parsed = urlparse(absolute)
                        netloc = (parsed.hostname or "").strip().lower()
                        # Strict netloc match: netloc == domain or netloc.endswith("." + domain)
                        if domain and (netloc == domain or netloc.endswith("." + domain)):
                            js_urls.append(absolute)
            except Exception:
                self.log.debug("Failed to extract scripts from %s", page_url)

            # Scan up to 10 linked JS files
            for js_url in js_urls[:10]:
                try:
                    js_resp = self.client.get(js_url)
                    if js_resp.status_code == 200 and js_resp.text:
                        for res in self._scan_text(js_resp.text, js_url, domain, entity.id):
                            yield res
                except Exception:
                    self.log.debug("Failed to fetch JS file %s", js_url)
