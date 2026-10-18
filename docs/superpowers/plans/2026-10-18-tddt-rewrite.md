# TDDT v2 Rewrite — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite TDDT as a plugin-based EASM+OSINT tool with a correlation engine, keyless-first module set, and a new User OSINT mode.

**Architecture:** `tddt.core` (entity model, HTTP client, logger, correlation engine, plugin registry) is the stable foundation. Modules under `tddt.modules.{corporate,user}/<category>/<name>.py` self-register via `@register_module` and are auto-discovered. The engine iterates on an `EntityGraph` until convergence or cap. Report layer (`tddt.report`) exports JSON/Markdown/HTML and builds `Profile` aggregates for user mode.

**Tech Stack:** Python 3.11+, `requests` + `requests-cache` + `urllib3.Retry`, `ThreadPoolExecutor`, `rich`, `beautifulsoup4`, `dnspython`, `mmh3`, `python-dotenv`, `phonenumbers`, `holehe`, `pypdf`, `python-docx`. `pytest` + `pytest-vcr` + `pytest-cov`, `ruff`, `mypy --strict` (core only).

**Spec:** `docs/superpowers/specs/2026-10-18-tddt-rewrite-design.md`

## Global Constraints

- **Python 3.11+** required (uses `str | None`, `ClassVar`, modern dataclass features). Pinned in `pyproject.toml`.
- **Cross-platform** (Linux, macOS, Windows). Use `sys.executable`, `pathlib`, XDG via `platformdirs` for cache/log paths.
- **Zero API keys required** for `--only-keyless` scan; every module with `requires_key` has a documented keyless alternative in the same category.
- **No `except Exception: pass`** anywhere in the repo. CI check enforces this. Replacement: `log.exception()` or `log.warning(..., exc_info=True)`.
- **Secret entities never carry the full value** — only `preview` (max 40 chars) + `sha256` for dedup. Enforced in `Secret.__post_init__`.
- **TLS verification ON by default**; `--insecure` is the only way to disable.
- **Report JSON schema stable**: top-level keys `scan`, `entities`, `profile` only. Entity dicts always carry `type`, `value`, `id`, `confidence`, `source_module`, `parent_id`, `discovered_at`, `metadata`.
- **No commit touches `main.py`** until Phase 5. The old entry point stays working during migration.

## Review Focus

Inputs the spec implies but no single task's tests cover end-to-end. For each, the test is attached to the owning task.

1. **Wildcard DNS target** — every subdomain query resolves, engine could enqueue thousands. `CorrelationEngine.max_entities_per_type=2000` cap must halt enqueueing of further `Subdomain` and emit a warning. *Covered in Task 1.8.*
2. **Scan hits `max_runtime=600s`** — engine aborts between iterations, exports partial graph via same report path, exit code 0 with a documented flag in `scan.terminated_reason`. *Covered in Task 1.8.*
3. **Entity value containing control chars / zero-width unicode** — `BaseEntity.id` hash stays stable, logger escapes before printing (no terminal injection). *Covered in Task 1.1.*
4. **User mode CLI without any input flag** (`tddt user` alone) — exits with code 2 and a clear error before any module is instantiated. *Covered in Task 2.1.*
5. **Target DNS fails for the seed domain** (`whois` resolves but `A` record absent) — engine still runs passive-only modules that take `Domain` (crtsh, hunter, email dorks), does not crash on missing IPAddress. *Covered in Task 1.8 integration test.*

---

## Phase 0 — Scaffolding

### Task 0.1: Package layout + pyproject.toml

**Files:**
- Create: `pyproject.toml`, `tddt/__init__.py`, `tddt/__main__.py`, `tddt/core/__init__.py`, `tddt/modules/__init__.py`, `tddt/modules/corporate/__init__.py`, `tddt/modules/user/__init__.py`, `tddt/report/__init__.py`, `tests/__init__.py`, `.gitignore` (append `.cache/`, `__pycache__/`, `.coverage`, `htmlcov/`, `*.pyc`, `report-*.json`)
- Modify: `requirements.txt` (replace with pinned list — see Global Constraints and spec §6.6)

**Interfaces:**
- Produces: a `pip install -e .` installable package exposing `tddt` CLI entry point stub (that just prints "TDDT v2 — not implemented yet" and exits 0).

- [ ] **Step 1: Write `pyproject.toml`**

Content: name `tddt`, version `2.0.0.dev0`, Python `>=3.11`, dependencies from spec §6.6 pinned, `[project.scripts] tddt = "tddt.cli:main"`, `[tool.ruff]` with rules `E,F,W,I,UP,B,SIM,PLE`, `[tool.ruff.lint.per-file-ignores]` for tests, `[tool.mypy]` with `strict = true, files = "tddt/core"`, `[tool.pytest.ini_options]` with `markers = ["active: tests that make outbound network connections"]` and `addopts = "-ra --strict-markers"`.

- [ ] **Step 2: Create empty `__init__.py` files** per Files list; `tddt/cli.py` with `def main(): print("TDDT v2 — not implemented yet")`.

- [ ] **Step 3: Verify install**

Run: `pip install -e . && tddt`
Expected: prints the stub message, exits 0.

- [ ] **Step 4: Commit**

```
git add pyproject.toml tddt/ tests/ requirements.txt .gitignore
git commit -m "chore: scaffold tddt v2 package layout"
```

---

### Task 0.2: CI workflow + lint/type/except-pass guards

**Files:**
- Create: `.github/workflows/ci.yml`, `scripts/check_no_except_pass.sh`

