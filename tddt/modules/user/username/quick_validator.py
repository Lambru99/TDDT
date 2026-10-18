"""Username quick validator bootstrap module (FP killer)."""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable

from tddt.core.entity import BaseEntity, Username
from tddt.core.module import BaseModule, register_module


@register_module(
    name="user.username.quick_validator",
    mode=["user"],
    consumes=[Username],
    produces=[Username],
    min_confidence=0.3,
    active=False,
    requires_key=None,
)
class QuickValidatorModule(BaseModule):
    """Probes top 5 platforms to promote genuine candidates and degrade false positives."""

    def _check_platform(self, username: str, site_name: str) -> bool:
        try:
            if site_name == "github":
                resp = self.client.get(
                    f"https://api.github.com/users/{username}",
                    host_hint="api.github.com",
                    timeout=8,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return isinstance(data, dict) and bool(data.get("login"))
                return False

            if site_name == "gitlab":
                resp = self.client.get(
                    f"https://gitlab.com/api/v4/users?username={username}",
                    host_hint="gitlab.com",
                    timeout=8,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return isinstance(data, list) and len(data) > 0
                return False

            if site_name == "keybase":
                resp = self.client.get(
                    f"https://keybase.io/_/api/1.0/user/lookup.json?username={username}",
                    host_hint="keybase.io",
                    timeout=8,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return isinstance(data, dict) and data.get("them") is not None
                return False

            if site_name == "reddit":
                resp = self.client.get(
                    f"https://www.reddit.com/user/{username}/about.json",
                    host_hint="www.reddit.com",
                    timeout=8,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return isinstance(data, dict) and bool(data.get("data"))
                return False

            if site_name == "hackernews":
                resp = self.client.get(
                    f"https://hacker-news.firebaseio.com/v0/user/{username}.json",
                    host_hint="hacker-news.firebaseio.com",
                    timeout=8,
                )
                if resp.status_code == 200:
                    return resp.text.strip() != "null" and resp.json() is not None
                return False

        except Exception:
            self.log.debug("Quick validator probe failed for %s on %s", username, site_name, exc_info=True)

        return False

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        sites = ["github", "gitlab", "keybase", "reddit", "hackernews"]

        for entity in entities:
            if not isinstance(entity, Username):
                continue

            username = entity.value.strip().lower()
            matched_sites: list[str] = []

            for site in sites:
                if self._check_platform(username, site):
                    matched_sites.append(site)

            meta = dict(entity.metadata)
            if len(matched_sites) >= 2:
                meta["quick_validated"] = True
                meta["validated_sites"] = matched_sites
                yield dataclasses.replace(entity, confidence=0.6, metadata=meta)
            else:
                meta["quick_validated"] = False
                yield dataclasses.replace(entity, confidence=0.1, metadata=meta)
