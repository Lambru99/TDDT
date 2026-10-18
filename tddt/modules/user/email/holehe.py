"""Holehe account existence checker module."""

from __future__ import annotations

from collections.abc import Iterable

from tddt.core.entity import BaseEntity, Email, Service
from tddt.core.module import BaseModule, register_module


@register_module(
    name="user.email.holehe",
    mode=["user"],
    consumes=[Email],
    produces=[Service],
    active=False,
    requires_key=None,
)
class HoleheModule(BaseModule):
    """Checks account existence across 120+ platforms using the holehe engine."""

    def _run_holehe(self, email: str) -> list[dict]:
        try:
            import httpx
            import trio
            from holehe.core import get_functions, import_submodules, launch_module

            class DummyArgs:
                onlyused = True
                nopasswordrecovery = True
                timeout = 5

            args = DummyArgs()
            modules = import_submodules("holehe.modules")
            websites = get_functions(modules, args)
            out: list[dict] = []

            async def runner():
                async with httpx.AsyncClient(timeout=5) as client:
                    async with trio.open_nursery() as nursery:
                        for w in websites:
                            nursery.start_soon(launch_module, w, email, client, out)

            trio.run(runner)
            return out
        except Exception:
            self.log.debug("Holehe execution error for %s", email, exc_info=True)
            return []

    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Email):
                continue

            email_val = entity.value.strip().lower()
            results = self._run_holehe(email_val)
            for res in results:
                if res.get("exists") is True:
                    site_name = res.get("name", "Unknown")
                    yield Service(
                        value=f"{site_name}:{email_val}",
                        parent_id=entity.id,
                        source_module=self.name,
                        confidence=0.7,
                        metadata={
                            "site": site_name,
                            "exists": True,
                            "method": "holehe",
                            "email": email_val,
                            "rate_limit": res.get("rate_limit", False),
                        },
                    )
