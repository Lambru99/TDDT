import requests
import re
import time
import random
from collections import Counter
from urllib.parse import quote_plus
from rich.console import Console
from modules.config import require_api_key

console = Console()

# Regex per catturare indirizzi email
EMAIL_REGEX = r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}'

GENERIC_KEYWORDS = [
    'info', 'admin', 'contact', 'support', 'sales', 'hr', 'job',
    'recruit', 'office', 'privacy', 'press', 'legal', 'noreply',
    'no-reply', 'newsletter', 'marketing', 'billing', 'abuse',
    'security', 'webmaster', 'postmaster', 'help', 'team'
]

JUNK_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.gif', '.css', '.js', '.svg', '.ico', '.woff')


class EmailHarvester:
    def __init__(self, domain):
        self.domain = domain
        self.found_emails: set = set()
        self.bing_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36 Edge/115.0.1901.188',
            'Referer': 'https://www.google.com/'
        }
        self.generic_headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

    def _extract_emails(self, text):
        """Estrae email dal testo e le aggiunge al set, filtrando junk."""
        matches = re.findall(EMAIL_REGEX, text)
        for email in matches:
            email = email.lower().strip()
            if (email.endswith(f"@{self.domain}")
                    and not any(email.endswith(ext) for ext in JUNK_EXTENSIONS)):
                self.found_emails.add(email)

    # ── SOURCE 1: Bing ────────────────────────────────────────────────────
    def _search_bing(self):
        """Bing: 4 varianti di query per massimizzare il coverage di dominio e persone."""
        queries = [
            f'"@{self.domain}"',
            f'"{self.domain}" email OR contact OR mail',
            f'site:{self.domain} email OR mail',
            f'"{self.domain}" info OR admin OR support OR sales'
        ]
        for query in queries:
            base_url = f"https://www.bing.com/search?q={quote_plus(query)}&first={{}}"
            for page in range(0, 30, 10):
                try:
                    url = base_url.format(page)
                    response = requests.get(url, headers=self.bing_headers, timeout=10)
                    if response.status_code == 200:
                        self._extract_emails(response.text)
                    time.sleep(random.uniform(0.8, 1.8))
                except Exception:
                    continue

    # ── SOURCE 2: DuckDuckGo ──────────────────────────────────────────────
    def _search_duckduckgo(self):
        """DuckDuckGo HTML endpoint."""
        queries = [
            f'"@{self.domain}"',
            f'"{self.domain}" email OR mail OR contact',
            f'"{self.domain}" info OR admin OR helpdesk'
        ]
        url = "https://html.duckduckgo.com/html/"
        for query in queries:
            try:
                response = requests.post(
                    url, data={'q': query}, headers=self.generic_headers, timeout=10
                )
                if response.status_code == 200:
                    self._extract_emails(response.text)
                elif response.status_code == 403:
                    console.print("[dim]   [!] DuckDuckGo rate limit (403). Skipping.[/dim]")
                time.sleep(random.uniform(1.0, 2.0))
            except Exception:
                pass

    # ── SOURCE 3: GitHub Public Code Search ───────────────────────────────
    def _search_github(self):
        """Cerca email nel codice pubblico su GitHub."""
        try:
            url = "https://api.github.com/search/code"
            params = {'q': f'"{self.domain}" in:file', 'per_page': 30}
            headers = {
                **self.generic_headers,
                'Accept': 'application/vnd.github.v3+json'
            }
            resp = requests.get(url, params=params, headers=headers, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get('items', []):
                    # Scarica il file raw e cerca email
                    raw_url = item.get('html_url', '').replace(
                        'github.com', 'raw.githubusercontent.com'
                    ).replace('/blob/', '/')
                    try:
                        raw_resp = requests.get(raw_url, headers=self.generic_headers, timeout=8)
                        if raw_resp.status_code == 200:
                            self._extract_emails(raw_resp.text)
                    except Exception:
                        pass
                    time.sleep(0.5)
            elif resp.status_code == 422:
                pass  # query non valida, salta
        except Exception:
            pass

    # ── SOURCE 4: Hunter.io ───────────────────────────────────────────────
    def _search_hunter(self) -> dict | None:
        """
        Hunter.io: restituisce email + naming convention ufficiale.
        Richiede HUNTER_API_KEY. Se assente → skip.
        """
        api_key = require_api_key('HUNTER_API_KEY', 'Email/Hunter.io')
        if not api_key:
            return None

        try:
            url = "https://api.hunter.io/v2/domain-search"
            params = {
                'domain': self.domain,
                'api_key': api_key,
                'limit': 100
            }
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code == 200:
                data = resp.json().get('data', {})
                emails_list = data.get('emails', [])
                for entry in emails_list:
                    email = entry.get('value', '')
                    if email:
                        self.found_emails.add(email.lower())
                # Hunter fornisce direttamente il pattern
                pattern = data.get('pattern', None)
                return {'hunter_pattern': pattern, 'hunter_count': len(emails_list)}
        except Exception:
            pass
        return None

    # ── SOURCE 5: Phonebook.cz ────────────────────────────────────────────
    def _search_phonebook(self):
        """Phonebook.cz: database di email harvesting, no API key."""
        try:
            url = "https://phonebook.cz/?"
            params = {'search': self.domain, 'type': 2}  # type=2 → email
            headers = {
                **self.generic_headers,
                'Referer': 'https://phonebook.cz/'
            }
            resp = requests.get(url, params=params, headers=headers, timeout=15)
            if resp.status_code == 200:
                self._extract_emails(resp.text)
        except Exception:
            pass

    # ── NAMING CONVENTION ANALYSIS ────────────────────────────────────────
    def _deduce_pattern(self, hunter_pattern: str | None = None) -> str:
        """Analizza il pattern di naming convention delle email trovate."""
        # Se Hunter.io ha già fornito il pattern, usalo come ground truth
        if hunter_pattern:
            return hunter_pattern

        if not self.found_emails:
            return "Unknown"

        pattern_votes = []
        for email in self.found_emails:
            local = email.split('@')[0]
            if any(k in local for k in GENERIC_KEYWORDS):
                continue
            if '.' in local:
                parts = local.split('.')
                if len(parts) == 2:
                    if len(parts[0]) == 1:
                        pattern_votes.append("{initial}.{surname}")   # m.rossi
                    elif len(parts[1]) == 1:
                        pattern_votes.append("{name}.{initial}")      # mario.r
                    else:
                        pattern_votes.append("{name}.{surname}")       # mario.rossi
            elif '_' in local:
                pattern_votes.append("{name}_{surname}")               # mario_rossi
            elif len(local) > 3:
                pattern_votes.append("{surname}{initial} or {name}")  # rossim / mario

        if not pattern_votes:
            return "Custom/Mixed"
        return Counter(pattern_votes).most_common(1)[0][0]

    # ── PUBLIC METHOD ─────────────────────────────────────────────────────
    def harvest(self) -> dict:
        try:
            console.log("[dim]   Querying Bing...[/dim]")
            self._search_bing()

            console.log("[dim]   Querying DuckDuckGo...[/dim]")
            self._search_duckduckgo()

            console.log("[dim]   Querying GitHub public code...[/dim]")
            self._search_github()

            console.log("[dim]   Querying Phonebook.cz...[/dim]")
            self._search_phonebook()

            console.log("[dim]   Querying Hunter.io...[/dim]")
            hunter_data = self._search_hunter()
            hunter_pattern = hunter_data.get('hunter_pattern') if hunter_data else None

            pattern = self._deduce_pattern(hunter_pattern)

            people = []
            generic = []
            for email in self.found_emails:
                local = email.split('@')[0]
                if any(k in local for k in GENERIC_KEYWORDS):
                    generic.append(email)
                else:
                    people.append(email)

            return {
                "total_found": len(self.found_emails),
                "naming_convention": pattern,
                "people": sorted(people),
                "generic": sorted(generic),
                "sources_used": {
                    "bing": True,
                    "duckduckgo": True,
                    "github": True,
                    "phonebook": True,
                    "hunter_io": hunter_data is not None
                }
            }

        except Exception as e:
            return {"error": str(e)}