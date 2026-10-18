"""User mode EmailRep deliverability and reputation validator module."""

from __future__ import annotations

from tddt.core.entity import Email
from tddt.core.module import register_module
from tddt.modules.corporate.email.emailrep_validator import EmailRepValidatorModule


@register_module(
    name="user.email.emailrep_validator",
    mode=["user"],
    consumes=[Email],
    produces=[Email],
    active=False,
    requires_key=None,
)
class UserEmailRepValidatorModule(EmailRepValidatorModule):
    """User mode adapter for EmailRep reputation validation."""
    pass
