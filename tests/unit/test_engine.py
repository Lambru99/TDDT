from __future__ import annotations

import time
from collections.abc import Iterable

import pytest

from tddt.core.config import Settings
from tddt.core.engine import CorrelationEngine
from tddt.core.entity import BaseEntity, Domain, Email, Subdomain
from tddt.core.module import MODULE_REGISTRY, BaseModule, register_module


@pytest.fixture(autouse=True)
def _clean_registry():
    MODULE_REGISTRY.clear()
    yield
    MODULE_REGISTRY.clear()


@pytest.fixture
def engine():
    """Engine with a dummy client (no module in these tests actually uses the client)."""
    settings = Settings()
    settings.threads = 4
    return CorrelationEngine(client=None, settings=settings)


# ──────────────────────────────────────────────────────────────────────────────
# Basic dispatch
# ──────────────────────────────────────────────────────────────────────────────


def test_engine_runs_applicable_module_on_seed(engine):
    @register_module(
        name="t.produces_email", mode=["corporate"],
        consumes=[Domain], produces=[Email], active=False,
    )
    class M(BaseModule):
        def run(self, entities):
            for e in entities:
                yield Email(value=f"info@{e.value}", parent_id=e.id)

    graph = engine.scan([Domain(value="x.com")], mode="corporate")
    emails = graph.of_type(Email)
    assert len(emails) == 1
    assert emails[0].value == "info@x.com"


def test_engine_dedup_prevents_rerun(engine):
    """Same (module, entity) pair should not be dispatched twice."""
    call_count = {"n": 0}

    @register_module(
        name="t.counts", mode=["corporate"],
        consumes=[Domain], produces=[Email], active=False,
    )
    class M(BaseModule):
        def run(self, entities):
            call_count["n"] += len(list(entities))
            for e in entities:
                # Yield the same Email every time to keep the graph adding no new work
                yield Email(value="static@x.com", parent_id=e.id)

    engine.scan([Domain(value="x.com")], mode="corporate")
    assert call_count["n"] == 1


def test_engine_stops_at_max_iterations():
    settings = Settings()
    settings.max_iterations = 2
    settings.threads = 2
    engine = CorrelationEngine(client=None, settings=settings)
    counter = {"n": 0}

    @register_module(
        name="t.chain", mode=["corporate"],
        consumes=[Domain], produces=[Domain], active=False,
    )
    class M(BaseModule):
        def run(self, entities):
            for e in entities:
                counter["n"] += 1
                # Always produce a NEW domain to keep the queue going.
                yield Domain(value=f"n{counter['n']}.{e.value}", parent_id=e.id)

    graph = engine.scan([Domain(value="x.com")], mode="corporate")
    assert graph.metadata["terminated_reason"] == "max_iterations"


def test_engine_stops_at_max_runtime():
    """Review Focus #2: engine aborts between iterations when wall-time cap hit."""
    settings = Settings()
    settings.max_runtime = 0.4
    settings.max_iterations = 100
    settings.threads = 2
    engine = CorrelationEngine(client=None, settings=settings)

    @register_module(
        name="t.slow", mode=["corporate"],
        consumes=[Domain], produces=[Domain], active=False,
    )
    class M(BaseModule):
        def run(self, entities):
            for e in entities:
                time.sleep(0.3)
                yield Domain(value=f"slow{e.value}", parent_id=e.id)

    start = time.monotonic()
    graph = engine.scan([Domain(value="x.com")], mode="corporate")
    elapsed = time.monotonic() - start
    assert graph.metadata["terminated_reason"] == "max_runtime"
    assert elapsed < 2.0  # should abort well before running many iterations


def test_engine_respects_downstream_threshold(engine):
    """Entities below 0.5 confidence enter the graph but don't trigger downstream."""
    produced = {"low_seen": 0}

    @register_module(
        name="t.produces_low", mode=["corporate"],
        consumes=[Domain], produces=[Email], active=False,
    )
    class LowProducer(BaseModule):
        def run(self, entities):
            for e in entities:
                yield Email(value=f"low@{e.value}", confidence=0.3, parent_id=e.id)

    @register_module(
        name="t.email_consumer", mode=["corporate"],
        consumes=[Email], produces=[Domain], active=False,
    )
    class EmailConsumer(BaseModule):
        def run(self, entities):
            produced["low_seen"] += len(list(entities))
            return []

    engine.scan([Domain(value="x.com")], mode="corporate")
    assert produced["low_seen"] == 0  # low-confidence Email never triggered downstream


def test_engine_respects_max_entities_per_type():
    """Review Focus #1: wildcard DNS produces 5000 subdomains → graph caps at the max."""
    settings = Settings()
    settings.threads = 2
    engine = CorrelationEngine(client=None, settings=settings, max_entities_per_type=50)

    @register_module(
        name="t.flood", mode=["corporate"],
        consumes=[Domain], produces=[Subdomain], active=False,
    )
    class Flood(BaseModule):
        def run(self, entities):
            for e in entities:
                for i in range(5000):
                    yield Subdomain(value=f"sub{i}.{e.value}", parent_id=e.id)

    graph = engine.scan([Domain(value="x.com")], mode="corporate")
    # Domain count includes Subdomain by polymorphism, but exact-type cap applies.
    sub_count = sum(1 for e in graph.all() if type(e).__name__ == "Subdomain")
    assert sub_count == 50


