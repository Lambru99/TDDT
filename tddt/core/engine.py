"""CorrelationEngine: iterative scan over an EntityGraph.

Each iteration dequeues the new entities, finds applicable modules via the
registry, dispatches them in parallel (ThreadPoolExecutor), and feeds their
output back into the graph. Dedup via `_dispatched` + `graph.add` prevents
rework. Caps (iterations, runtime, entities-per-type, downstream_threshold)
keep the correlation bounded. See spec §7.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING

from tddt.core.entity import DEFAULT_MAX_ENTITIES_PER_TYPE, BaseEntity, EntityGraph
from tddt.core.logger import get_logger
from tddt.core.module import BaseModule, applicable

if TYPE_CHECKING:  # pragma: no cover
    from tddt.core.config import Settings
    from tddt.core.http import HttpClient


DEFAULT_DOWNSTREAM_THRESHOLD = 0.5


class CorrelationEngine:
    def __init__(
        self,
        client: "HttpClient | None",
        settings: "Settings",
        log=None,
        max_entities_per_type: int = DEFAULT_MAX_ENTITIES_PER_TYPE,
        downstream_threshold: float = DEFAULT_DOWNSTREAM_THRESHOLD,
    ) -> None:
        self.client = client
        self.settings = settings
        self.log = log or get_logger(__name__)
        self.max_entities_per_type = max_entities_per_type
        self.downstream_threshold = downstream_threshold

    def scan(
        self,
        seeds: list[BaseEntity],
        mode: str,
        allow_active: bool = True,
        keyless_only: bool = False,
        progress_callback: Callable[[int, EntityGraph], None] | None = None,
    ) -> EntityGraph:
        graph = EntityGraph(max_entities_per_type=self.max_entities_per_type)
        queue: deque[BaseEntity] = deque()
        for seed in seeds:
            if graph.add(seed):
                queue.append(seed)

        start = time.monotonic()
        iteration = 0
        terminated = "converged"

        while queue:
            # Time cap (checked at the start of each iteration).
            if time.monotonic() - start >= self.settings.max_runtime:
                terminated = "max_runtime"
                break
            # Iteration cap.
            if iteration >= self.settings.max_iterations:
                terminated = "max_iterations"
                break

            iteration += 1
            batch = list(queue)
            queue.clear()

            # Build (module_cls -> list of entities to process).
            grouped: dict[type[BaseModule], list[BaseEntity]] = defaultdict(list)
            for entity in batch:
                mods = applicable(
                    entity_type=type(entity),
                    mode=mode,
                    keyless_only=keyless_only,
                    allow_active=allow_active,
                    settings=self.settings,
                )
                for mod_cls in mods:
                    if entity.confidence < mod_cls.min_confidence:
                        continue
                    if graph.is_dispatched(mod_cls.name, entity.id):
                        continue
                    graph.mark_dispatched(mod_cls.name, entity.id)
                    grouped[mod_cls].append(entity)

            if not grouped:
                # Nothing applicable — converge without firing the callback,
                # since no actual work took place in this iteration.
                iteration -= 1
                break

            # Dispatch in parallel.
            new_entities: list[BaseEntity] = []
            with ThreadPoolExecutor(max_workers=self.settings.threads) as ex:
                futures = {
                    ex.submit(self._run_module, mod_cls, entities): mod_cls
                    for mod_cls, entities in grouped.items()
                }
                for fut in as_completed(futures):
                    try:
                        new_entities.extend(fut.result())
                    except Exception:  # noqa: BLE001 - module isolation
                        self.log.exception(
                            "unexpected engine failure for module %s", futures[fut].name
                        )

            # Fold new entities into graph; enqueue those above the threshold.
            for ent in new_entities:
                if graph.add(ent) and ent.confidence >= self.downstream_threshold:
                    queue.append(ent)

            if progress_callback:
                progress_callback(iteration, graph)

        graph.metadata["terminated_reason"] = terminated
        graph.metadata["iterations"] = iteration
        graph.metadata["elapsed_s"] = round(time.monotonic() - start, 3)
        return graph

    # ── Module invocation with batching + failure isolation ────────────────

    def _run_module(
        self, mod_cls: type[BaseModule], entities: list[BaseEntity]
    ) -> list[BaseEntity]:
        try:
            mod = mod_cls(self.client, self.settings, log=self.log)
        except Exception:  # noqa: BLE001 - log and skip, module isolation
            self.log.exception("failed to instantiate %s", mod_cls.name)
            return []

        results: list[BaseEntity] = []
        batch_size = mod_cls.batch_size

        def _invoke(chunk: list[BaseEntity]) -> list[BaseEntity]:
            try:
                return list(mod.run(chunk))
            except Exception:  # noqa: BLE001 - module isolation
                self.log.exception("module %s raised; skipping chunk", mod_cls.name)
                return []

        if batch_size == 0:
            results.extend(_invoke(entities))
        elif batch_size <= 1:
            for e in entities:
                results.extend(_invoke([e]))
        else:
            for i in range(0, len(entities), batch_size):
                results.extend(_invoke(entities[i : i + batch_size]))
        return results
