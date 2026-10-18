"""GitHub commit author email search module."""

from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import quote_plus

from tddt.core.entity import BaseEntity, Email, Service, Username
from tddt.core.module import BaseModule, register_module


@register_module(
    name="user.email.github_commit_search",
    mode=["user"],
    consumes=[Email],
    produces=[Username, Service],
    active=False,
    requires_key=None,
)
class GithubCommitSearchModule(BaseModule):
    """Searches GitHub public commits to uncover usernames and profiles linked to an email."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Email):
                continue

            email_val = entity.value.strip().lower()
            token = getattr(self.settings, "github", "") or getattr(
                self.settings, "github_token", ""
            )
            headers = {"Accept": "application/vnd.github.cloak-preview+json"}
            if token:
                headers["Authorization"] = f"token {token}"

            url = f"https://api.github.com/search/commits?q={quote_plus(f'author-email:{email_val}')}"

            try:
                resp = self.client.get(
                    url, headers=headers, host_hint="api.github.com", timeout=12
                )
            except Exception:
                self.log.debug("GitHub commit search failed for %s", email_val, exc_info=True)
                continue

            if resp.status_code != 200:
                self.log.debug("GitHub commit search returned %d for %s", resp.status_code, email_val)
                continue

            try:
                data = resp.json()
            except Exception:
                self.log.debug("Failed decoding GitHub commits JSON for %s", email_val, exc_info=True)
                continue

            discovered_logins: set[str] = set()
            for item in data.get("items", []):
                author = item.get("author")
                if isinstance(author, dict):
                    login = author.get("login")
                    if login:
                        discovered_logins.add(login)

            for login in sorted(discovered_logins):
                yield Username(
                    value=login,
                    parent_id=entity.id,
                    source_module=self.name,
                    confidence=0.85,
                    metadata={"source": "github_commits", "email": email_val},
                )
                yield Service(
                    value=f"GitHub:{login}",
                    parent_id=entity.id,
                    source_module=self.name,
                    confidence=0.85,
                    metadata={"site": "GitHub", "username": login, "url": f"https://github.com/{login}"},
                )
