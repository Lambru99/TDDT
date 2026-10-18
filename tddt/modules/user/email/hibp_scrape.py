"""User mode HaveIBeenPwned breach scraper module."""

from __future__ import annotations

from tddt.core.entity import Breach, Email
from tddt.core.module import register_module
from tddt.modules.corporate.breach.hibp_scrape import HibpScrapeModule


@register_module(
    name="user.email.hibp_scrape",
    mode=["user"],
    consumes=[Email],
    produces=[Breach],
    active=False,
    requires_key="hibp_api_key",
)
class UserHibpScrapeModule(HibpScrapeModule):
    """User mode adapter for HIBP breach checking."""
    pass
