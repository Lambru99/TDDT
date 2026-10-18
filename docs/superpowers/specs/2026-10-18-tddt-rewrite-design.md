# TDDT v2 — Rewrite Design Spec

**Date**: 2026-10-18
**Author**: Lambru (latiniludovico@gmail.com) + Claude Opus 4.7 (brainstorming)
**Status**: Draft for approval
**Scope**: Full architectural rewrite of TDDT under the "Core + Plugin registry" approach, adding keyless-first module coverage and a new User OSINT mode.

---

## 1. Executive Summary

TDDT è oggi un tool EASM Python monolitico in cui `main.py` orchestra ~15 moduli di recon su un dominio. Funziona ma soffre di:

- **Modalità `--light` non ermetica**: Photon (active) parte comunque.
- **Molti silent fail** (`except Exception: pass` sparsi) che nascondono fallimenti sistematici (Bing/DDG/GitHub rate-limiting).
- **Falsi positive strutturali**: takeover non verificati, JS secrets senza entropy check, substring match sui netloc.
- **CVE raccolte ma mai mostrate**.
- **Email harvester poco efficace** rispetto a SpiderFoot (sorgenti insufficienti).
- **Nessuna correlazione**: ogni modulo è isolato, non alimenta il successivo.
- **Nessun supporto a OSINT su persone** (solo domini).

Questa spec definisce la riscrittura in architettura **Core + Plugin registry** con:
- Modello Entity tipizzato come lingua comune tra moduli.
- Correlation engine iterativo con dedup/cycle prevention.
- Catalogo esteso di moduli (~45 corporate + ~32 user mode), ~90% keyless.
- Modalità separata **User OSINT** con tre layer sopra Sherlock: FP killer, profiling, auto-pivot.
- Infrastructure condivisa: HTTP client con retry/rate-limit/cache, logging strutturato, zero `except: pass`.

**Vincoli di scelta** (confermati durante il brainstorming):
- Concorrenza: `ThreadPoolExecutor + requests` (non asyncio).
- API key sempre opzionali: scan completamente keyless deve dare valore reale.
- Pivot iterativo full-graph nella user mode (con cap sulla profondità).
- Cross-mode user→corporate automatico: **opt-in** via flag, non default.
- Migration graduale (non big-bang), compatibilità del vecchio CLI mantenuta durante la transizione.

---

## 2. Problem Statement (dettaglio bug correnti da risolvere)

Riferimento alla code review precedente. Fix verranno mappati a moduli specifici in §8-§9.

### Critici / logici

1. `--light` → `run_all=True` fa partire Photon (active) comunque. `main.py:105-114`.
2. Takeover DNS segnalato su solo pattern matching, nessuna verifica attiva del CNAME. `dns_deep.py:83-94`. Factory di falsi-positive.
3. CVE da InternetDB salvate in `vuln_data['cves']` ma mai mostrate a schermo. `main.py:234`, `vuln_scan.py:48-53`.
4. Port scan passivo quando `len(potential_ports) >= 100`: usa la lista "potential" come se fosse verificata. `vuln_scan.py:45-46`.
5. GitHub code search senza token: rate limit 10 req/min → 403 quasi certo. `email_harvester.py:88-115`.
6. `ip-api.com` chiamato in HTTP (non HTTPS). `netblock.py:9`.
7. `crt.sh` retry loop buggato (continua a ritentare su 404). `recon.py:24-45`.
8. `verify_live_domains` itera dict invece di `as_completed`. `recon.py:92-103`.
9. `verify=False` ovunque: TLS verification silently disabled. `http_inspector.py`, `favicon_recon.py`, `id_analytics.py`, `js_secrets.py`, `tech_fingerprint.py`.
10. JS secrets alti FP: regex `password:` matcha placeholder; `self.domain in parsed.netloc` matcha `evilexample.com.attacker.site`. `js_secrets.py:75`.
11. urlDNA: `time.sleep(5)` arbitrario invece di polling. `urldna_recon.py`.
12. Bucket brute-force seriale: 100 richieste in sequenza, no rate-limit, no thread. `bucket_finder.py:83-112`.
13. Photon hardcoded `python3`: fallisce su Windows; timeout 180s troppo basso con `-l 3 --wayback`. `photon_wrapper.py`.
14. Phonebook.cz silent fail (richiede login dal 2023). `email_harvester.py:150-163`.
15. `__pycache__` committato, `report.json` committato (potenziale leak).

### Secondari

- No wildcard DNS detection → ogni subdomain inesistente appare live.
- WHOIS: no RDAP fallback, timeout 10s troppo basso.
- `requirements.txt` senza pin.
- Zero test, nessun CI.
- SPF non segue `include:`. No DKIM/CAA/BIMI.
- Favicon DB con solo ~15 signature.
- TechFingerprint fa un GET duplicato rispetto a HttpInspector.
- User-Agent diverso in ogni modulo.

---

## 3. Goals and Non-Goals

### Goals

