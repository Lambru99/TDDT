"""User mode Gravatar profile discovery module."""

from __future__ import annotations

from tddt.core.entity import Email, URL
from tddt.core.module import register_module
from tddt.modules.corporate.breach.gravatar import GravatarModule


@register_module(
    name="user.email.gravatar",
    mode=["user"],
    consumes=[Email],
    produces=[URL],
    active=False,
    requires_key=None,
)
class UserGravatarModule(GravatarModule):
    """User mode adapter for Gravatar profile discovery."""
    pass
