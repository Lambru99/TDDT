"""Service content validator and metadata extractor (Core FP killer layer 2)."""

from __future__ import annotations

import dataclasses
import hashlib
from collections.abc import Iterable
from bs4 import BeautifulSoup

from tddt.core.entity import BaseEntity, Service
from tddt.core.module import BaseModule, register_module

SOFT_404_INDICATORS = (
    "user not found",
    "profile does not exist",
    "page not found",
    "account suspended",
    "user does not exist",
    "no user with this name",
    "doesn't exist",
    "this account has been suspended",
)


@register_module(
    name="user.username.service_validator",
    mode=["user"],
    consumes=[Service],
    produces=[Service],
    min_confidence=0.3,
    active=False,
    requires_key=None,
)
class ServiceValidatorModule(BaseModule):
    """Validates public profile content, filters soft-404s, and extracts bio/avatar metadata."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Service):
                continue

            url = entity.metadata.get("url")
            if not url:
                yield entity
                continue

            try:
                resp = self.client.get(url, timeout=10)
            except Exception:
                self.log.debug("Service validator request failed for %s", url, exc_info=True)
                yield entity
                continue

            body_low = resp.text.lower()
            if any(ind in body_low for ind in SOFT_404_INDICATORS):
                meta = dict(entity.metadata)
                meta["soft_404"] = True
                meta["validated"] = False
                yield dataclasses.replace(entity, confidence=0.1, metadata=meta)
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            avatar_url = ""
            og_img = soup.find("meta", property="og:image")
            if og_img and og_img.get("content"):
                avatar_url = str(og_img.get("content")).strip()

            bio = ""
            og_desc = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "description"})
            if og_desc and og_desc.get("content"):
                bio = str(og_desc.get("content")).strip()

            avatar_hash = hashlib.sha256(avatar_url.encode()).hexdigest()[:16] if avatar_url else ""

            meta = dict(entity.metadata)
            meta["validated"] = True
            if avatar_url:
                meta["avatar_url"] = avatar_url
                meta["avatar_hash"] = avatar_hash
            if bio:
                meta["bio"] = bio

            yield dataclasses.replace(entity, confidence=0.7, metadata=meta)