def test_engine_skips_active_in_light(engine):
    seen = {"active": 0, "passive": 0}

    @register_module(
        name="t.active", mode=["corporate"],
        consumes=[Domain], produces=[Email], active=True,
    )
    class Active(BaseModule):
        def run(self, entities):
            seen["active"] += 1
            return []

    @register_module(
        name="t.passive", mode=["corporate"],
        consumes=[Domain], produces=[Email], active=False,
    )
    class Passive(BaseModule):
        def run(self, entities):
            seen["passive"] += 1
            return []

    engine.scan([Domain(value="x.com")], mode="corporate", allow_active=False)
    assert seen["active"] == 0
    assert seen["passive"] == 1


def test_engine_isolates_failing_module(engine):
    """A module that raises must not kill the scan."""
    seen = {"ok": 0}

    @register_module(
        name="t.boom", mode=["corporate"],
        consumes=[Domain], produces=[Email], active=False,
    )
    class Boom(BaseModule):
        def run(self, entities):
            raise RuntimeError("deliberate")

    @register_module(
        name="t.ok", mode=["corporate"],
        consumes=[Domain], produces=[Email], active=False,
    )
    class Ok(BaseModule):
        def run(self, entities):
            seen["ok"] += 1
            for e in entities:
                yield Email(value=f"info@{e.value}", parent_id=e.id)

    graph = engine.scan([Domain(value="x.com")], mode="corporate")
    assert seen["ok"] == 1
    assert graph.count_of_type(Email) == 1


def test_engine_control_char_in_seed_value_does_not_crash(engine):
    """Review Focus #3: zero-width unicode in seed must not crash the engine."""
    @register_module(
        name="t.read_value", mode=["user"],
        consumes=[Email], produces=[Email], active=False,
    )
    class M(BaseModule):
        def run(self, entities):
            return []

    graph = engine.scan([Email(value="x​@y.com")], mode="user")
    assert graph.count_of_type(Email) == 1  # seed preserved


def test_engine_no_a_record_still_runs_passive_modules(engine):
    """Review Focus #5: seed Domain with no derived IPAddress. Modules consuming
    Domain still execute (the engine doesn't require any particular derived entity)."""
    @register_module(
        name="t.needs_ip", mode=["corporate"],
        consumes=[Domain], produces=[Email], active=False,
    )
    class NeedsIp(BaseModule):
        def run(self, entities):
            # Pretend this is email harvesting that doesn't need an IP.
            for e in entities:
                yield Email(value=f"info@{e.value}", parent_id=e.id)

    graph = engine.scan([Domain(value="offline.test")], mode="corporate")
    assert graph.count_of_type(Email) == 1


# ──────────────────────────────────────────────────────────────────────────────
# Batching
# ──────────────────────────────────────────────────────────────────────────────


def test_engine_batches_when_batch_size_gt_1():
    """A module with batch_size=100 receives up to 100 entities per run call."""
    engine_s = Settings()
    engine_s.threads = 2
    engine = CorrelationEngine(client=None, settings=engine_s)
    batch_sizes_seen: list[int] = []

    @register_module(
        name="t.batched", mode=["corporate"],
        consumes=[Subdomain], produces=[Email], active=False, batch_size=10,
    )
    class M(BaseModule):
        def run(self, entities):
            batch_sizes_seen.append(len(list(entities)))
            return []

    @register_module(
        name="t.flood", mode=["corporate"],
        consumes=[Domain], produces=[Subdomain], active=False,
    )
    class Flood(BaseModule):
        def run(self, entities):
            for e in entities:
                if isinstance(e, Subdomain):
                    continue
                for i in range(25):
                    yield Subdomain(value=f"s{i}.{e.value}", parent_id=e.id)

    engine.scan([Domain(value="x.com")], mode="corporate")
    # Flood produces 25 Subdomains → M batches them 10 + 10 + 5.
    assert sorted(batch_sizes_seen) == [5, 10, 10]


# ──────────────────────────────────────────────────────────────────────────────
# Progress callback
# ──────────────────────────────────────────────────────────────────────────────


def test_engine_progress_callback_fires_per_iteration(engine):
    @register_module(
        name="t.one", mode=["corporate"],
        consumes=[Domain], produces=[Email], active=False,
    )
    class M(BaseModule):
        def run(self, entities):
            for e in entities:
                yield Email(value=f"i@{e.value}", parent_id=e.id)

    events: list[int] = []

    def cb(iteration, graph):
        events.append(iteration)

    engine.scan([Domain(value="x.com")], mode="corporate", progress_callback=cb)
    assert events == [1]
