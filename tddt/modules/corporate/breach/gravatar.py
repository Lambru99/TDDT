"""Gravatar avatar and profile discovery module."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable

from tddt.core.entity import BaseEntity, Email, URL
from tddt.core.module import BaseModule, register_module


@register_module(
    name="corporate.breach.gravatar",
    mode=["corporate", "user"],
    consumes=[Email],
    produces=[URL],
    active=False,
    requires_key=None,
)
class GravatarModule(BaseModule):
    """Checks Gravatar for avatar profile associated with email address."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Email):
                continue

            email_val = entity.value.strip().lower()
            email_hash = hashlib.md5(email_val.encode("utf-8")).hexdigest()
            avatar_url = f"https://www.gravatar.com/avatar/{email_hash}?d=404"

            try:
                resp = self.client.get(
                    avatar_url, host_hint="www.gravatar.com", timeout=10
                )
            except Exception:
                self.log.debug("Gravatar lookup failed for %s", email_val, exc_info=True)
                continue

            if resp.status_code == 404:
                self.log.debug("No Gravatar found for %s", email_val)
                continue
            if resp.status_code != 200:
                self.log.debug("Gravatar returned status %d for %s", resp.status_code, email_val)
                continue

            yield URL(
                value=f"https://www.gravatar.com/avatar/{email_hash}",
                parent_id=entity.id,
                source_module=self.name,
                metadata={
                    "email": email_val,
                    "hash": email_hash,
                    "profile": f"https://gravatar.com/{email_hash}",
                    "source": "gravatar",
                },
            )