- **G1**: Fix di tutti i bug §2.1-§2.15.
- **G2**: Email harvesting che trovi un numero di indirizzi paragonabile a SpiderFoot (15+ sorgenti aggregate, dedup, confidence boost quando confermato cross-source).
- **G3**: Scan completamente funzionale senza alcuna API key / account; API key danno boost ma non abilitano feature core.
- **G4**: Nuova modalità **User OSINT** con 4 input types (Email/Username/FullName/Phone), FP killer superiore a Sherlock, profiling layer (CV/sito/domini di proprietà), auto-pivot iterativo.
- **G5**: Aggiungere moduli deve costare un file + un decoratore. Zero modifiche al core per nuovi moduli.
- **G6**: Logging strutturato, zero `except: pass`. Ogni fallimento di sorgente visibile e tracciabile.
- **G7**: Report multi-formato: rich console live, JSON validato, Markdown, HTML standalone.
- **G8**: Testabilità: pytest + VCR cassette, 70%+ coverage sul `core/`, un test per modulo.
- **G9**: Migration graduale: il CLI legacy (`python main.py example.com`) resta funzionante durante la transizione con deprecation warning.

### Non-Goals (esplicito per prevenire scope creep)

- GUI/TUI dedicata (Rich console è sufficiente).
- Database persistente / scan ricorrenti / scheduling.
- Exploitation attiva (solo probing).
- Distributed scanning.
- Auto-update interno (si usa `pip install -U`).
- Supporto a `asyncio` (scelto thread model).
- Full backward-compat sul formato JSON legacy (schema cambia; migrazione documentata ma non supportata runtime).

---

## 4. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                            CLI                                   │
│  tddt corp <domain>  |  tddt user --email ...  |  tddt list-… │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                       CorrelationEngine                          │
│  seed → queue → applicable_modules → ThreadPool → graph.add()   │
│                     (iterate until convergence or cap)           │
└─────────┬─────────────────┬──────────────────────┬──────────────┘
          │                 │                      │
          ▼                 ▼                      ▼
┌──────────────┐  ┌──────────────────┐  ┌─────────────────────────┐
│ MODULE_REG   │  │   EntityGraph    │  │       HttpClient        │
│ decorators + │  │   (nodes+edges,  │  │  (requests + cache +    │
│ autodiscover │  │    dedup by id)  │  │   retry + rate-limit)   │
└──────┬───────┘  └──────────────────┘  └──────────┬──────────────┘
       │                                            │
       ▼                                            ▼
┌─────────────────┐                       ┌─────────────────────┐
│ BaseModule      │                       │  Settings  (.env +  │
│ subclasses      │                       │  CLI flags, keys    │
│ (corp + user)   │                       │  optional)          │
└─────────────────┘                       └─────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Report layer                             │
│   JSON exporter · Markdown · HTML · ProfileAggregator (user)    │
└─────────────────────────────────────────────────────────────────┘
```

**Data flow**: Il CLI parsa i flag, costruisce `Settings`, inizializza `HttpClient` e `Logger`, istanzia `CorrelationEngine`, passa i seed entity (es. `Domain("example.com")`). L'engine itera: per ogni entity nella queue trova i moduli applicabili dal registry, li esegue in parallelo, le entity prodotte vengono deduplicate e aggiunte al grafo, le nuove sopra `downstream_threshold` tornano in queue. Quando converge, il report layer esporta nei formati richiesti.

---

## 5. Entity Model

### 5.1 BaseEntity

```python
@dataclass(frozen=True, eq=False)
class BaseEntity:
    value: str
    confidence: float = 1.0            # 0.0-1.0, usato per FP management
    source_module: str = ""            # chi l'ha prodotta
    parent_id: str | None = None       # entity che ha causato la scoperta
    discovered_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict = field(default_factory=dict, hash=False, compare=False)

    @property
    def id(self) -> str:
        return hashlib.sha1(f"{type(self).__name__}:{self.value}".encode()).hexdigest()[:12]

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other) -> bool:
        return isinstance(other, BaseEntity) and self.id == other.id
```

Identità data da hash del valore normalizzato → deduplicazione automatica. `metadata` è `dict` mutabile ma escluso da hash/eq (è un piggyback per dati accessori: il "chi è" è `type + value`, non il payload). `frozen=True` protegge il value/confidence; il graph aggiorna `confidence` tramite un metodo `graph.boost_confidence(id, delta)` che sostituisce l'entity nel nodo.

### 5.2 Entità concrete

**Infrastructure** (corporate):
- `Domain` (lowercase, no protocol/path)
- `Subdomain(Domain)` — sottoclasse → un modulo che consuma `Domain` processa automaticamente anche subdomain
- `IPAddress` (v4/v6, normalizzata via `ipaddress`)
- `URL` (normalizzata via `urllib.parse`)
- `Certificate` (hash cert + metadata)
- `Port` ({ip, port, protocol})
- `CVE` (id + CVSS + descrizione)
- `Technology` (name + version + category)
- `Bucket` (provider + name + status)
- `WHOISRecord`
- `DNSRecord` (type + value)
- `Secret` (**preview, NOT valore completo**, + hash dedup)
- `TrackerID` (UA/G-Tag/GTM/AdSense)
- `TakeoverFinding` (CNAME + service + verifica contenuto)
- `Finding` (generico: CORS, TLS, SH — con tipo in metadata)

**People** (user mode):
- `Email` (lowercase, regex-validated)
- `Username` (string + confidence per FP)
- `FullName` (string + language + varianti normalizzate)
- `Phone` (E.164 via `phonenumbers`)
- `Service` (`{platform, username, url, profile_metadata}` — account trovato su sito X)
- `Document` (URL + tipo + match keyword)
- `Website` (URL personale attribuito)
- `Breach` (name + date + exposed data classes, **NO password**)
- `Organization` (azienda derivata da LinkedIn/GitHub profile)

### 5.3 EntityGraph

```python
class EntityGraph:
    def add(self, entity: BaseEntity) -> bool:  # True se nuova, False se dedup
    def children_of(self, entity_id: str) -> list[BaseEntity]:
    def of_type(self, entity_type: type[BaseEntity]) -> list[BaseEntity]:
    def all(self) -> Iterator[BaseEntity]:
    def export(self) -> dict:  # per report JSON
