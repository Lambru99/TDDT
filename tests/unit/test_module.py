from __future__ import annotations

import importlib
import sys
import textwrap
from collections.abc import Iterable
from pathlib import Path

import pytest

from tddt.core.config import Settings
from tddt.core.entity import BaseEntity, Domain, Email, Subdomain
from tddt.core.module import (
    MODULE_REGISTRY,
    BaseModule,
    applicable,
    autodiscover,
    register_module,
)


@pytest.fixture(autouse=True)
def _clean_registry():
    """Each test starts with an empty MODULE_REGISTRY."""
    MODULE_REGISTRY.clear()
    yield
    MODULE_REGISTRY.clear()


def _make_module(name: str, **kwargs) -> type[BaseModule]:
    """Build and register a minimal concrete BaseModule."""
    defaults = {
        "mode": ["corporate"],
        "consumes": [Domain],
        "produces": [Email],
        "active": False,
        "requires_key": None,
        "batch_size": 1,
        "min_confidence": 0.3,
    }
    defaults.update(kwargs)

    @register_module(name=name, **defaults)
    class _Mod(BaseModule):
        def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
            return []

    return _Mod


# ──────────────────────────────────────────────────────────────────────────────


def test_decorator_registers_class():
    _make_module("corporate.email.fake")
    assert "corporate.email.fake" in MODULE_REGISTRY
    assert issubclass(MODULE_REGISTRY["corporate.email.fake"], BaseModule)


def test_decorator_sets_classvars():
    cls = _make_module("x.y", mode=["user"], active=True, min_confidence=0.5)
    assert cls.name == "x.y"
    assert cls.mode == ["user"]
    assert cls.active is True
    assert cls.min_confidence == 0.5


def test_duplicate_name_raises():
    _make_module("dup.name")
    with pytest.raises(ValueError, match="duplicate"):
        _make_module("dup.name")


def test_applicable_filters_by_entity_type():
    dom_mod = _make_module("mod.dom", consumes=[Domain])
    _make_module("mod.email", consumes=[Email])
    result = applicable(
        entity_type=Domain, mode="corporate", keyless_only=False,
        allow_active=True, settings=Settings(),
    )
    assert dom_mod in result
    assert len(result) == 1


def test_applicable_filters_by_mode():
    user_mod = _make_module("mod.user", mode=["user"])
    _make_module("mod.corp", mode=["corporate"])
    result = applicable(
        entity_type=Domain, mode="user", keyless_only=False,
        allow_active=True, settings=Settings(),
    )
    assert user_mod in result
    assert len(result) == 1


def test_applicable_filters_active_when_light():
    _make_module("mod.active", active=True)
    passive = _make_module("mod.passive", active=False)
    result = applicable(
        entity_type=Domain, mode="corporate", keyless_only=False,
        allow_active=False, settings=Settings(),
    )
    assert result == [passive]


def test_applicable_filters_missing_key():
    _make_module("mod.needs_key", requires_key="hunter")
    keyless = _make_module("mod.keyless", requires_key=None)
    settings = Settings()  # no hunter key
    result = applicable(
        entity_type=Domain, mode="corporate", keyless_only=False,
        allow_active=True, settings=settings,
    )
    assert result == [keyless]


def test_applicable_includes_keyed_when_configured():
    needs_key = _make_module("mod.needs_key", requires_key="hunter")
    settings = Settings()
    settings.hunter = "abc"
    result = applicable(
        entity_type=Domain, mode="corporate", keyless_only=False,
        allow_active=True, settings=settings,
    )
    assert needs_key in result


def test_applicable_keyless_only_excludes_keyed_even_if_configured():
    _make_module("mod.needs_key", requires_key="hunter")
    settings = Settings()
    settings.hunter = "abc"
    result = applicable(
        entity_type=Domain, mode="corporate", keyless_only=True,
        allow_active=True, settings=settings,
    )
    assert result == []


def test_subclass_consume_match():
    """A module consuming Domain should match Subdomain inputs (issubclass)."""
    mod = _make_module("mod.dom", consumes=[Domain])
    result = applicable(
        entity_type=Subdomain, mode="corporate", keyless_only=False,
        allow_active=True, settings=Settings(),
    )
    assert mod in result


def test_autodiscover_finds_modules(tmp_path: Path, monkeypatch):
    """Create a fake package tree, add to sys.path, autodiscover imports it."""
    pkg = tmp_path / "fake_mods"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "my_module.py").write_text(
        textwrap.dedent(
            """
            from collections.abc import Iterable
            from tddt.core.entity import BaseEntity, Domain, Email
            from tddt.core.module import BaseModule, register_module

            @register_module(
                name="fake.hello",
                mode=["corporate"],
                consumes=[Domain],
                produces=[Email],
                active=False,
            )
            class Hello(BaseModule):
                def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]:
                    return []
            """
        )
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    # Clear any cached submodules.
    for mod in list(sys.modules):
        if mod.startswith("fake_mods"):
            del sys.modules[mod]

    count = autodiscover("fake_mods")
    assert count >= 1
    assert "fake.hello" in MODULE_REGISTRY


def test_autodiscover_empty_package_returns_zero(tmp_path: Path, monkeypatch):
    pkg = tmp_path / "empty_pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    monkeypatch.syspath_prepend(str(tmp_path))
    for mod in list(sys.modules):
        if mod.startswith("empty_pkg"):
            del sys.modules[mod]
    assert autodiscover("empty_pkg") == 0


def test_basemodule_cannot_be_instantiated_abstract():
    with pytest.raises(TypeError):
        BaseModule(None, Settings(), None)  # type: ignore[arg-type]
