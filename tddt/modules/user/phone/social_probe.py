"""Active social messenger probe module for phone numbers."""

from __future__ import annotations

import re
from typing import ClassVar, Iterable

from tddt.core.entity import BaseEntity, Phone, Service
from tddt.core.logger import get_logger
from tddt.core.module import BaseModule, register_module

_log = get_logger(__name__)


@register_module(
    name="user.phone.social_probe",
    mode=["user"],
    consumes=[Phone],
    produces=[Service],
    active=True,
    requires_key=None,
)
class PhoneSocialProbeModule(BaseModule):
    """Actively probes messaging service endpoints for registered phone numbers."""

    def run(self, entities: Iterable[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Phone):
                continue

            digits = re.sub(r"\D", "", entity.value)
            if not digits:
                continue

            # Probe WhatsApp
            wa_url = f"https://api.whatsapp.com/send?phone={digits}"
            try:
                resp = self.client.get(wa_url, timeout=10)
                if resp.status_code == 200:
                    yield Service(
                        value=f"https://api.whatsapp.com/send?phone={digits}",
                        source_module=self.name,
                        confidence=0.85,
                        metadata={"platform": "whatsapp", "phone": entity.value, "short_url": f"https://wa.me/{digits}"},
                    )
            except Exception as e:
                _log.debug("WhatsApp probe failed for %s: %s", entity.value, e)