```

Dedup via `.id`; su dedup, boost di confidence se nuova sorgente conferma (`enrich_confidence`).

### 5.4 Scelte di design esplicite

- `Subdomain extends Domain` → riuso naturale dei moduli downstream.
- Confidence sempre presente, 1.0 di default; moduli FP-killer la modificano.
- `Secret` non contiene mai il valore completo → report JSON safe da committare.
- Nessuna `Company` o `Location` entity → metadata di altre.
- Nessun versioning temporale → fuori scope.

---

## 6. Core Infrastructure

### 6.1 HttpClient (singleton condiviso)

```python
client = get_client()  # init at CLI startup
r = client.get("https://crt.sh/...", host_hint="crt.sh")
```

**Interno**: `requests_cache.CachedSession` + `urllib3.Retry` adapter + rate limiter per-host + rotazione UA. Thread-safe per uso in `ThreadPoolExecutor`.

- **Retry**: 429/500/502/503/504 con `backoff_factor=0.5`, max 3 tentativi, honor di `Retry-After`.
- **Rate limit per-host**: token bucket in memoria. Default sensati pre-registrati:
  - `crt.sh`: 0.5 req/s
  - `bing.com` / `duckduckgo.com`: 1 req/s
  - `api.github.com`: 2 req/s (10 req/s con token)
  - `ip-api.com`: 0.75 req/s (45/min free tier)
  - `web.archive.org`: 1 req/s
- **Timeout**: 15s default, override per-call.
- **TLS**: `verify=True` sempre; `--insecure` globale per opt-out.
- **UA**: pool di 5 UA realistici, uno pescato per Session (non per-request, evita fingerprint anti-bot).
- **Proxy**: `--proxy http://...` → `session.proxies`.

### 6.2 Cache

- Backend SQLite via `requests-cache`.
- Path XDG: `~/.cache/tddt/http.sqlite` (Linux/macOS); `%LOCALAPPDATA%\tddt\http.sqlite` (Windows).
- TTL per-host configurabile:
  - `crt.sh`: 24h
  - `hunter.io`: 7d
  - `otx.alienvault.com`: 24h
  - `bing.com`/`duckduckgo.com`: 1h
  - `internetdb.shodan.io`: 1h
  - default: 30 min
- `--no-cache` disattiva; `--clear-cache` wipe + procede.

### 6.3 Logger

- `logging` + `rich.logging.RichHandler` (console).
- RotatingFileHandler `~/.cache/tddt/tddt.log`, 5 file × 10 MB.
- Livelli: `INFO` default, `-v` → `DEBUG`, `-vv` → `TRACE` (body preview + headers).
- Prefisso strutturato: `[corporate.email.bing] 403 → rate-limited, backing off 2s`.
- **Policy**: nessun `except Exception: pass` nel repo (enforced via code review + ruff rule custom).

### 6.4 Settings

```python
@dataclass
class Settings:
    threads: int = 20
    timeout: float = 15.0
    verify_tls: bool = True
    cache_enabled: bool = True
    proxy: str | None = None
    aggressive_email: bool = False
    aggressive_phone: bool = False
    follow_domains: bool = False       # user mode cross-mode opt-in
    max_iterations: int = 5
    max_runtime: float = 600.0
    # API keys (optional)
    hunter: str | None = None
    otx: str | None = None
    urlscan: str | None = None
    urldna: str | None = None
    grayhat: str | None = None
    github: str | None = None
    photon_path: str | None = None
```

Caricato da `.env` (via `python-dotenv`) + CLI flags. Nessuna chiave mai obbligatoria.

### 6.5 Error handling policy

Tre tier:
1. **Fatale**: `log.critical()` + `sys.exit(1)` (es. target DNS impossibile).
2. **Modulo fallito**: `log.exception()` + `{"error": "..."}` nel report, scan continua.
3. **Sorgente fallita** (dentro modulo multi-source): `log.warning()` + source skippata, altre proseguono.

L'engine non si ferma mai per errore di un singolo modulo.

### 6.6 Dipendenze nuove totali

```
requests>=2.31
requests-cache>=1.2         # NEW
dnspython>=2.5
beautifulsoup4>=4.12
rich>=13.7
mmh3>=4.1
python-dotenv>=1.0
phonenumbers>=8.13          # NEW
holehe>=1.63                # NEW (open-source, free)
pypdf>=4.0                  # NEW
python-docx>=1.1            # NEW
urldna (as today, optional)
```

Librerie **evitate volutamente**: `httpx`/`asyncio` (scelto thread), `pydantic` (dataclass basta), `tenacity` (urllib3.Retry basta), `loguru` (logging + rich).

---

## 7. Plugin Registry + Correlation Engine

### 7.1 BaseModule

