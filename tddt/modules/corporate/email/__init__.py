"""Corporate email harvesting modules package."""

from __future__ import annotations

import re

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
JUNK_EXTENSIONS = (
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".css",
    ".js",
    ".svg",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
)


def extract_domain_emails(text: str, domain: str) -> set[str]:
    """Extract email addresses from text that belong to domain or its subdomains."""
    found: set[str] = set()
    dom_lower = domain.lower().strip()
    for m in EMAIL_REGEX.findall(text):
        e = m.lower().strip()
        if (e.endswith(f"@{dom_lower}") or e.endswith(f".{dom_lower}")) and not any(
            e.endswith(ext) for ext in JUNK_EXTENSIONS
        ):
            found.add(e)
    return found
