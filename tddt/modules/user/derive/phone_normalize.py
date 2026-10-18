"""Phone number normalization to E.164 standard module."""

from __future__ import annotations

from collections.abc import Iterable
import phonenumbers

from tddt.core.entity import BaseEntity, Phone
from tddt.core.module import BaseModule, register_module


@register_module(
    name="user.derive.phone_normalize",
    mode=["user"],
    consumes=[Phone],
    produces=[Phone],
    active=False,
    requires_key=None,
)
class PhoneNormalizeModule(BaseModule):
    """Parses and normalizes candidate phone numbers into E.164 format."""

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Phone):
                continue

            raw = entity.value.strip()
            parsed = None
            try:
                # First attempt without region (for numbers with leading +)
                parsed = phonenumbers.parse(raw, None)
            except phonenumbers.NumberParseException:
                for region in ("IT", "US", "GB", "FR", "DE"):
                    try:
                        parsed = phonenumbers.parse(raw, region)
                        if phonenumbers.is_valid_number(parsed):
                            break
                    except phonenumbers.NumberParseException:
                        parsed = None

            if parsed and phonenumbers.is_valid_number(parsed):
                e164 = phonenumbers.format_number(
                    parsed, phonenumbers.PhoneNumberFormat.E164
                )
                yield Phone(
                    value=e164,
                    parent_id=entity.id,
                    source_module=self.name,
                    confidence=1.0,
                    metadata={
                        "country_code": parsed.country_code,
                        "national_number": parsed.national_number,
                        "raw_input": raw,
                    },
                )