```python
class BaseModule(ABC):
    name: ClassVar[str]
    consumes: ClassVar[list[type[BaseEntity]]]
    produces: ClassVar[list[type[BaseEntity]]]
    active: ClassVar[bool]
    requires_key: ClassVar[str | None]      # None = keyless
    batch_size: ClassVar[int] = 1           # 1 single, >1 grouped, 0 all-at-once
    min_confidence: ClassVar[float] = 0.3   # soglia per non essere invocato
    mode: ClassVar[list[str]]               # ["corporate"], ["user"], ["corporate","user"]

    def __init__(self, client: HttpClient, settings: Settings, log: Logger): ...

    @abstractmethod
    def run(self, entities: list[BaseEntity]) -> Iterable[BaseEntity]: ...

    # Utility shared (per FP management)
    def validate_http_signature(self, url: str) -> dict: ...
    def enrich_confidence(self, entity_id: str, factor: float) -> None: ...
    def cross_validate(self, entities: list[BaseEntity]) -> None: ...
```

### 7.2 Registry

Decoratore:

```python
@register_module(
    name="corporate.email.hunter",
    mode=["corporate"],
    consumes=[Domain],
    produces=[Email],
    active=False,
    requires_key="hunter",
)
class EmailHunter(BaseModule):
    def run(self, domains):
        for d in domains:
            ...
            yield Email(...)
```

**Autodiscover** via `importlib.import_module` + walk su `tddt/modules/corporate/**/*.py` e `tddt/modules/user/**/*.py` all'avvio del CLI. Aggiungere un modulo = creare un file nella cartella giusta.

Query:
```python
registry.applicable(
    entity_type=Domain,
    mode="corporate",
    keyless_only=False,
    allow_active=True,
    settings=settings,
)
```

### 7.3 CorrelationEngine

```python
class CorrelationEngine:
    max_iterations: int                 # da Settings
    threads: int
    max_runtime: float
    downstream_threshold: float = 0.5
    max_entities_per_type: int = 2000

    def scan(self, seeds: list[BaseEntity], mode: str) -> EntityGraph:
        graph = EntityGraph()
        queue = deque(seeds)
        for e in seeds: graph.add(e)

        start = time.monotonic()
        iteration = 0
        while queue and iteration < self.max_iterations:
            if time.monotonic() - start > self.max_runtime: break
            iteration += 1
            batch = list(queue); queue.clear()
            tasks = self._schedule(batch, mode, graph)
            with ThreadPoolExecutor(max_workers=self.threads) as ex:
                for new_entities in ex.map(self._run_task, tasks):
                    for ent in new_entities:
                        if graph.add(ent):
                            if ent.confidence >= self.downstream_threshold:
                                queue.append(ent)
            self._emit_progress(iteration, graph)
        return graph
```

### 7.4 Scheduling rules

