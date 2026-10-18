"""Wappalyzer-like technology fingerprinting module.

Consumes URL entities and analyzes headers, HTML body, scripts, and meta tags
to identify running technologies.
Fixes bug §2.secondary: reuses response captured in URL metadata from http_inspector,
making ZERO additional outbound requests when cached metadata is present.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from bs4 import BeautifulSoup

from tddt.core.entity import BaseEntity, Technology, URL
from tddt.core.module import BaseModule, register_module

SIGNATURES: dict[str, dict[str, list[str] | dict[str, str]]] = {
    # CMS & Platforms
    "WordPress": {
        "html": [r"/wp-content/", r"/wp-includes/"],
        "meta": [r'name=["\']generator["\'].*WordPress'],
    },
    "Drupal": {
        "html": [r"/sites/default/files/", r"Drupal\.settings"],
        "header": {"X-Generator": r"Drupal"},
    },
    "Joomla": {
        "html": [r"/components/com_", r"Joomla!"],
        "meta": [r'name=["\']generator["\'].*Joomla'],
    },
    "Shopify": {
        "html": [r"Shopify\.theme", r"cdn\.shopify\.com"],
    },
    "Magento": {
        "html": [r"Mage\.", r"/skin/frontend/", r"Magento"],
    },
    "Ghost": {
        "meta": [r'name=["\']generator["\'].*Ghost'],
    },
    # Frontend Frameworks & Libraries
    "React": {
        "html": [r"__reactFiber", r"data-reactroot", r"_reactListening"],
        "script_src": [r"react\.min\.js", r"react-dom", r"chunk\.js"],
    },
    "Next.js": {
        "html": [r"/_next/static/", r"__NEXT_DATA__"],
    },
    "Vue.js": {
        "html": [r"__vue_app__", r"data-v-", r"v-bind:", r"v-model="],
        "script_src": [r"vue\.min\.js", r"vue\.js"],
    },
    "Angular": {
        "html": [r"ng-version=", r"ng-app=", r"ng-controller="],
        "script_src": [r"angular\.min\.js", r"angular\.js"],
    },
    "jQuery": {
        "html": [r"jquery\.min\.js", r"jquery\.js", r"jQuery\("],
        "script_src": [r"jquery[.-]"],
    },
    # Web Servers & Proxies
    "nginx": {
        "header": {"Server": r"nginx"},
    },
    "Apache": {
        "header": {"Server": r"Apache"},
    },
    "Microsoft-IIS": {
        "header": {"Server": r"Microsoft-IIS"},
    },
    "Cloudflare": {
        "header": {"Server": r"cloudflare", "cf-ray": r"."},
    },
    "LiteSpeed": {
        "header": {"Server": r"LiteSpeed"},
    },
    # Backend Languages & Runtimes
    "PHP": {
        "header": {"X-Powered-By": r"PHP"},
        "cookie": [r"PHPSESSID"],
    },
    "ASP.NET": {
        "header": {"X-Powered-By": r"ASP\.NET", "X-AspNet-Version": r"."},
        "cookie": [r"ASP\.NET_SessionId"],
    },
    "Express": {
        "header": {"X-Powered-By": r"Express"},
    },
}


@register_module(
    name="corporate.web.tech_fingerprint",
    mode=["corporate"],
    consumes=[URL],
    produces=[Technology],
    active=False,
    requires_key=None,
)
class TechFingerprintModule(BaseModule):
    """Detects technologies from HTTP headers and HTML markup."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, URL):
                continue

            headers: dict[str, str] = entity.metadata.get("headers", {})
            body: str = entity.metadata.get("body", "")

            # If headers and body are absent from metadata, fetch via client
            if not headers and not body:
                try:
                    resp = self.client.get(entity.value)
                    headers = dict(resp.headers)
                    body = resp.text
                except Exception:
                    self.log.debug("tech_fingerprint failed to fetch %s", entity.value)
                    continue

            # Parse HTML for meta tags and scripts if body is present
            meta_tags: list[str] = []
            generator_contents: list[str] = []
            script_srcs: list[str] = []
            if body:
                try:
                    soup = BeautifulSoup(body, "html.parser")
                    for meta in soup.find_all("meta"):
                        meta_tags.append(str(meta))
                        if meta.get("name", "").lower() == "generator":
                            generator_contents.append(meta.get("content", ""))
                    for script in soup.find_all("script", src=True):
                        src = script.get("src")
                        if src:
                            script_srcs.append(src)
                except Exception:
                    self.log.debug("HTML parse failed during tech fingerprinting for %s", entity.value)

            matched_techs: set[str] = set()

            for tech_name, rules in SIGNATURES.items():
                is_match = False

                # 1. Header checks
                header_rules = rules.get("header")
                if isinstance(header_rules, dict):
                    for hdr_name, pattern in header_rules.items():
                        # Case-insensitive header lookup
                        hdr_val = next(
                            (v for k, v in headers.items() if k.lower() == hdr_name.lower()), ""
                        )
                        if hdr_val and re.search(pattern, hdr_val, re.IGNORECASE):
                            is_match = True
                            break

                # 2. HTML body pattern checks
                if not is_match and body:
                    html_rules = rules.get("html")
                    if isinstance(html_rules, list):
                        for pattern in html_rules:
                            if re.search(pattern, body, re.IGNORECASE):
                                is_match = True
                                break

                # 3. Meta tag checks
                if not is_match and meta_tags:
                    meta_rules = rules.get("meta")
                    if isinstance(meta_rules, list):
                        for pattern in meta_rules:
                            # Check against raw body, tag string, or generator content
                            if (
                                any(re.search(pattern, m, re.IGNORECASE) for m in meta_tags)
                                or (body and re.search(pattern, body, re.IGNORECASE))
                                or any(re.search(pattern, g, re.IGNORECASE) for g in generator_contents)
                            ):
                                is_match = True
                                break

                # 4. Script src checks
                if not is_match and script_srcs:
                    script_rules = rules.get("script_src")
                    if isinstance(script_rules, list):
                        for pattern in script_rules:
                            if any(re.search(pattern, s, re.IGNORECASE) for s in script_srcs):
                                is_match = True
                                break

                # 5. Cookie checks
                if not is_match:
                    cookie_rules = rules.get("cookie")
                    if isinstance(cookie_rules, list):
                        set_cookie = headers.get("Set-Cookie", "")
                        for pattern in cookie_rules:
                            if re.search(pattern, set_cookie, re.IGNORECASE):
                                is_match = True
                                break

                if is_match and tech_name not in matched_techs:
                    matched_techs.add(tech_name)
                    yield Technology(
                        value=tech_name,
                        parent_id=entity.id,
                        source_module=self.name,
                        metadata={"url": entity.value},
                    )
