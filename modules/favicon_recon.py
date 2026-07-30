import requests
import mmh3
import codecs
import time
import random
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


class FaviconRecon:
    def __init__(self, domain):
        self.domain = domain
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
        }
        # Hash MurmurHash3 noti → tecnologia associata
        self.signatures = {
            116323821:   "Spring Boot",
            -1566948357: "Jenkins",
            81586312:    "Jenkins (Old)",
            -674393285:  "Docker",
            -205568434:  "Kubernetes",
            1768625805:  "Atlassian Jira",
            -1255745778: "Cobalt Strike Beacon",
            366968058:   "Outlook Web Access",
            -446862803:  "Plesk",
            -1473489816: "cPanel",
            -150253027:  "Grafana",
            708578229:   "GitLab",
            1461153895:  "Fortinet",
            -373567943:  "F5 BIG-IP",
            1062420841:  "Cisco ASA",
        }

    def _find_favicon_url_from_html(self, base_url):
        """
        Scarica la homepage e cerca il favicon nei tag <link>.
        Restituisce l'URL assoluto del favicon o None se non trovato.
        """
        try:
            response = requests.get(
                base_url, headers=self.headers, timeout=8, verify=False,
                allow_redirects=True
            )
            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, 'html.parser')

            # Priorità dei tag da cercare
            rel_values = [
                'icon',
                'shortcut icon',
                'apple-touch-icon',
                'apple-touch-icon-precomposed',
                'mask-icon',
            ]

            for rel in rel_values:
                # BeautifulSoup supporta ricerca parziale su liste di classe
                tag = soup.find('link', rel=lambda r: r and rel in ' '.join(r).lower())
                if tag and tag.get('href'):
                    href = tag['href'].strip()
                    if href:
                        # Risolve URL relativo → assoluto
                        absolute = urljoin(response.url, href)
                        return absolute

            return None

        except Exception:
            return None

    def _search_ddg(self, query):
        """Cerca su DuckDuckGo per trovare host Shodan con lo stesso hash."""
        url = "https://html.duckduckgo.com/html/"
        payload = {'q': query}
        results = []
        try:
            time.sleep(random.uniform(1.5, 3.0))
            resp = requests.post(url, data=payload, headers=self.headers, timeout=10)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                for link in soup.find_all('a', class_='result__a'):
                    href = link.get('href')
                    if href and 'shodan.io/host' in href:
                        results.append(href)
        except Exception:
            pass
        return results

    def _download_and_hash(self, favicon_url):
        """Scarica il favicon e calcola l'hash MurmurHash3."""
        try:
            response = requests.get(
                favicon_url, headers=self.headers, timeout=8, verify=False
            )
            if response.status_code == 200 and len(response.content) > 0:
                favicon_b64 = codecs.encode(response.content, "base64")
                hash_val = mmh3.hash(favicon_b64)
                return hash_val, favicon_url
        except Exception:
            pass
        return None, None

    def analyze(self):
        favicon_data = {"found": False}

        # ── STEP 1: HTML-first parsing ──────────────────────────────────────
        # Prova https, poi http
        for proto in ['https', 'http']:
            base_url = f"{proto}://{self.domain}"
            favicon_url = self._find_favicon_url_from_html(base_url)
            if favicon_url:
                hash_val, used_url = self._download_and_hash(favicon_url)
                if hash_val is not None:
                    favicon_data = {
                        "found": True,
                        "source": "html_tag",
                        "url": used_url,
                        "hash": hash_val,
                        "tech": self.signatures.get(hash_val, "Unknown"),
                        "related_hosts": []
                    }
                    break

        # ── STEP 2: Fallback a /favicon.ico se HTML non ha prodotto nulla ───
        if not favicon_data["found"]:
            fallback_candidates = [
                f"https://{self.domain}/favicon.ico",
                f"http://{self.domain}/favicon.ico",
                f"https://www.{self.domain}/favicon.ico",
            ]
            for url in fallback_candidates:
                hash_val, used_url = self._download_and_hash(url)
                if hash_val is not None:
                    favicon_data = {
                        "found": True,
                        "source": "fallback_root",
                        "url": used_url,
                        "hash": hash_val,
                        "tech": self.signatures.get(hash_val, "Unknown"),
                        "related_hosts": []
                    }
                    break

        # ── STEP 3: Shodan dork via DuckDuckGo (se favicon trovato) ─────────
        if favicon_data["found"]:
            dork = f'site:shodan.io "http.favicon.hash:{favicon_data["hash"]}"'
            found_links = self._search_ddg(dork)
            ips = []
            for link in found_links:
                parts = link.split('/')
                if parts:
                    ips.append(parts[-1])
            favicon_data["related_hosts"] = list(set(ips))

        return favicon_data