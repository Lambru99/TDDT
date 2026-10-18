"""Hunter.io domain search module for corporate email harvesting and naming patterns."""

from __future__ import annotations

from collections.abc import Iterable

from tddt.core.entity import BaseEntity, Domain, Email, Finding
from tddt.core.module import BaseModule, register_module


@register_module(
    name="corporate.email.hunter",
    mode=["corporate"],
    consumes=[Domain],
    produces=[Email, Finding],
    active=False,
    requires_key="hunter_api_key",
)
class HunterEmailModule(BaseModule):
    """Harvests emails and naming pattern from Hunter.io."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Domain):
                continue

            domain = entity.value.strip().lower()
            api_key = getattr(self.settings, "hunter", "") or getattr(
                self.settings, "hunter_api_key", ""
            )
            if not api_key:
                self.log.debug("Hunter.io API key not configured; skipping %s", domain)
                continue

            url = "https://api.hunter.io/v2/domain-search"
            params = {
                "domain": domain,
                "api_key": api_key,
                "limit": "100",
            }

            try:
                resp = self.client.get(
                    url, params=params, host_hint="api.hunter.io", timeout=15
                )
            except Exception:
                self.log.debug("Hunter.io query failed for %s", domain, exc_info=True)
                continue

            if resp.status_code in (401, 403, 429):
                self.log.warning(
                    "Hunter.io returned status %d for %s (invalid key or rate limit)",
                    resp.status_code,
                    domain,
                )
                continue
            if resp.status_code != 200:
                self.log.debug("Hunter.io returned non-200 status %d for %s", resp.status_code, domain)
                continue

            try:
                payload = resp.json()
            except Exception:
                self.log.debug("Failed to decode Hunter.io JSON for %s", domain, exc_info=True)
                continue

            data = payload.get("data", {})
            pattern = data.get("pattern")
            if pattern:
                entity.metadata["naming_pattern"] = pattern
                yield Finding(
                    value=pattern,
                    parent_id=entity.id,
                    source_module=self.name,
                    metadata={"type": "naming_pattern", "pattern": pattern, "domain": domain},
                )

            for item in data.get("emails", []):
                val = item.get("value", "").strip().lower()
                if val:
                    yield Email(
                        value=val,
                        parent_id=entity.id,
                        source_module=self.name,
                        metadata={
                            "source": "hunter",
                            "first_name": item.get("first_name"),
                            "last_name": item.get("last_name"),
                            "domain": domain,
                        },
                    )
