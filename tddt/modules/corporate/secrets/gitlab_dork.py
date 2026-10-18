"""GitLab public projects discovery module.

Searches public GitLab repositories and code for projects referencing
the target domain.
"""

from __future__ import annotations

from collections.abc import Iterable

from tddt.core.entity import BaseEntity, Domain, Secret, URL
from tddt.core.module import BaseModule, register_module


@register_module(
    name="corporate.secrets.gitlab_dork",
    mode=["corporate"],
    consumes=[Domain],
    produces=[Secret, URL],
    active=False,
    requires_key=None,
)
class GitlabDorkModule(BaseModule):
    """Searches GitLab for public projects referencing the domain."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Domain):
                continue
            domain = entity.value.strip().lower()

            url = "https://gitlab.com/api/v4/projects"
            params = {"search": domain, "per_page": 20}

            try:
                resp = self.client.get(url, params=params, host_hint="gitlab.com")
            except Exception:
                self.log.warning("gitlab_dork request failed for %s", domain, exc_info=True)
                continue

            if resp.status_code != 200:
                self.log.debug("gitlab_dork status %d for %s", resp.status_code, domain)
                continue

            try:
                projects = resp.json()
            except Exception:
                self.log.debug("gitlab_dork invalid JSON for %s", domain)
                continue

            if not isinstance(projects, list):
                continue

            seen: set[str] = set()
            for p in projects:
                if not isinstance(p, dict):
                    continue
                web_url = p.get("web_url", "").strip()
                if web_url and web_url not in seen:
                    seen.add(web_url)
                    yield URL(
                        value=web_url,
                        parent_id=entity.id,
                        source_module=self.name,
                        metadata={
                            "domain": domain,
                            "source": "gitlab_dork",
                            "name": p.get("name", ""),
                        },
                    )
