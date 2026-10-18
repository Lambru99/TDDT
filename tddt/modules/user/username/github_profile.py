"""GitHub public user profile and commit email scraper module."""

from __future__ import annotations

from collections.abc import Iterable

from tddt.core.entity import BaseEntity, Email, FullName, Organization, Username, Website
from tddt.core.module import BaseModule, register_module


@register_module(
    name="user.username.github_profile",
    mode=["user"],
    consumes=[Username],
    produces=[Email, Website, FullName, Organization],
    active=False,
    requires_key=None,
)
class GithubProfileModule(BaseModule):
    """Scrapes public GitHub user profiles, extracting name, company, site, and email."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Username):
                continue

            username = entity.value.strip().lower()
            token = getattr(self.settings, "github", "") or getattr(
                self.settings, "github_token", ""
            )
            headers = {"Accept": "application/vnd.github.v3+json"}
            if token:
                headers["Authorization"] = f"token {token}"

            url = f"https://api.github.com/users/{username}"
            try:
                resp = self.client.get(
                    url, headers=headers, host_hint="api.github.com", timeout=12
                )
            except Exception:
                self.log.debug("GitHub profile query failed for %s", username, exc_info=True)
                continue

            if resp.status_code != 200:
                self.log.debug("GitHub profile returned %d for %s", resp.status_code, username)
                continue

            try:
                profile = resp.json()
            except Exception:
                self.log.debug("Failed decoding GitHub profile JSON for %s", username, exc_info=True)
                continue

            name = profile.get("name")
            if name:
                yield FullName(
                    value=str(name).strip(),
                    parent_id=entity.id,
                    source_module=self.name,
                    confidence=0.8,
                    metadata={"source": "github_profile", "username": username},
                )

            company = profile.get("company")
            if company:
                clean_co = str(company).lstrip("@").strip()
                if clean_co:
                    yield Organization(
                        value=clean_co,
                        parent_id=entity.id,
                        source_module=self.name,
                        confidence=0.7,
                        metadata={"source": "github_profile", "username": username},
                    )

            blog = profile.get("blog")
            if blog:
                blog_str = str(blog).strip()
                if not blog_str.startswith("http"):
                    blog_str = f"https://{blog_str}"
                yield Website(
                    value=blog_str,
                    parent_id=entity.id,
                    source_module=self.name,
                    confidence=0.8,
                    metadata={"source": "github_profile", "username": username},
                )

            email_found = profile.get("email")
            if email_found:
                yield Email(
                    value=str(email_found).strip().lower(),
                    parent_id=entity.id,
                    source_module=self.name,
                    confidence=0.9,
                    metadata={"source": "github_profile", "username": username},
                )
            else:
                # Fallback to events API for commit emails
                events_url = f"https://api.github.com/users/{username}/events/public"
                try:
                    ev_resp = self.client.get(
                        events_url, headers=headers, host_hint="api.github.com", timeout=10
                    )
                    if ev_resp.status_code == 200:
                        events = ev_resp.json()
                        discovered_emails: set[str] = set()
                        if isinstance(events, list):
                            for event in events:
                                if event.get("type") == "PushEvent":
                                    payload = event.get("payload", {})
                                    for commit in payload.get("commits", []):
                                        author = commit.get("author", {})
                                        em = author.get("email", "").lower().strip()
                                        if em and "noreply.github.com" not in em:
                                            discovered_emails.add(em)
                        for em in sorted(discovered_emails):
                            yield Email(
                                value=em,
                                parent_id=entity.id,
                                source_module=self.name,
                                confidence=0.8,
                                metadata={"source": "github_events_commit", "username": username},
                            )
                except Exception:
                    self.log.debug("GitHub events email lookup failed for %s", username, exc_info=True)
