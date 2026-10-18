"""GitLab public user profile scraper module."""

from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import quote_plus

from tddt.core.entity import BaseEntity, Email, Username, Website
from tddt.core.module import BaseModule, register_module


@register_module(
    name="user.username.gitlab_profile",
    mode=["user"],
    consumes=[Username],
    produces=[Email, Website],
    active=False,
    requires_key=None,
)
class GitlabProfileModule(BaseModule):
    """Scrapes public GitLab user profiles for public emails and website URLs."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Username):
                continue

            username = entity.value.strip().lower()
            url = f"https://gitlab.com/api/v4/users?username={quote_plus(username)}"

            try:
                resp = self.client.get(url, host_hint="gitlab.com", timeout=12)
            except Exception:
                self.log.debug("GitLab profile query failed for %s", username, exc_info=True)
                continue

            if resp.status_code != 200:
                self.log.debug("GitLab profile returned status %d for %s", resp.status_code, username)
                continue

            try:
                users = resp.json()
            except Exception:
                self.log.debug("Failed decoding GitLab users JSON for %s", username, exc_info=True)
                continue

            if isinstance(users, list) and users:
                user_info = users[0]
                pub_email = user_info.get("public_email")
                if pub_email:
                    yield Email(
                        value=str(pub_email).strip().lower(),
                        parent_id=entity.id,
                        source_module=self.name,
                        confidence=0.9,
                        metadata={"source": "gitlab_profile", "username": username},
                    )

                web_url = user_info.get("website_url")
                if web_url:
                    clean_url = str(web_url).strip()
                    if not clean_url.startswith("http"):
                        clean_url = f"https://{clean_url}"
                    yield Website(
                        value=clean_url,
                        parent_id=entity.id,
                        source_module=self.name,
                        confidence=0.8,
                        metadata={"source": "gitlab_profile", "username": username},
                    )
