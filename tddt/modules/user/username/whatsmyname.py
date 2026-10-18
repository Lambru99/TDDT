"""WhatsMyName username enumeration module (Core FP killer layer 1)."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from platformdirs import user_cache_dir

from tddt.core.config import Settings
from tddt.core.entity import BaseEntity, Service, Username
from tddt.core.http import HttpClient
from tddt.core.module import BaseModule, register_module

WMN_URL = "https://raw.githubusercontent.com/WebBreacher/WhatsMyName/main/wmn-data.json"


@register_module(
    name="user.username.whatsmyname",
    mode=["user"],
    consumes=[Username],
    produces=[Service],
    min_confidence=0.5,
    active=False,
    requires_key=None,
)
class WhatsMyNameModule(BaseModule):
    """Probes hundreds of public services using the WhatsMyName database."""

    def __init__(
        self,
        client: HttpClient,
        settings: Settings,
        log=None,
        db_path: Path | None = None,
    ) -> None:
        super().__init__(client, settings, log=log)
        self.db_path = db_path or (Path(user_cache_dir("tddt")) / "wmn.json")

    def _load_sites(self) -> list[dict]:
        if not self.db_path.exists():
            try:
                self.db_path.parent.mkdir(parents=True, exist_ok=True)
                resp = self.client.get(WMN_URL, timeout=30)
                if resp.status_code == 200:
                    self.db_path.write_bytes(resp.content)
            except Exception:
                self.log.debug("Failed downloading WMN database", exc_info=True)
                return []

        try:
            with open(self.db_path, encoding="utf-8") as f:
                data = json.load(f)
                return data.get("sites", [])
        except Exception:
            self.log.debug("Failed reading WMN database from %s", self.db_path, exc_info=True)
            return []

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        sites = self._load_sites()
        if not sites:
            return

        for entity in entities:
            if not isinstance(entity, Username):
                continue

            username = entity.value.strip().lower()

            for site in sites:
                site_name = site.get("name", "Unknown")
                uri_template = site.get("uri_check", "")
                if not uri_template or "{account}" not in uri_template:
                    continue

                check_url = uri_template.replace("{account}", username)
                e_code = site.get("e_code", 200)
                m_code = site.get("m_code")
                e_string = site.get("e_string", "")
                m_string = site.get("m_string", "")

                try:
                    resp = self.client.get(check_url, timeout=8)
                    if m_code and resp.status_code == m_code:
                        continue
                    if resp.status_code != e_code:
                        continue
                    if e_string and e_string not in resp.text:
                        continue
                    if m_string and m_string in resp.text:
                        continue

                    yield Service(
                        value=f"{site_name}:{username}",
                        parent_id=entity.id,
                        source_module=self.name,
                        confidence=0.5,
                        metadata={
                            "site": site_name,
                            "url": check_url,
                            "username": username,
                            "category": site.get("category", ""),
                        },
                    )
                except Exception:
                    self.log.debug("WMN check failed for %s on %s", username, site_name, exc_info=True)
                    continue