Un modulo gira su una entity sse:
1. `type(entity)` è in `module.consumes` (o sottoclasse).
2. `mode` del modulo matcha quello della scan.
3. Modulo keyless OR chiave configurata.
4. Modulo passivo OR scan non in `--light`.
5. `entity.confidence >= module.min_confidence`.
6. Coppia `(module.name, entity.id)` non già dispatchata (tracking in `EntityGraph._dispatched: set[tuple[str, str]]`, aggiornato prima dell'esecuzione del task).

### 7.5 Cycle prevention

- `graph.add()` ritorna `False` se entity già nota → non ri-enqueue.
- Soglia `downstream_threshold` previene esplosione da Sherlock-like (400 Service a confidence 0.3 non triggerano moduli downstream).
- Hard caps: iterazioni, runtime, max_entities_per_type.

### 7.6 Progressive output

Dopo ogni iterazione, `rich.live.Live` aggiorna:
```
[Iter 2/5] 15 moduli eseguiti · 24 Subdomain → 18 IPAddress, 5 Technology, 2 Secret (34s)
```

### 7.7 FP reduction utilities nell'engine

Esposte a tutti i moduli:
- `validate_http_signature(url)` → fingerprint della soft-404 host-level (cached per host, usato da Sherlock-like).
- `enrich_confidence(entity_id, +0.2)` → bump quando sorgente nuova conferma.
- `cross_validate(services)` → cluster per avatar/bio hash → aggiorna confidence per attribuzione.

### 7.8 `--light` ermetico

Con `allow_active=False` l'engine non istanzia MAI moduli `active=True`. Risolve il bug Photon in light mode (§2.1).

---

## 8. Corporate Mode Module Catalog

~45 moduli totali, ~90% keyless. Legenda: 🔑 richiede key (opzionale), 🔥 active, ✨ nuovo, 🔧 esistente rifattorizzato (con fix bug mappati).

### 8.1 Infrastructure discovery

| Module | consumes → produces | passive | keyless | fix/notes |
|---|---|---|---|---|
| `subdomain.crtsh` 🔧 | `Domain` → `Subdomain` | ✓ | ✓ | §2.7 retry bug |
| `subdomain.hackertarget` 🔧 | `Domain` → `Subdomain` | ✓ | ✓ | — |
| `subdomain.otx_passive_dns` ✨ | `Domain` → `Subdomain` | ✓ | ✓ | — |
| `subdomain.rapiddns` ✨ | `Domain` → `Subdomain` | ✓ | ✓ | — |
| `subdomain.wayback_extract` ✨ | `URL` → `Subdomain` | ✓ | ✓ | riusa wayback data |
| `subdomain.wildcard_detector` ✨ | `Domain` → flag | ✓ | ✓ | precondizione (abbassa conf su wildcard DNS) |
| `dns.deep` 🔧 | `Domain` → `DNSRecord`, `Subdomain` | ✓ | ✓ | +CAA/DKIM/BIMI |
| `dns.axfr_attempt` ✨ | `Domain` → `Subdomain` | 🔥 | ✓ | zone transfer |
| `dns.doh_multi` ✨ | `Domain` → `IPAddress` | ✓ | ✓ | 4 DoH resolver cross-check |
| `netblock.ipapi` 🔧 | `IPAddress` → metadata | ✓ | ✓ | **HTTPS obbligatorio** (§2.6) |
| `netblock.reverse_asn` ✨ | `IPAddress` → `IPAddress` | ✓ | ✓ | espande pool ASN |

### 8.2 Web surface

| Module | consumes → produces | passive | keyless | fix/notes |
|---|---|---|---|---|
| `http.inspector` 🔧 | `Subdomain` → `URL`+meta | ✓ | ✓ | TLS verify ON (§2.9) |
| `tech.fingerprint` 🔧 | `URL` → `Technology`, headers | ✓ | ✓ | riusa response (fix GET doppio) |
| `favicon.recon` 🔧 | `Domain`/`Subdomain` → `Technology` | ✓ | ✓ | DB ~500 hash (FavFreak import) |
| `favicon.shodan_dork` 🔧 | `Technology`(favicon) → `Subdomain` | ✓ | ✓ (opt) | API Shodan se key, DDG fallback |
| `analytics.ids` 🔧 | `URL` → `TrackerID` | ✓ | ✓ | — |
| `analytics.reverse` 🔧 | `TrackerID` → `Domain` | ✓ | ✓ | — |
| `security.headers` ✨ | `URL` → headers mancanti | ✓ | ✓ | modulo dedicato |
| `takeover.verifier` ✨ | `DNSRecord`(CNAME) → `TakeoverFinding` | 🔥 | ✓ | **fix §2.2**: fetch + match fingerprint |
| `cors.misconfig` ✨ | `URL` → `Finding` | 🔥 | ✓ | — |
| `tls.deep` ✨ | `Subdomain:443` → `Finding` | 🔥 | ✓ | versioni, cipher, chain via `ssl` stdlib |

### 8.3 Historical & secrets

| Module | consumes → produces | passive | keyless | fix/notes |
|---|---|---|---|---|
| `wayback.wayback_machine` 🔧 | `Domain` → `URL` | ✓ | ✓ | — |
| `wayback.commoncrawl` 🔧 | `Domain` → `URL` | ✓ | ✓ | — |
| `wayback.otx` 🔧 | `Domain` → `URL` | ✓ | 🔑 opt | — |
| `wayback.urlscan` 🔧 | `Domain` → `URL` | ✓ | ✓ | — |
| `js.secrets` 🔧 | `URL` → `Secret`, `URL`, `Email` | ✓ | ✓ | **fix §2.10**: entropy + deny-list + strict netloc endswith |
| `secrets.github_dork` ✨ | `Domain` → `Secret`, `URL` | ✓ | ✓ opt | — |
| `secrets.gitlab_dork` ✨ | `Domain` → `Secret`, `URL` | ✓ | ✓ | — |
| `secrets.pastebin_dork` ✨ | `Domain` → `Secret`, `URL` | ✓ | ✓ | — |

### 8.4 Email harvesting (15 moduli, uno per fonte)

| Module | consumes → produces | passive | keyless | fix/notes |
|---|---|---|---|---|
| `email.bing_scrape` 🔧 | `Domain` → `Email` | ✓ | ✓ | — |
| `email.ddg_scrape` 🔧 | `Domain` → `Email` | ✓ | ✓ | — |
| `email.crtsh_san` ✨ | `Domain` → `Email` | ✓ | ✓ | SAN cert |
| `email.google_dork` ✨ | `Domain` → `Email` | ✓ | ✓ | query mirate SpiderFoot-style |
| `email.wayback_scrape` ✨ | `URL`(wayback) → `Email` | ✓ | ✓ | zero traffico extra |
| `email.pastebin_dork` ✨ | `Domain` → `Email` | ✓ | ✓ | — |
| `email.theharvester_asian` ✨ | `Domain` → `Email` | ✓ | ✓ | Baidu/Yahoo/Yandex |
| `email.gitlab_search` ✨ | `Domain` → `Email` | ✓ | ✓ | — |
| `email.github_search` 🔧 | `Domain` → `Email` | ✓ | ✓ opt | **fix §2.5** token boost rate limit |
| `email.hunter` 🔧 | `Domain` → `Email`, naming_pattern | ✓ | 🔑 | — |
| `email.phonebook` 🔧 | `Domain` → `Email` | ✓ | ✓ | **fix §2.14** log silent fail |
| `email.linkedin_bing` ✨ | `Domain` → `FullName`, `Email` | ✓ | ✓ | scrape dipendenti |
| `email.smtp_bruteforce` ✨ | `Domain`+pattern → `Email` | 🔥 | ✓ | opt-in `--aggressive-email` |
| `email.pattern_deducer` 🔧 | `Email` → naming_pattern | ✓ | ✓ | synth |
| `email.emailrep_validator` ✨ | `Email` → confidence | ✓ | ✓ | validation, non discovery |

### 8.5 Cloud / breach / exposure

| Module | consumes → produces | passive | keyless | fix/notes |
|---|---|---|---|---|
| `bucket.grayhat` 🔧 | `Domain` → `Bucket` | ✓ | 🔑 | — |
| `bucket.bruteforce` 🔧 | `Domain` → `Bucket` | 🔥 | ✓ | **fix §2.12** parallelizzato + rate-limit |
| `breach.hibp_scrape` ✨ | `Email` → `Breach` | ✓ | ✓ | — |
| `breach.dehashed_scrape` ✨ | `Email` → `Breach` | ✓ | ✓ | — |
| `breach.gravatar` ✨ | `Email` → `URL`+meta | ✓ | ✓ | — |

### 8.6 Deep intel

| Module | consumes → produces | passive | keyless | fix/notes |
|---|---|---|---|---|
| `urldna.scan` 🔧 | `Domain` → `Technology`, `Finding` | ✓ | 🔑 | **fix §2.11** polling |
| `photon.wrapper` 🔧 | `Domain` → `URL`, `Secret`, `Email` | 🔥 | ✓ (binario) | **fix §2.13** `sys.executable`, timeout 300s |

### 8.7 Vuln surface

| Module | consumes → produces | passive | keyless | fix/notes |
|---|---|---|---|---|
| `vuln.internetdb` 🔧 | `IPAddress` → `Port`, `CVE`, `Technology` | ✓ | ✓ | — |
| `vuln.port_scan` 🔧 | `IPAddress` → `Port` | 🔥 | ✓ | **fix §2.4** top-1000 + parallel |
| `vuln.cve_enricher` ✨ | `CVE` → metadata NVD | ✓ | ✓ | **fix §2.3** CVE shown in report |

---

## 9. User Mode Module Catalog

~32 moduli, ~100% keyless. Legenda: 🎯 = FP killer.

### 9.1 Derivation (input → altri input, risolve "lavoro preliminare")

| Module | consumes → produces | notes |
|---|---|---|
| `user.derive.email_to_username` | `Email` → `Username` candidates (conf 0.3) | ~15 varianti |
| `user.derive.fullname_to_username` | `FullName` → `Username` candidates (conf 0.3) | — |
| `user.derive.phone_normalize` | `Phone` → `Phone`(E.164) | `phonenumbers` |
| `user.derive.email_to_name` | `Email` → `FullName` candidate | parse local-part |

### 9.2 Email-based

| Module | consumes → produces | passive | keyless |
|---|---|---|---|
| `user.email.hibp_scrape` | `Email` → `Breach` | ✓ | ✓ |
| `user.email.dehashed_scrape` | `Email` → `Breach` | ✓ | ✓ |
| `user.email.gravatar` | `Email` → `URL`+meta | ✓ | ✓ |
| `user.email.holehe` | `Email` → `Service` | ✓ | ✓ |
| `user.email.github_commit_search` | `Email` → `Username`, `Service` | ✓ | ✓ opt |
| `user.email.google_dork` | `Email` → `URL`, `Document`, `Service` | ✓ | ✓ |
| `user.email.emailrep_validator` | `Email` → confidence | ✓ | ✓ |
| `user.email.smtp_verify` | `Email` → confidence | 🔥 | ✓ |

### 9.3 Username-based (incl. FP killer)

| Module | consumes → produces | passive | keyless | notes |
|---|---|---|---|---|
| `user.username.whatsmyname` 🎯 | `Username` → `Service` | ✓ | ✓ | **core FP killer**: WhatsMyName DB |
| `user.username.service_validator` 🎯 | `Service` → confidence | ✓ | ✓ | 2° layer: content check + metadata |
| `user.username.cross_site_attribution` 🎯 | `Service` batch → confidence | ✓ | ✓ | 3° layer: cluster avatar/bio |
| `user.username.github_profile` | `Username` → `Email`, `Website`, `FullName`, `Organization` | ✓ | ✓ opt |
| `user.username.gitlab_profile` | `Username` → `Email`, `Website` | ✓ | ✓ |
| `user.username.social_scrape` | `Service`(twitter/x) → `URL`, `Email` | ✓ | ✓ | via nitter |

### 9.4 FullName-based (profiling layer)

| Module | consumes → produces | passive | keyless | notes |
|---|---|---|---|---|
| `user.fullname.google_dork` | `FullName` → `URL`, `Service` | ✓ | ✓ | — |
| `user.fullname.bing_dork` | `FullName` → `URL`, `Service` | ✓ | ✓ | — |
| `user.fullname.linkedin_bing` | `FullName` → `Service`(LinkedIn), `Organization` | ✓ | ✓ | bypassa auth wall |
| `user.fullname.cv_hunter` | `FullName` → `Document` | ✓ | ✓ | dork filetype:pdf/doc |
| `user.fullname.personal_site` | `FullName` → `Website`, `Domain` | ✓ | ✓ | TLD personal-looking |
| `user.fullname.reverse_whois` | `FullName`/`Email` → `Domain` | ✓ | ✓ | viewdns.info scrape |
| `user.fullname.crtsh_san` | `FullName` → `Domain` | ✓ | ✓ | — |

### 9.5 Phone-based

| Module | consumes → produces | passive | keyless | notes |
|---|---|---|---|---|
| `user.phone.libphonenumbers` | `Phone` → metadata | ✓ | ✓ | offline |
| `user.phone.google_dork` | `Phone` → `URL`, `FullName` | ✓ | ✓ | — |
| `user.phone.social_probe` | `Phone` → `Service`(Telegram/WhatsApp) | 🔥 | ✓ | opt-in `--aggressive-phone` |
| `user.phone.truecaller_scrape` | `Phone` → `FullName` | ✓ | ✓ | best-effort |

### 9.6 Document-based

| Module | consumes → produces | passive | keyless |
|---|---|---|---|
| `user.document.pdf_metadata` | `Document`(PDF) → `Email`, `FullName`, software | ✓ | ✓ |
| `user.document.text_mine` | `Document` → `Email`, `Phone`, `URL` | ✓ | ✓ |

### 9.7 Service-based (pivot da account)

| Module | consumes → produces | passive | keyless |
|---|---|---|---|
| `user.service.profile_scraper` | `Service` → `Email`, `Website`, `FullName`, `Organization` | ✓ | ✓ |
| `user.service.avatar_hasher` | `Service` → avatar hash in metadata | ✓ | ✓ |

### 9.8 FP killer in dettaglio (meccanismi)

1. **WhatsMyName DB**: JSON open-source con per-site rules (URL pattern, "exists" markers, "not exists" markers). Scaricato una tantum, aggiornabile con `tddt update-wmn-db`.
2. **Content validation** (`service_validator`): dopo HTTP 200 fa fetch profilo, verifica username in HTML, estrae metadata (avatar/bio/followers/join_date), downgrade a 0.1 se metadata mancano.
3. **Cross-site attribution clustering**: avatar hash + bio hash → cluster di `Service` → stessa persona (boost +0.3) o username collision (-0.2).

### 9.9 Cross-mode (opt-in)

Flag `--follow-domains`: se user mode trova `Domain` o `Website` → scan corporate sul dominio nello stesso report, in sezione separata `cross_mode_results`. **Off di default** (richiesta esplicita).

### 9.10 Caps specifici user mode

- `max_services_per_username: 150`
- `max_username_candidates: 20`
- `confidence_floor_for_profile: 0.6` (soglia per entrata nel Profile aggregato)

---

## 10. CLI, Report, Testing, Project Structure

### 10.1 CLI

Entry point `tddt` installabile via `pyproject.toml`.

```
tddt corp <domain> [flags]
tddt user [--email X] [--username X] [--name "X X"] [--phone X] [flags]
tddt update-wmn-db
tddt clear-cache
tddt list-modules [--mode corp|user] [--keyless-only]
```

Flag comuni:
- `-o/--output <file>` (default `report-{target}-{timestamp}.json`)
- `-f/--format <fmt>` (`rich,json` default; combinabili con `markdown`, `html`)
- `-l/--light`
- `--only-keyless`
- `-t/--threads N` (default 20)
- `-v/-vv`
- `--proxy <url>`
- `--insecure`
- `--no-cache` / `--clear-cache`
- `--max-iterations N` (default 5)
- `--max-runtime S` (default 600)
- `--only-module <name>` / `--skip-module <name>`

Specifici `corp`: `--aggressive-email`, `--photon-path`.
Specifici `user`: `--aggressive-phone`, `--follow-domains`. Almeno uno tra `--email/--username/--name/--phone` è richiesto.

### 10.2 Report formats

- **`rich`**: console live via `rich.live.Live`, tabelle finali per entity type.
- **`json`**: schema stabile:
```json
{
  "scan": {
    "mode": "corporate", "seed": {...},
    "started_at": "...", "finished_at": "...", "duration_s": 55.3,
    "iterations_completed": 3,
    "modules_executed": [...], "modules_skipped": [...]
  },
  "entities": {
    "by_type": {"Domain": [...], "Email": [...], ...},
    "graph_edges": [{"parent_id": "...", "child_id": "...", "module": "..."}]
  },
  "profile": {...}
}
```
- **`markdown`**: human-readable, sezioni per gruppo, anchor-link.
- **`html`**: self-contained via `console.export_html()`.

### 10.3 ProfileAggregator (user mode)

Layer `report/`, NOT un modulo. Dopo scan:
1. Raggruppa `Service` per cluster da `cross_site_attribution`.
2. Cluster più grande = primary, altri in `profile.alternates`.
3. Aggrega al primary: `Email`, `Website`, `Document`, `Breach`, `FullName`, `Organization`, `Phone` collegati via graph edge.
4. Risolve conflitti `FullName`: highest confidence; tie → tutti con flag `conflicting`.

Output in `report.profile`:
```json
{
  "primary": {
    "names": [...], "emails": [...], "websites": [...],
    "organizations": [...], "services": [...], "documents": [...], "phones": [...]
  },
  "alternates": [...]
}
```

### 10.4 Testing

- `pytest` + `pytest-vcr` (cassette HTTP recorded).
- Per-module unit tests con cassette per 1 target reale + 1 target vuoto.
- Core: 90%+ coverage. Modules: 70%+.
- Engine: integration con 3-4 fake module.
- CI GitHub Actions: Python 3.11/3.12 su Ubuntu, lint (ruff) + mypy strict su `core/` + test.
- Zero test attivi in CI (socket/SMTP skippati con marker `@pytest.mark.active`).

### 10.5 Project structure

```
TDDT/
├── pyproject.toml
├── README.md (rewritten)
├── .env.example
├── tddt/
│   ├── __init__.py
│   ├── __main__.py              # python -m tddt
│   ├── cli.py
│   ├── core/
│   │   ├── entity.py
│   │   ├── module.py
│   │   ├── engine.py
│   │   ├── http.py
│   │   ├── cache.py
│   │   ├── rate_limit.py
│   │   ├── config.py
│   │   └── logger.py
│   ├── modules/
│   │   ├── __init__.py
│   │   ├── corporate/
│   │   │   ├── subdomain/       # 5 file
│   │   │   ├── dns/             # 3 file
│   │   │   ├── netblock/        # 2 file
│   │   │   ├── web/             # 7 file
│   │   │   ├── analytics/       # 2 file
│   │   │   ├── wayback/         # 4 file
│   │   │   ├── secrets/         # 4 file
│   │   │   ├── email/           # 15 file
│   │   │   ├── bucket/          # 2 file
│   │   │   ├── breach/          # 3 file
│   │   │   ├── vuln/            # 3 file
│   │   │   └── external/        # 2 file (urldna, photon)
│   │   └── user/
│   │       ├── derive/          # 4 file
│   │       ├── email/           # 8 file
│   │       ├── username/        # 6 file
│   │       ├── fullname/        # 7 file
│   │       ├── phone/           # 4 file
│   │       ├── service/         # 2 file
│   │       └── document/        # 2 file
│   ├── report/
│   │   ├── json_exporter.py
│   │   ├── markdown_exporter.py
│   │   ├── html_exporter.py
│   │   └── profile_aggregator.py
│   └── data/
│       └── wmn.json             # scaricato on-demand
├── tests/
│   ├── unit/
│   ├── integration/
│   └── cassettes/
├── docs/
│   └── superpowers/specs/
│       └── 2026-10-18-tddt-rewrite-design.md
└── .github/workflows/ci.yml
```

### 10.6 Migration plan (graduale, non big-bang)

1. Setup core + engine + CLI nuovi in parallelo al vecchio `main.py` (zero rotture).
2. Migrazione 1 modulo alla volta, iniziando dai semplici (whois, dns.deep).
3. `python main.py <domain>` resta funzionante, con deprecation warning quando tutti i moduli sono stati portati.
4. Dopo migrazione completa, `main.py` → stub che redirige a `tddt corp`.
5. Un singolo commit finale rimuove il legacy entry point e la vecchia `modules/`.

---

## 11. Acceptance Criteria

La riscrittura è considerata completa quando:

- **AC1** — `tddt corp example.com --light` esegue zero chiamate `active=True` (verificabile con `--vv` log + socket mock in test).
- **AC2** — `tddt corp example.com` senza alcuna API key configurata produce un report JSON non vuoto con `Subdomain`, `Email`, `DNSRecord`, `Technology`, `Secret` entity.
- **AC3** — Un modulo `takeover.verifier` segnala un takeover solo se fetch del CNAME ritorna una fingerprint nota di errore (test con cassette: CNAME verso GitHub Pages esistente → no finding; CNAME verso GitHub Pages non reclamato → finding).
- **AC4** — Il report JSON mostra tutti i `CVE` scoperti via `vuln.internetdb` nella sezione dedicata (test: target con CVE noti → entity count > 0).
- **AC5** — `tddt user --name "Mario Rossi"` deriva ≥10 `Username` candidate e lancia `whatsmyname` solo sui candidati sopra `min_confidence` (dopo validazione).
- **AC6** — `tddt user --email X` con un email di test noto trova almeno 1 `Breach`, 1 `Service` validato, 1 `Username` reale.
- **AC7** — Il motore converge: 5 iterazioni max, nessun loop infinito su input ricorsivi (test con fake module cycle).
- **AC8** — Aggiungere un nuovo modulo richiede un solo file nuovo in `tddt/modules/corporate/.../file.py` con il decoratore `@register_module`. Zero modifiche a `cli.py`, `engine.py`, `core/`.
- **AC9** — Il repo ha coverage pytest ≥70% globale, ≥90% su `tddt/core/`.
- **AC10** — Il CLI legacy (`python main.py example.com`) continua a funzionare durante tutta la fase di migrazione.
- **AC11** — Zero occorrenze di `except Exception: pass` nel repo (enforced via ruff rule custom o grep in CI).
- **AC12** — Il report JSON **non** contiene mai il valore completo di una `Secret` entity (solo preview + hash). Verificabile via test unit sul `JsonExporter`.

---

## 12. Open Items (da decidere nel plan di implementazione)

- **Ordine di implementazione** dei moduli: proposta → Core prima, poi corporate base (whois, dns, subdomain, http, tech), poi email cluster, poi deep OSINT, poi user mode.
- **WhatsMyName DB versioning**: come gestire breaking changes nel formato JSON upstream.
- **Linter custom** per impedire `except Exception: pass`: ruff plugin o grep-based check in CI.
- **Formato della cassette VCR**: filtrare chiavi API dagli header registrati (sicurezza).
- **Bootstrap dei Username candidate**: `user.derive.email_to_username` e `fullname_to_username` producono candidati a `confidence=0.3`, sotto `downstream_threshold=0.5` → `whatsmyname` non li vede. Opzioni:
  - A) `derive` produce a 0.5 → `whatsmyname` gira su tutti (esplosione: 15 candidati × 600 siti = 9000 req).
  - B) Introdurre `user.username.quick_validator`: modulo con `min_confidence=0.3` che testa i candidati su ~5 siti ad alta affidabilità (GitHub, Reddit, Keybase); se survive → promuove a 0.6, se no → degrada a 0.1. Solo i promossi scatenano `whatsmyname` full. **Raccomandato**.
  - C) Nessun derive automatico: user deve passare `--username` esplicito.
  - Scelta attesa: **B**. Da confermare in plan.

Questi non bloccano l'approvazione dello spec; verranno affrontati nel plan di implementazione (writing-plans).

---

**Fine del design doc.**
