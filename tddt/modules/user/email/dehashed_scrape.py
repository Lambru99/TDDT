"""User mode DeHashed breach scraper module."""

from __future__ import annotations

from tddt.core.entity import Breach, Email
from tddt.core.module import register_module
from tddt.modules.corporate.breach.dehashed_scrape import DehashedScrapeModule


@register_module(
    name="user.email.dehashed_scrape",
    mode=["user"],
    consumes=[Email],
    produces=[Breach],
    active=False,
    requires_key="dehashed_api_key",
)
class UserDehashedScrapeModule(DehashedScrapeModule):
    """User mode adapter for DeHashed breach checking."""
    pass
