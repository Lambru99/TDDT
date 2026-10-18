"""Profile avatar discovery and hash computation module."""

from __future__ import annotations

import hashlib
from typing import ClassVar, Iterable
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from tddt.core.entity import BaseEntity, Service, URL
from tddt.core.logger import get_logger
from tddt.core.module import BaseModule, register_module

_log = get_logger(__name__)


@register_module(
    name="user.service.avatar_hasher",
    mode=["user"],
    consumes=[Service],
    produces=[URL],
    active=False,
    requires_key=None,
)
class ServiceAvatarHasherModule(BaseModule):
    """Finds and hashes user profile avatars to enable cross-site visual attribution."""

    def run(self, entities: Iterable[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Service):
                continue

            try:
                resp = self.client.get(entity.value, timeout=15)
            except Exception as e:
                _log.warning("HTTP error fetching service %s: %s", entity.value, e)
                continue

            if resp.status_code != 200:
                _log.debug("Service page returned HTTP %d for %s", resp.status_code, entity.value)
                continue

            try:
                soup = BeautifulSoup(resp.text, "html.parser")
            except Exception as e:
                _log.debug("HTML parsing failed for %s: %s", entity.value, e)
                continue

            avatar_urls = []
            og_img = soup.select_one("meta[property='og:image']")
            if og_img and og_img.get("content"):
                avatar_urls.append(og_img["content"].strip())

            for img in soup.select("img.avatar, img[class*='avatar']"):
                src = img.get("src")
                if src and isinstance(src, str):
                    avatar_urls.append(src.strip())

            for raw_avatar_url in avatar_urls:
                avatar_url = urljoin(entity.value, raw_avatar_url)
                if not avatar_url.startswith(("http://", "https://")):
                    continue

                try:
                    img_resp = self.client.get(avatar_url, timeout=10)
                except Exception as e:
                    _log.debug("Failed to fetch avatar image %s: %s", avatar_url, e)
                    continue

                if img_resp.status_code != 200 or not img_resp.content:
                    continue

                sha256_hash = hashlib.sha256(img_resp.content).hexdigest()
                yield URL(
                    value=avatar_url,
                    source_module=self.name,
                    confidence=0.85,
                    metadata={
                        "avatar_sha256": sha256_hash,
                        "service": entity.value,
                    },
                )
                break  # Primary avatar processed
