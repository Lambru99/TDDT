# TDDT (Total Domain Discovery Tool) v2

A high-performance, modular External Attack Surface Management (EASM) and User OSINT framework in Python.

TDDT correlates intelligence through an automated entity graph, dispatching passive and active reconnaissance modules based on declared entity consumption and production rules.

---

## ⚠️ Legal Disclaimer

Usage of this tool for attacking targets without prior mutual consent is illegal. It is the end user's responsibility to obey all applicable local, state, and international laws. Developers assume no liability for misuse.

- Use `--light` (`-l`) for strictly passive OSINT research (zero active network probes against target systems).
- Active modules (e.g. SMTP mailbox validation, socket port scanning, CORS verification) must only be used on assets you own or have explicit permission to test.

---

## 📦 Installation

TDDT v2 requires Python 3.11+.

### Recommended: Install via pipx
```bash
pipx install .
```

### Or Install via venv
```bash
git clone https://github.com/Lambru99/TDDT.git
cd TDDT
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

---

## 🚀 Quick Start & CLI Subcommands

TDDT v2 provides dedicated subcommands for corporate surface mapping and user identity profiling.

### 1. Corporate Mode (`tddt corp`)
Discovers subdomains, DNS infrastructure, cloud buckets, exposed secrets, web technologies, and security findings.

```bash
# Passive-only corporate scan (safe, no direct active probes)
tddt corp example.com --light

# Full scan with active port scanning and takeover verification
tddt corp example.com -o report-example.json

# Skip modules that require external API keys
tddt corp example.com --only-keyless
```

### 2. User Mode (`tddt user`)
Cross-references identities across emails, usernames, names, and phone numbers:

```bash
# Profile an individual by email
tddt user --email victim@target.org --light

# Profile by full name and dork for CVs/documents and personal domains
tddt user --name "John Doe"

# Username enumeration across hundreds of sites via WhatsMyName
tddt user --username johndoe

# Phone number validation and enrichment
tddt user --phone "+14155552671"

# Opt-in cross-mode pivot: if personal websites or domains are found, automatically run corporate reconnaissance
tddt user --name "Jane Doe" --follow-domains
```

### 3. Utility Subcommands
```bash
# Update WhatsMyName detection rules database
tddt update-wmn-db

# List all registered corporate and user modules
tddt list-modules

# Clear cached HTTP responses
tddt clear-cache
```

---

## 🛠️ CLI Flags Reference

| Flag | Description |
|------|-------------|
| `-o, --output FILE` | Path to save JSON report (default: `report-<target>-<timestamp>.json`) |
| `-l, --light` | Passive-only mode. Disables active TCP sockets, SMTP brute force, and active probes. |
| `--only-keyless` | Skips any module requiring paid/registered API keys. |
| `-t, --threads N` | Thread pool concurrency (default: 20). |
| `-v, -vv, -vvv` | Verbosity levels (INFO, DEBUG, TRACE). |
| `--proxy URL` | HTTP/SOCKS5 proxy URL (e.g. `http://127.0.0.1:8080` or `socks5://127.0.0.1:9050`). |
| `--insecure` | Disable TLS certificate verification. |
| `--no-cache` | Disable SQLite HTTP response caching. |
| `--max-iterations N`| Maximum correlation loop iterations (default: 5). |
| `--max-runtime S` | Maximum total scan runtime in seconds (default: 600.0). |
| `--follow-domains` | *(User mode only)* Opt-in to trigger corporate scan on discovered domains. |

---

## 🔑 API Keys Configuration

Copy `.env.example` to `.env` to configure optional API keys:

```bash
cp .env.example .env
```

Supported environment variables:
- `GITHUB_TOKEN`: GitHub API token for commit scraping and secret mining
- `HIBP_API_KEY`: Have I Been Pwned breach checks
- `DEHASHED_API_KEY`: DeHashed breach search
- `TRUECALLER_API_KEY`: Truecaller phone owner lookup
- `HUNTER_API_KEY`: Hunter.io email harvesting
- `OTX_API_KEY`: AlienVault OTX passive DNS
- `URLSCAN_API_KEY`: URLScan.io submissions
- `URLDNA_API_KEY`: urlDNA intelligence
- `GRAYHAT_API_KEY`: GrayhatWarfare cloud bucket search

---

## 🧩 Adding New Modules

TDDT v2 features an autodiscovery module registry. Creating a new module is simple:

```python
from collections.abc import Iterable
from tddt.core.entity import BaseEntity, Domain, Subdomain
from tddt.core.module import BaseModule, register_module

@register_module(
    name="corporate.subdomain.custom_source",
    mode=["corporate"],
    consumes=[Domain],
    produces=[Subdomain],
    active=False,
    requires_key=None,
)
class CustomSubdomainModule(BaseModule):
    def run(self, entities: Iterable[BaseEntity]) -> Iterable[BaseEntity]:
        for entity in entities:
            if not isinstance(entity, Domain):
                continue
            # Your OSINT logic here
            yield Subdomain(
                value=f"admin.{entity.value}",
                parent_id=entity.id,
                source_module=self.name,
                confidence=0.8,
            )
```

Save your file under `tddt/modules/corporate/` or `tddt/modules/user/` and TDDT discovers and runs it automatically.

---

## 🔄 Migration from v1

TDDT v2 is an architectural rewrite introducing a typed Entity Graph (`EntityGraph`), correlation engine, structured reporting, and dedicated subcommands (`corp` and `user`). Legacy calls using `python main.py <domain> [flags]` remain supported via a backwards-compatibility shim that prints a deprecation warning and automatically translates legacy flags into `tddt corp <domain>`. All custom scripts should migrate to the `tddt` CLI.
