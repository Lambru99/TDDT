"""GitHub code search module for email discovery."""

from __future__ import annotations

from collections.abc import Iterable

from tddt.core.entity import BaseEntity, Domain, Email
from tddt.core.module import BaseModule, register_module
from tddt.modules.corporate.email import extract_domain_emails


@register_module(
    name="corporate.email.github_search",
    mode=["corporate"],
    consumes=[Domain],
    produces=[Email],
    active=False,
    requires_key=None,
)
class GithubSearchModule(BaseModule):
    """Searches GitHub public code for email addresses belonging to domain."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Domain):
                continue

            domain = entity.value.strip().lower()
            token = getattr(self.settings, "github", "") or getattr(
                self.settings, "github_token", ""
            )

            headers = {
                "Accept": "application/vnd.github.v3+json",
            }
            if token:
                headers["Authorization"] = f"token {token}"

            url = "https://api.github.com/search/code"
            params = {"q": f'"{domain}" in:file', "per_page": 30}

            try:
                resp = self.client.get(
                    url, params=params, headers=headers, host_hint="api.github.com", timeout=15
                )
            except Exception:
                self.log.debug("GitHub code search request failed for %s", domain, exc_info=True)
                continue

            if resp.status_code in (403, 429):
                if not token:
                    self.log.warning(
                        "GitHub code search rate limit reached (unauthenticated 10 req/min cap) for %s",
                        domain,
                    )
                else:
                    self.log.warning(
                        "GitHub code search returned status %d for %s (rate limit)",
                        resp.status_code,
                        domain,
                    )
                continue

            if resp.status_code != 200:
                self.log.debug("GitHub code search returned status %d for %s", resp.status_code, domain)
                continue

            try:
                data = resp.json()
            except Exception:
                self.log.debug("Failed to decode GitHub search JSON for %s", domain, exc_info=True)
                continue

            emails: set[str] = set()
            for item in data.get("items", []):
                html_url = item.get("html_url", "")
                raw_url = html_url.replace("github.com", "raw.githubusercontent.com").replace(
                    "/blob/", "/"
                )
                if not raw_url:
                    continue
                try:
                    raw_resp = self.client.get(raw_url, host_hint="raw.githubusercontent.com", timeout=10)
                    if raw_resp.status_code == 200:
                        emails.update(extract_domain_emails(raw_resp.text, domain))
                except Exception:
                    self.log.debug("Failed to fetch raw file %s", raw_url, exc_info=True)

            for email in sorted(emails):
                yield Email(
                    value=email,
                    parent_id=entity.id,
                    source_module=self.name,
                    metadata={"source": "github_search", "domain": domain},
                )
