"""
js_secrets.py — Photon-like JS crawler
Crawla la homepage e i JS linkati cercando: secret keys, endpoint nascosti,
token JWT, email, credenziali hardcoded.
"""
import requests
import re
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# ── Regex patterns ────────────────────────────────────────────────────────────
SECRET_PATTERNS = {
    # Cloud / Infra
    "AWS Access Key":        r'AKIA[0-9A-Z]{16}',
    "AWS Secret Key":        r'(?i)aws.{0,20}secret.{0,20}["\']([A-Za-z0-9+/]{40})',
    "Google API Key":        r'AIza[0-9A-Za-z\-_]{35}',
    "Google OAuth":          r'[0-9]+-[0-9A-Za-z_]{32}\.apps\.googleusercontent\.com',
    # Tokens
    "JWT Token":             r'eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}',
    "Bearer Token":          r'(?i)bearer\s+[A-Za-z0-9\-._~+/]{20,}',
    # Credentials in code
    "Password in code":      r'(?i)(?:password|passwd|pwd)\s*[:=]\s*["\']([^"\']{6,})["\']',
    "Secret in code":        r'(?i)(?:secret|api_secret|client_secret)\s*[:=]\s*["\']([^"\']{8,})["\']',
    "Token in code":         r'(?i)(?:token|access_token|auth_token)\s*[:=]\s*["\']([^"\']{8,})["\']',
    # Services
    "Stripe Live Key":       r'sk_live_[0-9a-zA-Z]{24}',
    "Stripe Test Key":       r'sk_test_[0-9a-zA-Z]{24}',
    "GitHub Token":          r'ghp_[A-Za-z0-9]{36}',
    "Slack Token":           r'xox[baprs]-[0-9A-Za-z]{10,48}',
    "Twilio Account SID":    r'AC[a-z0-9]{32}',
    "SendGrid API Key":      r'SG\.[A-Za-z0-9\-_]{22}\.[A-Za-z0-9\-_]{43}',
    "Mailgun API Key":       r'key-[0-9a-zA-Z]{32}',
    "Private Key Header":    r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
}

ENDPOINT_PATTERNS = [
    r'["\'](/api/[^"\'?\s]{3,})',
    r'["\'](/v\d+/[^"\'?\s]{3,})',
    r'["\'](/internal/[^"\'?\s]{3,})',
    r'["\'](/admin/[^"\'?\s]{3,})',
    r'["\'](/graphql[^"\'?\s]*)',
    r'["\'](/swagger[^"\'?\s]*)',
    r'["\'](/debug[^"\'?\s]*)',
    r'["\'](/_[^"\'?\s]{3,})',             # underscore prefix = spesso privato
]

EMAIL_REGEX = r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}'


class JsSecrets:
    def __init__(self, domain):
        self.domain = domain
        self.base_urls = [f"https://{domain}", f"http://{domain}"]
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

    def _get_js_urls(self, homepage_url) -> list:
        """Estrae tutti gli URL di file JS dalla homepage."""
        js_urls = []
        try:
            resp = requests.get(homepage_url, headers=self.headers, timeout=8, verify=False)
            if resp.status_code != 200:
                return js_urls
            soup = BeautifulSoup(resp.text, 'html.parser')
            for tag in soup.find_all('script', src=True):
                src = tag['src'].strip()
                if src:
                    absolute = urljoin(resp.url, src)
                    # Solo JS dello stesso dominio o subdomain
                    parsed = urlparse(absolute)
                    if self.domain in parsed.netloc:
                        js_urls.append(absolute)
        except Exception:
            pass
        return js_urls[:20]  # max 20 JS files

    def _scan_content(self, content: str, source_url: str) -> dict:
        """Scansiona il contenuto di un file/pagina e restituisce le trovate."""
        findings = {
            'secrets': {},
            'endpoints': [],
            'emails': [],
            'source': source_url
        }

        # Secrets
        for name, pattern in SECRET_PATTERNS.items():
            matches = re.findall(pattern, content)
            if matches:
                # Deduplicazione e limite
                uniq = list(set(m if isinstance(m, str) else m for m in matches))[:5]
                findings['secrets'][name] = uniq

        # Hidden endpoints
        for pattern in ENDPOINT_PATTERNS:
            matches = re.findall(pattern, content)
            for m in matches:
                if m not in findings['endpoints']:
                    findings['endpoints'].append(m)

        # Email
        emails = re.findall(EMAIL_REGEX, content)
        for e in emails:
            e = e.lower()
            if f"@{self.domain}" in e and e not in findings['emails']:
                findings['emails'].append(e)

        return findings

    def scan(self) -> dict:
        """
        Punto d'ingresso principale.
        Ritorna un dict con:
        - secrets: {pattern_name: [match1, ...]}
        - endpoints: ['/api/v1/users', ...]
        - emails: ['x@domain.com', ...]
        - js_files_scanned: int
        """
        all_secrets = {}
        all_endpoints = set()
        all_emails = set()
        js_scanned = 0

        for base_url in self.base_urls:
            try:
                # Scansiona la homepage stessa
                resp = requests.get(base_url, headers=self.headers, timeout=8, verify=False)
                if resp.status_code == 200:
                    hp_findings = self._scan_content(resp.text, base_url)
                    for k, v in hp_findings['secrets'].items():
                        all_secrets.setdefault(k, []).extend(v)
                    all_endpoints.update(hp_findings['endpoints'])
                    all_emails.update(hp_findings['emails'])

                    # Scansiona i JS linkati
                    js_urls = self._get_js_urls(resp.url)
                    for js_url in js_urls:
                        try:
                            js_resp = requests.get(
                                js_url, headers=self.headers, timeout=8, verify=False
                            )
                            if js_resp.status_code == 200:
                                js_findings = self._scan_content(js_resp.text, js_url)
                                for k, v in js_findings['secrets'].items():
                                    all_secrets.setdefault(k, []).extend(v)
                                all_endpoints.update(js_findings['endpoints'])
                                all_emails.update(js_findings['emails'])
                                js_scanned += 1
                        except Exception:
                            continue
                    break  # se https funziona non prova http
            except Exception:
                continue

        # Deduplicazione finale
        for k in all_secrets:
            all_secrets[k] = list(set(all_secrets[k]))

        return {
            'secrets': all_secrets,
            'endpoints': sorted(list(all_endpoints))[:50],
            'emails': sorted(list(all_emails)),
            'js_files_scanned': js_scanned,
            'found': bool(all_secrets or all_endpoints or all_emails)
        }
