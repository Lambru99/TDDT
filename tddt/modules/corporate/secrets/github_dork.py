"""GitHub code search secret discovery module.

Searches GitHub code for public repositories leaking configuration files,
tokens, or secrets referencing the target domain.
Honors optional GitHub API token in settings.github.
"""

from __future__ import annotations

from collections.abc import Iterable

from tddt.core.entity import BaseEntity, Domain, Secret, URL
from tddt.core.module import BaseModule, register_module


@register_module(
    name="corporate.secrets.github_dork",
    mode=["corporate"],
    consumes=[Domain],
    produces=[Secret, URL],
    active=False,
    requires_key=None,
)
class GithubDorkModule(BaseModule):
    """Searches GitHub code for leaks associated with the domain."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Domain):
                continue
            domain = entity.value.strip().lower()

            url = "https://api.github.com/search/code"
            params = {"q": f"{domain} filename:.env"}
            headers = {"Accept": "application/vnd.github.v3+json"}
            token = getattr(self.settings, "github", None)
            if token:
                headers["Authorization"] = f"token {token}"

            try:
                resp = self.client.get(
                    url,
                    params=params,
                    headers=headers,
                    host_hint="api.github.com",
                )
            except Exception:
                self.log.warning("github_dork request failed for %s", domain, exc_info=True)
                continue

            if resp.status_code == 403:
                self.log.warning(
                    "GitHub API rate limit (403) reached for %s; consider setting GITHUB_API_KEY in .env",
                    domain,
                )
                continue

            if resp.status_code != 200:
                self.log.debug("github_dork status %d for %s", resp.status_code, domain)
                continue

            try:
                data = resp.json()
            except Exception:
                self.log.debug("github_dork invalid JSON for %s", domain)
                continue

            items = data.get("items", [])
            seen: set[str] = set()
            for item in items:
                if not isinstance(item, dict):
                    continue
                html_url = item.get("html_url", "").strip()
                if html_url and html_url not in seen:
                    seen.add(html_url)
                    yield URL(
                        value=html_url,
                        parent_id=entity.id,
                        source_module=self.name,
                        metadata={
                            "domain": domain,
                            "source": "github_dork",
                            "repo": item.get("repository", {}).get("full_name", ""),
                        },
                    )