**Interfaces:**
- Produces: a passing CI job on every push/PR: ruff, mypy on `tddt/core`, pytest (unit only), the except-pass guard.

- [ ] **Step 1: Write `scripts/check_no_except_pass.sh`**

Logic: `grep -rnE 'except[[:space:]]+[^:]*:[[:space:]]*(pass|$)' tddt/ && exit 1 || exit 0`. Make executable.

- [ ] **Step 2: Write `.github/workflows/ci.yml`**

Jobs: `lint` (ruff check), `types` (mypy on `tddt/core`), `test` (pytest -m "not active"), `guard` (bash scripts/check_no_except_pass.sh). Matrix Python 3.11, 3.12 on ubuntu-latest.

- [ ] **Step 3: Run guard locally**

Run: `bash scripts/check_no_except_pass.sh`
Expected: exit 0 (nothing in tddt/ yet).

- [ ] **Step 4: Commit**

```
git add .github/workflows/ci.yml scripts/
git commit -m "ci: lint, mypy, pytest, except-pass guard"
```

---

## Phase 1 — Core

### Task 1.1: BaseEntity + concrete entities + EntityGraph

**Files:**
- Create: `tddt/core/entity.py`, `tests/unit/test_entity.py`

**Interfaces:**
- Produces:
  - `BaseEntity` (frozen=True, eq=False, __hash__ on `.id`, metadata hash=False/compare=False — exact signature from spec §5.1 as corrected in self-review).
  - Concrete entities per spec §5.2: `Domain`, `Subdomain(Domain)`, `IPAddress`, `URL`, `Certificate`, `Port`, `CVE`, `Technology`, `Bucket`, `WHOISRecord`, `DNSRecord`, `Secret`, `TrackerID`, `TakeoverFinding`, `Finding`, `Email`, `Username`, `FullName`, `Phone`, `Service`, `Document`, `Website`, `Breach`, `Organization`.
  - `EntityGraph` with: `add(entity) -> bool`, `boost_confidence(id: str, delta: float) -> None`, `children_of(id: str) -> list[BaseEntity]`, `of_type(cls: type) -> list[BaseEntity]`, `all() -> Iterator[BaseEntity]`, `export() -> dict`, `_dispatched: set[tuple[str, str]]` (public contract: `is_dispatched(module_name, entity_id)` + `mark_dispatched(module_name, entity_id)`), `count_of_type(cls) -> int`.

- [ ] **Step 1: Write failing tests** in `tests/unit/test_entity.py`

