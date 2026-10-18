"""GitLab project search module for email discovery."""

from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import quote_plus

from tddt.core.entity import BaseEntity, Domain, Email
from tddt.core.module import BaseModule, register_module
from tddt.modules.corporate.email import extract_domain_emails


@register_module(
    name="corporate.email.gitlab_search",
    mode=["corporate"],
    consumes=[Domain],
    produces=[Email],
    active=False,
    requires_key=None,
)
class GitlabSearchModule(BaseModule):
    """Searches GitLab public projects for emails associated with the domain."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Domain):
                continue

            domain = entity.value.strip().lower()
            url = f"https://gitlab.com/api/v4/projects?search={quote_plus(domain)}"

            try:
                resp = self.client.get(url, host_hint="gitlab.com", timeout=15)
            except Exception:
                self.log.debug("GitLab search request failed for %s", domain, exc_info=True)
                continue

            if resp.status_code in (403, 429):
                self.log.warning(
                    "GitLab search returned status %d for %s (forbidden / rate limit)",
                    resp.status_code,
                    domain,
                )
                continue
            if resp.status_code != 200:
                self.log.debug("GitLab search returned status %d for %s", resp.status_code, domain)
                continue

            emails: set[str] = set()
            try:
                data = resp.json()
                if isinstance(data, list):
                    for proj in data:
                        if isinstance(proj, dict):
                            desc = proj.get("description") or ""
                            name = proj.get("name") or ""
                            emails.update(extract_domain_emails(f"{name}\n{desc}", domain))
            except Exception:
                emails.update(extract_domain_emails(resp.text, domain))

            for email in sorted(emails):
                yield Email(
                    value=email,
                    parent_id=entity.id,
                    source_module=self.name,
                    metadata={"source": "gitlab_search", "domain": domain},
                )
