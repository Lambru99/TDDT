"""Phone validation and metadata enrichment via libphonenumbers."""

from __future__ import annotations

from typing import ClassVar, Iterable

import phonenumbers
from phonenumbers import carrier, geocoder, timezone

from tddt.core.entity import BaseEntity, Phone
from tddt.core.logger import get_logger
from tddt.core.module import BaseModule, register_module

_log = get_logger(__name__)


@register_module(
    name="user.phone.libphonenumbers",
    mode=["user"],
    consumes=[Phone],
    produces=[Phone],
    active=False,
    requires_key=None,
)
class PhoneLibphonenumbersModule(BaseModule):
    """Parses, validates, and enriches phone numbers using libphonenumbers."""

    def run(self, entities: Iterable[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Phone):
                continue

            raw_val = entity.value.strip()
            try:
                parsed = phonenumbers.parse(raw_val, None)
            except Exception as e:
                _log.debug("Failed to parse phone number %s: %s", raw_val, e)
                continue

            is_valid = phonenumbers.is_valid_number(parsed)
            is_possible = phonenumbers.is_possible_number(parsed)

            e164_val = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
            country_desc = geocoder.description_for_number(parsed, "en") or None
            carrier_name = carrier.name_for_number(parsed, "en") or None
            tz_list = list(timezone.time_zones_for_number(parsed))

            meta = dict(entity.metadata)
            meta.update({
                "country": country_desc,
                "carrier": carrier_name,
                "timezones": tz_list,
                "valid": is_valid,
                "possible": is_possible,
            })

            conf = 0.95 if is_valid else (0.8 if is_possible else 0.5)
            yield Phone(
                value=e164_val,
                source_module=self.name,
                confidence=conf,
                metadata=meta,
            )