Tests (names + assertions):
- `test_base_entity_id_is_stable_hash`: `Domain(value="x.com").id == Domain(value="x.com").id`
- `test_base_entity_id_differs_by_type`: `Domain(value="x.com").id != Email(value="x.com").id` (unlikely but prove it)
- `test_subdomain_is_instance_of_domain`: `isinstance(Subdomain(value="a.x.com"), Domain) is True`
- `test_metadata_mutation_does_not_break_hash`: construct entity, mutate `metadata["k"] = "v"`, hash unchanged, dict containment still works
- `test_control_char_value_hashes_cleanly`: `Email(value="x​@y.com").id` returns 12-hex string (addresses Review Focus #3)
- `test_secret_preview_truncates_and_hashes_full_value`: `Secret(value="A"*500)` → `metadata["preview"]` is ≤40 chars, `metadata["sha256"]` is 64-hex of full string, `value` IS the preview (not the full secret)
- `test_graph_add_returns_true_for_new_false_for_dedup`
- `test_graph_boost_confidence_updates_entity`: initial 0.3, boost +0.2 → 0.5
- `test_graph_dispatched_tracking`: `mark_dispatched` then `is_dispatched` → True
- `test_graph_max_entities_per_type_cap_logs_warning`: adding > cap raises `GraphCapError` or logs warning + skips (choose: log+skip to be non-fatal)
- `test_graph_count_of_type`: 3 Domain + 2 Email → `count_of_type(Domain) == 3`

- [ ] **Step 2: Run tests to confirm failure**

Run: `pytest tests/unit/test_entity.py -v`
Expected: all fail with import errors / undefined.

- [ ] **Step 3: Implement `tddt/core/entity.py`**

Follow spec §5. For `Secret`: in `__post_init__` (via `object.__setattr__` because frozen), truncate value to 40 chars, compute sha256 of original into metadata, store original full-length nowhere. For `GraphCapError`: define as subclass of `Exception` or just log and skip — pick skip-and-log. For `boost_confidence`: since entities are frozen, replace the stored instance using `dataclasses.replace(entity, confidence=new)`.

- [ ] **Step 4: Run tests to pass**

Run: `pytest tests/unit/test_entity.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```
git add tddt/core/entity.py tests/unit/test_entity.py
git commit -m "feat(core): entity model + graph with dedup, confidence boost, dispatch tracking"
```

---

### Task 1.2: Logger

**Files:**
- Create: `tddt/core/logger.py`, `tests/unit/test_logger.py`

**Interfaces:**
- Produces: `get_logger(name: str) -> logging.Logger`, `setup_logging(verbosity: int, log_dir: Path | None) -> None`. `verbosity`: 0=INFO, 1=DEBUG, 2=TRACE (TRACE as custom level 5).

- [ ] **Step 1: Failing tests**

- `test_setup_info_level`: after `setup_logging(0)`, root level is INFO.
- `test_setup_debug_with_v`: `setup_logging(1)` → DEBUG.
- `test_setup_trace_with_vv`: `setup_logging(2)` → logging level 5 (TRACE), `log.trace("msg")` works.
- `test_file_handler_rotates`: `setup_logging(0, Path(tmp))` creates `tmp/tddt.log` with RotatingFileHandler, max 10 MB × 5.
- `test_control_chars_escaped_in_log`: logging a string with `\x1b[31m` does NOT emit raw ANSI through the file handler (escaped). (Review Focus #3 partially.)

- [ ] **Step 2: Run → fail. Step 3: Implement. Step 4: Pass. Step 5: Commit** (`feat(core): structured logging with Rich console + rotating file handler`).

---

### Task 1.3: Settings + .env loader

**Files:**
- Create: `tddt/core/config.py`, `tests/unit/test_config.py`

**Interfaces:**
- Produces: `Settings` dataclass per spec §6.4 (all fields with defaults). `load_settings(env_path: Path | None = None, cli_overrides: dict | None = None) -> Settings`. Precedence: defaults < `.env` < CLI overrides.

- [ ] **Step 1: Failing tests**

- `test_defaults`: `load_settings()` returns Settings with threads=20, timeout=15.0, verify_tls=True, cache_enabled=True, max_iterations=5, max_runtime=600.0, all keys None.
- `test_env_loads_key`: tmp `.env` with `HUNTER_API_KEY=abc` → `settings.hunter == "abc"`.
- `test_cli_override_wins`: `.env` with `HUNTER_API_KEY=env` + `cli_overrides={"hunter": "cli"}` → `settings.hunter == "cli"`.
- `test_missing_env_file_warns_not_fails`: no `.env` → still returns defaults, logs a warning once.

- [ ] **Step 2-5**: write, run, implement, verify, commit (`feat(core): Settings dataclass with .env + CLI precedence`).

---

### Task 1.4: RateLimiter (per-host token bucket)

**Files:**
- Create: `tddt/core/rate_limit.py`, `tests/unit/test_rate_limit.py`

**Interfaces:**
- Produces: `RateLimiter(defaults: dict[str, float])` where defaults map host → req/sec. Method `acquire(host: str) -> None` blocks until a token is available. Thread-safe.

- [ ] **Step 1: Failing tests**

- `test_acquire_within_rate_does_not_block`: rate=10/s, 5 acquires in a tight loop → total time < 0.1s.
- `test_acquire_blocks_when_exhausted`: rate=2/s, 4 acquires → total time ≥ 1.0s and < 2.0s.
- `test_unknown_host_uses_default_rate`: not in defaults → 10/s fallback.
- `test_thread_safe`: 10 threads × 5 acquires on same host at 20/s → total time ≥ ~2.0s (serialized).

- [ ] **Step 2-5**: write, run, implement (simple deque of timestamps with `threading.Lock`), verify, commit (`feat(core): per-host rate limiter`).

---

### Task 1.5: HttpClient

**Files:**
- Create: `tddt/core/http.py`, `tests/unit/test_http.py`
- Depends on: Task 1.4 (RateLimiter), Task 1.3 (Settings), Task 1.2 (Logger).

**Interfaces:**
- Produces: `HttpClient(settings: Settings, cache_path: Path | None)` with methods `get(url, host_hint=None, **kw) -> Response`, `post(...)`, `head(...)`. Default host rate limits per spec §6.1 pre-registered. `get_client() -> HttpClient` singleton accessor. Cleanup: `close()`.

- [ ] **Step 1: Failing tests** (using `responses` or `requests_mock`)

- `test_get_200_returns_response`
- `test_retry_on_429_honors_retry_after`: mock 2× 429 with `Retry-After: 1` then 200 → total elapsed ≥ 2.0s, final status 200.
- `test_retry_exponential_on_500`: 3× 500 → stops after 3 retries, raises.
- `test_cache_hits_second_call`: with `cache_enabled=True`, same URL twice → underlying mock called once.
- `test_no_cache_when_disabled`: `cache_enabled=False` → both calls hit mock.
- `test_tls_verify_default_true`: inspect built session, `verify` is True.
- `test_insecure_flag_disables_verify`: Settings with `verify_tls=False` → session verify False.
- `test_rate_limit_enforced_per_host`: 4 GETs to crt.sh at 0.5 req/s → ≥ 6s.
- `test_user_agent_from_pool`: `client.get(...)` sends UA that is in the known pool.
- `test_proxy_passed_to_session`: Settings with `proxy="http://p:8080"` → session.proxies set.

- [ ] **Step 2-5**: write, run, implement using `requests_cache.CachedSession` + `HTTPAdapter(Retry(total=3, status_forcelist=[429,500,502,503,504], backoff_factor=0.5, respect_retry_after_header=True))` + RateLimiter wrapper, verify, commit (`feat(core): HttpClient with retry/cache/rate-limit/UA pool`).

---

### Task 1.6: BaseModule + register_module + MODULE_REGISTRY + autodiscover

**Files:**
- Create: `tddt/core/module.py`, `tests/unit/test_module.py`

**Interfaces:**
- Produces:
  - `class BaseModule(ABC)` with ClassVars `name`, `consumes`, `produces`, `active`, `requires_key`, `batch_size=1`, `min_confidence=0.3`, `mode`. Methods `__init__(client, settings, log)`, `run(entities: list[BaseEntity]) -> Iterable[BaseEntity]` abstract; concrete `validate_http_signature(url) -> dict`, `enrich_confidence(entity_id, factor)` (delegates to graph via a callback injected at engine time).
  - `@register_module(name=..., mode=[...], consumes=[...], produces=[...], active=..., requires_key=..., batch_size=1, min_confidence=0.3)` decorator populating `MODULE_REGISTRY`.
  - `MODULE_REGISTRY: dict[str, type[BaseModule]]`.
  - `applicable(entity_type: type[BaseEntity], mode: str, keyless_only: bool, allow_active: bool, settings: Settings) -> list[type[BaseModule]]`.
  - `autodiscover() -> int` — walks `tddt/modules/{corporate,user}/**/*.py` and imports them, returns count of registered modules.

- [ ] **Step 1: Failing tests**

- `test_decorator_registers_class`: define a fake `FooMod` with decorator, assert in `MODULE_REGISTRY`.
- `test_duplicate_name_raises`: two modules with same `name` → `ValueError` at decoration time.
- `test_applicable_filters_by_entity_type`: register one Email-consuming + one Domain-consuming, query for Domain → only domain one.
- `test_applicable_filters_by_mode`: corporate-only module not returned for user mode query.
- `test_applicable_filters_active_in_light`: `allow_active=False` excludes active modules.
- `test_applicable_filters_missing_key`: requires_key="hunter", `settings.hunter is None`, `keyless_only=False` → excluded.
- `test_applicable_filters_keyless_only`: `keyless_only=True`, requires_key="hunter" → excluded even if key configured.
- `test_subclass_consume_match`: module `consumes=[Domain]`, query with `Subdomain` → included (via `issubclass`).
- `test_autodiscover_finds_modules`: create a fake file under `tests/_fixtures/fake_modules/`, call autodiscover with that path → count ≥ 1.

- [ ] **Step 2-5**: write, run, implement (decorator stores in `MODULE_REGISTRY`, `applicable` iterates with `issubclass` on consumes, `autodiscover` uses `importlib.import_module` + `pkgutil.walk_packages`), verify, commit (`feat(core): BaseModule, @register_module, applicable(), autodiscover`).

---

### Task 1.7: CorrelationEngine

**Files:**
- Create: `tddt/core/engine.py`, `tests/unit/test_engine.py`, `tests/integration/test_engine_integration.py`
- Depends on: 1.1 (graph), 1.5 (http), 1.6 (registry).

**Interfaces:**
- Produces: `CorrelationEngine(client, settings, logger)` with `scan(seeds: list[BaseEntity], mode: str) -> EntityGraph` and `progress_callback: Callable[[int, EntityGraph], None] | None`.
- Honors `max_iterations`, `max_runtime`, `max_entities_per_type`, `downstream_threshold` (0.5), `batch_size`, `min_confidence`, `_dispatched` dedup, `active`/`keyless` filters.
- Writes `graph.metadata["terminated_reason"]` ∈ {"converged", "max_iterations", "max_runtime"}.

- [ ] **Step 1: Failing unit tests** with fake modules

- `test_engine_runs_applicable_module_on_seed`: register fake `FakeMod` consuming `Domain` producing `Email`, scan `[Domain("x.com")]` → graph has an Email.
- `test_engine_dedup_prevents_rerun`: FakeMod produces same Email twice across iterations → graph has 1 Email, `_dispatched` prevents second module invocation on same seed.
- `test_engine_stops_at_max_iterations`: fake chain always producing a new entity → graph.metadata["terminated_reason"] == "max_iterations" when `max_iterations=3`.
- `test_engine_stops_at_max_runtime` *(Review Focus #2)*: FakeMod that `time.sleep(0.3)` on each entity, 10 seed entities, `max_runtime=0.5` → terminated_reason == "max_runtime", graph still exportable with partial results.
- `test_engine_respects_downstream_threshold`: FakeMod produces entity with `confidence=0.3`, no downstream module runs on it.
- `test_engine_respects_max_entities_per_type` *(Review Focus #1)*: fake produces 5000 Subdomain, graph tops at 2000, warning logged.
- `test_engine_skips_active_in_light`: active module not instantiated when `allow_active=False`.
- `test_engine_isolates_failing_module`: FakeMod raises, scan completes, log.exception recorded, graph still populated by other modules.
- `test_engine_control_char_in_seed_value_does_not_crash` *(Review Focus #3)*: seed `Email("x​@y.com")` → no exception.
- `test_engine_no_a_record_still_runs_passive_modules` *(Review Focus #5)*: seed Domain with no derived IPAddress → modules that consume `Domain` still execute (crtsh fake, email fake).

- [ ] **Step 2-5**: write, run, implement main loop per spec §7.3, verify, commit (`feat(core): CorrelationEngine with convergence, caps, and FP controls`).

---

## Phase 2 — CLI + Report

### Task 2.1: CLI entrypoint with subcommands

**Files:**
- Create/Modify: `tddt/cli.py`, `tests/unit/test_cli.py`
- Depends on: 1.1-1.7.

**Interfaces:**
- Produces: `main(argv: list[str] | None = None) -> int` dispatching subcommands per spec §10.1:
  - `corp <domain> [flags]` → engine.scan with seed `Domain(domain)`, mode `"corporate"`.
  - `user [--email X] [--username X] [--name "X X"] [--phone X] [flags]` → engine.scan with multi-seed, mode `"user"`.
  - `update-wmn-db` → downloads WhatsMyName JSON to `~/.cache/tddt/wmn.json` (impl stub returning 0, real logic in Task 4.3).
  - `clear-cache` → wipes `~/.cache/tddt/http.sqlite`.
  - `list-modules [--mode M] [--keyless-only]` → prints registered modules.
- Common flags per spec §10.1.
- `user` without any input flag → `argparse.error` → exit code 2.

- [ ] **Step 1: Failing tests**

- `test_corp_requires_domain`: `main(["corp"])` → exit 2.
- `test_user_requires_at_least_one_input` *(Review Focus #4)*: `main(["user"])` → exit 2 with error mentioning email/username/name/phone.
- `test_user_accepts_multi_input`: `main(["user", "--email", "x@y.com", "--name", "Mario Rossi"])` → calls engine with 2 seeds.
- `test_light_flag_sets_allow_active_false`: inspect engine call args.
- `test_only_keyless_flag_sets_filter`: inspect.
- `test_list_modules_prints_registered`: pre-register 2 fakes, run `main(["list-modules"])`, captured stdout contains both names.
- `test_output_default_path_pattern`: `main(["corp", "example.com"])` with no `-o` → report file at `report-example.com-<timestamp>.json`.
- `test_clear_cache_removes_file`: tmp cache file exists → after `main(["clear-cache"])` it is gone.

- [ ] **Step 2-5**: write, run, implement with argparse subparsers, verify, commit (`feat(cli): subcommands corp/user/update-wmn-db/clear-cache/list-modules with full flag set`).

---

### Task 2.2: JSON exporter

**Files:**
- Create: `tddt/report/json_exporter.py`, `tests/unit/test_json_exporter.py`

**Interfaces:**
- Produces: `export_json(graph: EntityGraph, scan_meta: dict, path: Path) -> None` writing the schema from spec §10.2.

- [ ] **Step 1: Failing tests**

- `test_schema_shape`: top-level keys exactly `{"scan", "entities", "profile"}` (profile omitted or null in corporate mode — pick null for schema stability).
- `test_entities_by_type_grouped`: 3 Domain, 2 Email → `entities.by_type.Domain` has 3, `.Email` has 2.
- `test_edges_recorded`: a child entity with parent_id → edges list has that pair.
- `test_secret_full_value_never_in_output`: Secret produced from value `"KEY-AAAAA..."`, dumped JSON does NOT contain the full string, DOES contain preview + sha256.
- `test_output_is_valid_json`: `json.loads(path.read_text())` succeeds.

- [ ] **Step 2-5**: implement, verify, commit (`feat(report): JSON exporter with stable schema and secret redaction`).

---

### Task 2.3: Markdown + HTML exporters

**Files:**
- Create: `tddt/report/markdown_exporter.py`, `tddt/report/html_exporter.py`, `tests/unit/test_md_html_exporter.py`

**Interfaces:**
- Produces: `export_markdown(graph, scan_meta, path)`, `export_html(graph, scan_meta, path)`. Markdown uses sections per spec §10.2. HTML uses `rich.console.Console(record=True)` + `export_html(inline_styles=True)`.

- [ ] **Step 1: Failing tests**

- `test_markdown_has_section_per_group`: output contains headings `## Identity`, `## DNS`, `## Attack Surface`, `## Emails`, `## Secrets`.
- `test_markdown_no_full_secret`: same redaction check.
- `test_html_self_contained`: output has `<html>` and no external `<link>` to CDN; opens standalone.
- `test_html_includes_summary_table`.

- [ ] **Step 2-5**: implement, verify, commit (`feat(report): Markdown and HTML exporters`).

---

### Task 2.4: ProfileAggregator

**Files:**
- Create: `tddt/report/profile_aggregator.py`, `tests/unit/test_profile_aggregator.py`

**Interfaces:**
- Produces: `build_profile(graph: EntityGraph) -> dict` returning the structure in spec §10.3. Called by `json_exporter` only when `scan.mode == "user"`.

- [ ] **Step 1: Failing tests**

- `test_profile_primary_has_largest_cluster`: 3 Service with avatar hash A + 2 with avatar hash B → primary cluster has 3, alternates has 2.
- `test_profile_aggregates_linked_emails`: Email with parent_id of a Service in primary cluster → appears in `primary.emails`.
- `test_profile_resolves_fullname_conflict`: 2 FullName candidates, pick highest confidence; tie → both with `conflicting: true`.
- `test_profile_empty_graph`: empty graph → `{"primary": {}, "alternates": []}`.
- `test_profile_confidence_floor`: Service with confidence 0.4 not included (floor 0.6 per spec §9.10).

- [ ] **Step 2-5**: implement, verify, commit (`feat(report): ProfileAggregator for user mode with cluster-based attribution`).

---

## Phase 3 — Corporate Modules

Each task in this phase follows the same shape:
1. For each module in the group, write one unit test using `pytest-vcr` cassette for one real target and (where relevant) one empty target.
2. Implement module as `BaseModule` subclass with `@register_module` decorator.
3. Verify test passes.
4. Commit the group.

The spec §8 tables give the exact `consumes`/`produces`/`active`/`requires_key` for each module. The implementer references the table; the plan does not duplicate it.

### Task 3.1: Subdomain enumeration (5 modules)

**Files:**
- Create: `tddt/modules/corporate/subdomain/{crtsh,hackertarget,otx_passive_dns,rapiddns,wayback_extract}.py` + 5 test files + cassettes.

**Interfaces:**
- Produces: 5 modules registered under `corporate.subdomain.*` consuming `Domain` or `URL` and producing `Subdomain`.

- [ ] **Steps**: for each module — failing test (produces ≥1 Subdomain on fixture target; 0 Subdomain on known-empty target; retry-on-404 does NOT loop infinitely for crtsh per bug §2.7) → implement → pass → commit as one group (`feat(corporate/subdomain): 5 keyless subdomain enumeration sources`).

---

### Task 3.2: DNS deep + AXFR + DoH + wildcard detector

**Files:**
- Create: `tddt/modules/corporate/dns/{deep,axfr_attempt,doh_multi,wildcard_detector}.py` + 4 test files + cassettes.

**Interfaces:**
- Produces: `dns.deep` consumes `Domain` produces `DNSRecord`+`Subdomain` (CAA, DKIM selectors, BIMI, MX, SPF, DMARC, NS, SOA, CNAME). `dns.axfr_attempt` active, tries AXFR on each NS. `dns.doh_multi` cross-checks resolution across Cloudflare/Google/Quad9/NextDNS. `wildcard_detector` queries 3 random long subdomain names; if any resolves, writes a flag in graph metadata.

- [ ] **Steps**: tests per module (SPF record parsing per flavor, DMARC policy extraction, AXFR gracefully fails when refused, DoH resolver fallback). Review Focus #1 wildcard test lives here (`test_wildcard_sets_flag_and_lowers_subdomain_confidence`).
- Commit: `feat(corporate/dns): deep DNS + AXFR + DoH + wildcard`.

---

### Task 3.3: Netblock (ipapi HTTPS + reverse ASN)

**Files:**
- Create: `tddt/modules/corporate/netblock/{ipapi,reverse_asn}.py` + tests.

- [ ] Tests cover: ipapi URL uses `https://` (bug §2.6 fix), batch of 100 IPs, reverse_asn uses bgp.he.net/hackertarget scrape, graceful on 429.
- Commit: `feat(corporate/netblock): HTTPS ip-api batch + reverse ASN expansion`.

---

### Task 3.4: Web surface base (http inspector + tech fingerprint + security headers + favicon)

**Files:**
- Create: `tddt/modules/corporate/web/{http_inspector,tech_fingerprint,security_headers,favicon_recon}.py` + tests.

- [ ] **Key fix in `tech_fingerprint`**: must consume `URL` (not re-fetch), reusing the response captured by `http_inspector` via a `URL` entity whose metadata carries the response body/headers. Test: a single HTTP mock serving one response → both modules together produce exactly ONE outbound call (fixes bug §2.secondary).
- Favicon DB extended to ~500 entries imported from FavFreak-style open source.
- TLS verify ON asserted in tests.
- Commit: `feat(corporate/web): http inspector, tech fingerprint, security headers, favicon`.

---

### Task 3.5: Web surface active (takeover.verifier + cors.misconfig + tls.deep)

**Files:**
- Create: `tddt/modules/corporate/web/{takeover_verifier,cors_misconfig,tls_deep}.py` + tests.

- [ ] **Takeover tests** fix bug §2.2: CNAME to a live GitHub Pages (fingerprint absent) → NO `TakeoverFinding`; CNAME to an unclaimed GitHub Pages (fingerprint "There isn't a GitHub Pages site here") → finding. Fingerprint DB covers GitHub Pages, Heroku, S3, Zendesk, Shopify, Fastly, Surge, Readme.io, Bitbucket, Pingdom.
- CORS test: send `Origin: evil.com` → if reflected in `Access-Control-Allow-Origin`, finding.
- TLS test: builds via `ssl.create_default_context`, enumerates supported protocol versions by handshake attempt per version, reports deprecated (SSLv3, TLS 1.0, TLS 1.1) if accepted.
- All three `active=True`. Verified not instantiated when `--light`.
- Commit: `feat(corporate/web): takeover verifier, CORS misconfig, TLS deep`.

---

### Task 3.6: Analytics + Wayback (6 modules)

**Files:**
- Create: `tddt/modules/corporate/analytics/{ids,reverse}.py` + `tddt/modules/corporate/wayback/{wayback_machine,commoncrawl,otx,urlscan}.py` + tests.

- [ ] **Fix §2.11-related**: urldna polling moves to Task 3.10. Wayback modules each test on fixtures with and without juicy results.
- Commit: `feat(corporate): analytics IDs + Wayback multi-source`.

---

### Task 3.7: Secrets scanning (4 modules)

**Files:**
- Create: `tddt/modules/corporate/secrets/{js_secrets,github_dork,gitlab_dork,pastebin_dork}.py` + tests.

- [ ] **js_secrets FP fixes (bug §2.10)**:
  - Entropy check: Shannon entropy ≥ 3.5 on captured group.
  - Deny-list placeholders: `{"xxxxx", "your-key", "example", "null", "undefined", "placeholder", "changeme", "test", "demo"}`.
  - Strict netloc: `netloc == domain or netloc.endswith("." + domain)` (not `in`).
  - Tests: a minified JS containing `password: "placeholder"` → ZERO secrets; same JS with `AKIA[random 16 upper]` → ONE Secret.
- Commit: `feat(corporate/secrets): JS scanner with FP controls + GitHub/GitLab/Pastebin dorking`.

---

### Task 3.8a: Email — search engines (7 modules)

**Files:**
- Create: `tddt/modules/corporate/email/{bing_scrape,ddg_scrape,crtsh_san,google_dork,pastebin_dork,theharvester_asian,linkedin_bing}.py` + tests.

- [ ] Each has one cassette per real target; `linkedin_bing` also produces `FullName` entities. Tests assert at least 1 Email on the fixture, 0 on empty-domain fixture, logger emits warning on 403 (not silent fail per bug §2.14).
- Commit: `feat(corporate/email): search-engine and dork-based harvesters (7 sources)`.

---

### Task 3.8b: Email — code/validation/synth (7 modules)

**Files:**
- Create: `tddt/modules/corporate/email/{github_search,gitlab_search,hunter,phonebook,wayback_scrape,pattern_deducer,emailrep_validator}.py` + tests.

- [ ] **github_search fix (bug §2.5)**: honors optional `settings.github` token (10× rate limit); logs explicitly when hitting unauthenticated 10 req/min cap. `phonebook` logs when response HTML is a login page (bug §2.14 fix). `pattern_deducer` is synth: no HTTP; takes graph's Email entities and emits one `TrackerID`-like entity (or dedicated `NamingPattern` entity — pick existing: reuse `metadata` on `Domain` seed instead to avoid new entity type).
- Commit: `feat(corporate/email): code platforms, validators, naming-pattern deducer`.

---

### Task 3.8c: Email active (smtp_bruteforce)

**Files:**
- Create: `tddt/modules/corporate/email/smtp_bruteforce.py` + test + `tddt/data/common_names_it.txt`, `common_names_en.txt` (500 names each).

- [ ] `active=True`, consumes `Domain` with `metadata["naming_pattern"]`, produces `Email`. Test: skipped by default (marker `@pytest.mark.active`); mock SMTP server for CI verifies no crash.
- Commit: `feat(corporate/email): SMTP RCPT bruteforce (active, opt-in)`.

---

### Task 3.9: Bucket + Breach (5 modules)

**Files:**
- Create: `tddt/modules/corporate/{bucket/{grayhat,bruteforce},breach/{hibp_scrape,dehashed_scrape,gravatar}}.py` + tests.

- [ ] **Bucket bruteforce fix (bug §2.12)**: pool threaded, honors `netblock` HTTP client rate limit. Test asserts 100 bucket URLs tried in < 10s with 20 threads vs the current serial > 100s.
- Commit: `feat(corporate): cloud bucket finder (parallel) + breach lookups (HIBP, Dehashed, Gravatar)`.

---

### Task 3.10: Vuln + External (5 modules)

**Files:**
- Create: `tddt/modules/corporate/{vuln/{internetdb,port_scan,cve_enricher},external/{urldna,photon}}.py` + tests.

- [ ] **InternetDB fix (bug §2.4)**: when `len(potential_ports) >= 100`, confidence of returned Port entities drops to 0.5 and metadata flags `verified=False`. CVE entities ALWAYS emitted when InternetDB returns `vulns` (fixes bug §2.3; display is Task 2.3's job).
- **port_scan**: top-1000 TCP ports probed in parallel; `active=True`.
- **cve_enricher**: consumes `CVE`, enriches via NVD JSON API (no key needed).
- **urldna fix (bug §2.11)**: polling loop with `max_poll=12 × 5s` instead of `time.sleep(5)`.
- **photon fix (bug §2.13)**: uses `sys.executable`, timeout 300s, output folder preserved on timeout for partial results.
- Commit: `feat(corporate): vuln surface (InternetDB, port scan, CVE enricher) + external (urlDNA, Photon)`.

---

## Phase 4 — User Modules

### Task 4.1: Derive modules (4)

**Files:**
- Create: `tddt/modules/user/derive/{email_to_username,fullname_to_username,phone_normalize,email_to_name}.py` + tests.

**Interfaces:**
- All produce entities with `confidence=0.3`. `phone_normalize` consumes raw `Phone` string, produces normalized E.164 `Phone` with `confidence=1.0` if valid, else 0.0 (filtered out).

- [ ] Tests cover: 15 username candidates from `mario.rossi@x.it`, 15 variants from `"Mario Rossi"`, invalid phone returns nothing.
- Commit: `feat(user/derive): username/name/phone derivation`.

---

### Task 4.2: Username quick_validator (bootstrap FP control)

**Files:**
- Create: `tddt/modules/user/username/quick_validator.py` + test.

**Interfaces:**
- `min_confidence=0.3` (unique: it is the only module that runs on candidates). Probes top 5 sites (GitHub, Reddit, Keybase, GitLab, HackerNews) per candidate. If ≥2 sites respond with "profile exists" fingerprint → promote candidate's confidence to 0.6 (triggers downstream whatsmyname). Else degrade to 0.1.

- [ ] Tests: known-existing username on GitHub → promoted; random nonsense username → degraded.
- Commit: `feat(user/username): quick_validator bootstrap FP control (resolves Open Item §12.5)`.

---

### Task 4.3: Username whatsmyname + service_validator + cross_site_attribution + `update-wmn-db` command

**Files:**
- Create: `tddt/modules/user/username/{whatsmyname,service_validator,cross_site_attribution}.py` + tests. Modify: `tddt/cli.py` `update-wmn-db` subcommand (stub from 2.1 now real).

**Interfaces:**
- `whatsmyname`: consumes `Username` (min_confidence 0.5), loads `~/.cache/tddt/wmn.json` on first use (download if missing), produces `Service` with per-site confidence 0.5 (pre-validation).
- `service_validator` 🎯: consumes `Service`, fetches profile page, verifies username in HTML + extracts avatar/bio/followers/join_date into metadata; promotes to 0.7 on success, degrades to 0.1 if soft-404 detected.
- `cross_site_attribution` 🎯: `batch_size=0` (all Services at once), clusters by avatar hash + bio similarity, boosts confidence per cluster size.

- [ ] Tests cover: WhatsMyName JSON schema parsing, soft-404 detection (test fixture with site that returns 200 containing "User not found"), cluster boost with 3 Service sharing avatar hash → all confidence +0.3.
- Commit: `feat(user/username): WhatsMyName + content validator + cross-site attribution clustering`.

---

### Task 4.4: Username profile scrapers (3)

**Files:**
- Create: `tddt/modules/user/username/{github_profile,gitlab_profile,social_scrape}.py` + tests.

- [ ] GitHub profile scrape extracts email from commits (`github.com/{user}.gpg` not always present; fall back to API `/users/{u}/events/public` with keyless rate limit, or token). `social_scrape` uses nitter mirror (list of fallback hosts).
- Commit: `feat(user/username): GitHub/GitLab/social profile scrapers`.

---

### Task 4.5: User Email (8 modules)

**Files:**
- Create: `tddt/modules/user/email/{hibp_scrape,dehashed_scrape,gravatar,holehe,github_commit_search,google_dork,emailrep_validator,smtp_verify}.py` + tests.

- [ ] `holehe` module is a thin adapter calling the `holehe` package (confirmed free open-source). `smtp_verify` is `active=True`. `github_commit_search` uses optional token.
- Commit: `feat(user/email): breach + gravatar + holehe + github commits + dork + validators`.

---

### Task 4.6: FullName profiling (7 modules)

**Files:**
- Create: `tddt/modules/user/fullname/{google_dork,bing_dork,linkedin_bing,cv_hunter,personal_site,reverse_whois,crtsh_san}.py` + tests.

- [ ] `cv_hunter` dork `"Full Name" filetype:pdf OR filetype:doc OR filetype:docx`. `personal_site` dork over personal-looking TLDs. `reverse_whois` scrapes viewdns.info.
- Commit: `feat(user/fullname): CV hunter, personal site, LinkedIn, reverse-WHOIS, name profiling`.

---

### Task 4.7: Phone (4 modules)

**Files:**
- Create: `tddt/modules/user/phone/{libphonenumbers,google_dork,social_probe,truecaller_scrape}.py` + tests.

- [ ] `social_probe` is `active=True`, gated by `--aggressive-phone`.
- Commit: `feat(user/phone): phone enrichment (metadata, dork, social, truecaller)`.

---

### Task 4.8: Document + Service pivot (4 modules)

**Files:**
- Create: `tddt/modules/user/document/{pdf_metadata,text_mine}.py`, `tddt/modules/user/service/{profile_scraper,avatar_hasher}.py` + tests.

- [ ] `pdf_metadata` uses `pypdf`. `text_mine` reads text via `pypdf` + `python-docx`. `profile_scraper` is per-platform (dispatches on `metadata["platform"]`). `avatar_hasher` uses perceptual hash (via `imagehash` only if the user explicitly adds it — else SHA-256 of resized image via stdlib + PIL IF available; the plan prefers SHA-256 of raw bytes to avoid new dependency and matches "cluster by exact match", acceptable).
- Commit: `feat(user)(service+document): profile scraper, avatar hasher, PDF metadata, text mine`.

---

### Task 4.9: Cross-mode flag (opt-in user → corporate)

**Files:**
- Modify: `tddt/cli.py` (handle `--follow-domains` after user scan), `tddt/report/json_exporter.py` (nests `cross_mode_results`).

- [ ] Test: user scan produces a `Website` → with `--follow-domains`, after main loop, a corporate scan runs on that domain → JSON has `cross_mode_results.corporate` section.
- Commit: `feat(user): --follow-domains opt-in cross-mode scan`.

---

## Phase 5 — Finalization

### Task 5.1: Legacy main.py shim with deprecation warning

**Files:**
- Modify: `main.py` (replace content).

- [ ] Content: parse legacy args, print deprecation warning to stderr, re-dispatch to `tddt.cli.main` with translated args. Test by running `python main.py example.com --light` and asserting it invokes `tddt corp example.com --light`.
- Commit: `chore: legacy main.py shim redirects to tddt v2 cli with deprecation warning`.

---

### Task 5.2: README + .env.example rewrite

**Files:**
- Modify: `README.md`, `.env.example`.

- [ ] README documents: install (`pipx install .`), `tddt corp`, `tddt user`, flags, example runs, migration from v1 (one-paragraph).
- Commit: `docs: rewrite README and .env.example for v2`.

---

### Task 5.3: End-to-end integration tests + remove v1 modules

**Files:**
- Create: `tests/integration/test_corp_scan_light.py`, `tests/integration/test_user_scan_email.py`.
- Delete: `modules/` (v1 directory), `report.json`, `tmp` (both v1 leftovers).

- [ ] Integration tests use VCR cassettes against a known test target (e.g. `example.com` with recorded fixtures) and assert the JSON report shape matches spec §10.2.
- Verify: `pip install -e . && tddt corp example.com --light --no-cache` produces a report file.
- Commit: `chore: remove v1 module tree + v1 leftover files; v2 migration complete`.

---

## Acceptance Verification

After Phase 5, run the AC checks from spec §11:
- `pytest -m "not active" --cov=tddt --cov-report=term-missing` → ≥70% overall, ≥90% on `tddt/core`.
- `bash scripts/check_no_except_pass.sh` → exit 0.
- Manual: `tddt corp example.com --light -v` produces non-empty JSON with `Subdomain`, `Email`, `DNSRecord`, `Technology`, `Secret` entity types (AC2).
- Manual: `tddt user --name "Mario Rossi" -v` produces ≥10 Username candidates visible in `-vv` log and runs `quick_validator` before `whatsmyname` (AC5).
- Add one new fake module file in `tddt/modules/corporate/subdomain/zz_test.py` with `@register_module` → `tddt list-modules` includes it with zero other edits (AC8).

---

**End of implementation plan.**
