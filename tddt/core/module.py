"""BaseModule, @register_module decorator, MODULE_REGISTRY, autodiscover.

Modules declare consumes/produces entity types, mode (corporate/user), and
whether they require an API key or make active probes. The engine filters
and dispatches via the registry.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import TYPE_CHECKING, ClassVar

from tddt.core.entity import BaseEntity
from tddt.core.logger import get_logger

if TYPE_CHECKING:  # pragma: no cover - import cycle guard
    from tddt.core.config import Settings
    from tddt.core.http import HttpClient

_log = get_logger(__name__)


MODULE_REGISTRY: dict[str, type["BaseModule"]] = {}


class BaseModule(ABC):
    """Base class for all corporate and user mode modules.

    Subclasses are registered via `@register_module(...)` which sets the
    ClassVars (name, mode, consumes, produces, active, requires_key,
    batch_size, min_confidence) and inserts the class into `MODULE_REGISTRY`.
    """

    name: ClassVar[str]
    mode: ClassVar[list[str]]
    consumes: ClassVar[list[type[BaseEntity]]]
    produces: ClassVar[list[type[BaseEntity]]]
    active: ClassVar[bool]
    requires_key: ClassVar[str | None]
    batch_size: ClassVar[int] = 1
    min_confidence: ClassVar[float] = 0.3

    def __init__(
        self,
        client: "HttpClient",
        settings: "Settings",
        log: logging.Logger | None = None,
    ) -> None:
        self.client = client
        self.settings = settings
        self.log = log or get_logger(type(self).__module__)

    @abstractmethod
    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
        """Process a batch of input entities and yield new entities."""


def register_module(
    *,
    name: str,
    mode: list[str],
    consumes: list[type[BaseEntity]],
    produces: list[type[BaseEntity]],
    active: bool,
    requires_key: str | None = None,
    batch_size: int = 1,
    min_confidence: float = 0.3,
):
    """Decorator that attaches the module's declaration to the class and
    inserts it into `MODULE_REGISTRY`. Raises on duplicate names."""

    def decorator(cls: type[BaseModule]) -> type[BaseModule]:
        if name in MODULE_REGISTRY:
            raise ValueError(f"duplicate module name: {name!r}")
        cls.name = name
        cls.mode = mode
        cls.consumes = consumes
        cls.produces = produces
        cls.active = active
        cls.requires_key = requires_key
        cls.batch_size = batch_size
        cls.min_confidence = min_confidence
        MODULE_REGISTRY[name] = cls
        return cls

    return decorator


def applicable(
    *,
    entity_type: type[BaseEntity],
    mode: str,
    keyless_only: bool,
    allow_active: bool,
    settings: "Settings",
) -> list[type[BaseModule]]:
    """Return registered module classes applicable to this entity + context.

    Filters:
      - module.mode contains the scan mode
      - entity_type is a subclass of (or is) one of module.consumes
      - active modules excluded when allow_active=False (i.e. --light)
      - modules requiring a key: excluded when keyless_only=True OR when the
        settings attribute named by requires_key is None/empty
    """
    result: list[type[BaseModule]] = []
    for cls in MODULE_REGISTRY.values():
        if mode not in cls.mode:
            continue
        if not any(issubclass(entity_type, c) for c in cls.consumes):
            continue
        if cls.active and not allow_active:
            continue
        if cls.requires_key:
            if keyless_only:
                continue
            key_value = getattr(settings, cls.requires_key, None)
            if not key_value:
                continue
        result.append(cls)
    return result


def autodiscover(package_name: str = "tddt.modules") -> int:
    """Import every submodule under `package_name` so decorators register.

    Returns the number of modules added to MODULE_REGISTRY by this call.
    Import failures of individual submodules are logged but don't abort the
    scan — this lets a broken plugin skip itself without killing the tool.
    """
    try:
        pkg = importlib.import_module(package_name)
    except ModuleNotFoundError:
        _log.warning("autodiscover: package %r not found", package_name)
        return 0

    before = set(MODULE_REGISTRY.keys())
    for info in pkgutil.walk_packages(pkg.__path__, prefix=f"{package_name}."):
        try:
            importlib.import_module(info.name)
        except ImportError as exc:
            _log.exception("autodiscover: failed to import %s: %s", info.name, exc)
    added = set(MODULE_REGISTRY.keys()) - before
    return len(added)
