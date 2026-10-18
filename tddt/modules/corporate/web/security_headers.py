"""Security headers evaluation module.

Analyzes HTTP response headers to identify missing or insecure security
headers (HSTS, CSP, X-Frame-Options, X-Content-Type-Options, etc.).
Produces Finding entities.
"""

from __future__ import annotations

from collections.abc import Iterable

from tddt.core.entity import BaseEntity, Finding, URL
from tddt.core.module import BaseModule, register_module

RECOMMENDED_HEADERS: dict[str, str] = {
    "Strict-Transport-Security": "Protects against SSL stripping and man-in-the-middle attacks.",
    "Content-Security-Policy": "Mitigates Cross-Site Scripting (XSS) and data injection attacks.",
    "X-Frame-Options": "Protects against clickjacking attacks by controlling frame embedding.",
    "X-Content-Type-Options": "Prevents MIME-type sniffing vulnerabilities.",
    "Referrer-Policy": "Controls how much referrer information is included with requests.",
    "Permissions-Policy": "Controls browser features and APIs available to the page.",
}


@register_module(
    name="corporate.web.security_headers",
    mode=["corporate"],
    consumes=[URL],
    produces=[Finding],
    active=False,
    requires_key=None,
)
class SecurityHeadersModule(BaseModule):
    """Checks for recommended HTTP security headers."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, URL):
                continue

            headers: dict[str, str] = entity.metadata.get("headers", {})
            if not headers:
                try:
                    resp = self.client.get(entity.value)
                    headers = dict(resp.headers)
                except Exception:
                    self.log.debug("security_headers: failed to fetch headers for %s", entity.value)
                    continue

            low_headers = {k.lower(): v for k, v in headers.items()}

            for header, desc in RECOMMENDED_HEADERS.items():
                if header.lower() not in low_headers:
                    yield Finding(
                        value=f"{entity.value}:missing_header:{header}",
                        parent_id=entity.id,
                        source_module=self.name,
                        metadata={
                            "type": "missing_security_header",
                            "header": header,
                            "description": desc,
                            "severity": "low",
                            "url": entity.value,
                        },
                    )
