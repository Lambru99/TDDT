"""Subdomain takeover verification module.

Fixes bug §2.2: does NOT rely only on CNAME pattern matching. Actively probes
the CNAME target and matches against verified error fingerprints (unclaimed
buckets, deleted apps, unregistered pages) to confirm actual takeover vulnerabilities.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from tddt.core.entity import BaseEntity, DNSRecord, TakeoverFinding
from tddt.core.module import BaseModule, register_module

TAKEOVER_FINGERPRINTS = {
    "GitHub Pages": {
        "cname": [r"\.github\.io$"],
        "fingerprints": ["There isn't a GitHub Pages site here"],
    },
    "Heroku": {
        "cname": [r"\.herokuapp\.com$"],
        "fingerprints": ["No such app", "herokucdn.com/error-pages/no-such-app.html"],
    },
    "AWS S3": {
        "cname": [r"\.s3\.amazonaws\.com$", r"\.s3-website[.-]"],
        "fingerprints": ["The specified bucket does not exist", "<Code>NoSuchBucket</Code>"],
    },
    "Zendesk": {
        "cname": [r"\.zendesk\.com$"],
        "fingerprints": ["Help Center Closed", "No such help center"],
    },
    "Shopify": {
        "cname": [r"\.myshopify\.com$"],
        "fingerprints": ["Sorry, this shop is currently unavailable."],
    },
    "Fastly": {
        "cname": [r"\.fastly\.net$", r"\.fastlylb\.net$"],
        "fingerprints": ["Fastly error: unknown domain"],
    },
    "Surge": {
        "cname": [r"\.surge\.sh$"],
        "fingerprints": ["project not found"],
    },
    "Readme.io": {
        "cname": [r"\.readme\.io$"],
        "fingerprints": ["Project doesnt exist... yet!"],
    },
    "Bitbucket": {
        "cname": [r"\.bitbucket\.io$"],
        "fingerprints": ["Repository not found"],
    },
    "Pingdom": {
        "cname": [r"\.pingdom\.net$"],
        "fingerprints": ["Pingdom | Public Report", "Public Report Not Found"],
    },
}


@register_module(
    name="corporate.web.takeover_verifier",
    mode=["corporate"],
    consumes=[DNSRecord],
    produces=[TakeoverFinding],
    active=True,
    requires_key=None,
)
class TakeoverVerifierModule(BaseModule):
    """Actively verifies CNAME records for takeover vulnerabilities."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, DNSRecord):
                continue
            if entity.metadata.get("type") != "CNAME":
                continue

            cname = entity.metadata.get("record", "").strip().rstrip(".").lower()
            subdomain = entity.metadata.get("domain", "").strip().rstrip(".").lower()
            if not cname or not subdomain:
                continue

            matched_service = None
            service_fingerprints = []
            for service, conf in TAKEOVER_FINGERPRINTS.items():
                for pat in conf["cname"]:
                    if re.search(pat, cname, re.IGNORECASE):
                        matched_service = service
                        service_fingerprints = conf["fingerprints"]
                        break
                if matched_service:
                    break

            if not matched_service:
                continue

            # Active probe: fetch subdomain to check for fingerprint
            response_body = ""
            for proto in ("https", "http"):
                try:
                    resp = self.client.get(f"{proto}://{subdomain}", timeout=5)
                    response_body = resp.text
                    if response_body:
                        break
                except Exception:
                    self.log.debug("takeover_verifier probe failed for %s://%s", proto, subdomain)

            if not response_body:
                continue

            for fp in service_fingerprints:
                if fp in response_body:
                    self.log.warning(
                        "SUBDOMAIN TAKEOVER CONFIRMED: %s -> %s (%s)",
                        subdomain,
                        cname,
                        matched_service,
                    )
                    yield TakeoverFinding(
                        value=f"{subdomain}:{matched_service}",
                        parent_id=entity.id,
                        source_module=self.name,
                        metadata={
                            "subdomain": subdomain,
                            "cname": cname,
                            "service": matched_service,
                            "fingerprint": fp,
                            "severity": "critical",
                        },
                    )
                    break
