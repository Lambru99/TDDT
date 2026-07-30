import requests
from modules.config import require_api_key, get_api_key

JUICY_EXTENSIONS = [
    '.bak', '.old', '.backup', '.sql', '.zip', '.rar',
    '.env', '.config', '.xml', '.json', '.git', '.sh',
    '.yaml', '.yml', '.pem', '.key', '.p12', '.pfx',
    '.log', '.dump', '.tar', '.gz', '.7z', '.passwd',
]


def _is_juicy(url: str) -> bool:
    low = url.lower()
    return any(low.endswith(ext) for ext in JUICY_EXTENSIONS)


class WaybackRecon:
    def __init__(self, domain):
        self.domain = domain
        self.cdx_api = "http://web.archive.org/cdx/search/cdx"
        self.headers = {'User-Agent': 'Mozilla/5.0 (OSINT-Tool/1.0)'}

    # ── SOURCE 1: Web Archive (Wayback Machine) ───────────────────────────
    def _fetch_wayback(self) -> list:
        params = {
            'url': f"*.{self.domain}/*",
            'collapse': 'urlkey',
            'output': 'json',
            'fl': 'original',
            'filter': 'statuscode:200',
            'limit': 3000
        }
        found = []
        try:
            response = requests.get(self.cdx_api, params=params, timeout=20)
            if response.status_code == 200:
                data = response.json()
                for row in data[1:]:
                    url = row[0]
                    if _is_juicy(url):
                        found.append(url)
        except Exception:
            pass
        return found

    # ── SOURCE 2: CommonCrawl CDX API ─────────────────────────────────────
    def _fetch_commoncrawl(self) -> list:
        found = []
        try:
            # Recupera l'indice più recente
            info_resp = requests.get(
                "https://index.commoncrawl.org/collinfo.json",
                timeout=15
            )
            if info_resp.status_code != 200:
                return found
            indexes = info_resp.json()
            if not indexes:
                return found

            # Usa l'indice più recente
            latest_api = indexes[0].get('cdx-api')
            if not latest_api:
                return found

            params = {
                'url': f"*.{self.domain}/*",
                'output': 'json',
                'fl': 'url',
                'filter': 'status:200',
                'limit': 1000,
                'collapse': 'urlkey'
            }
            resp = requests.get(latest_api, params=params, timeout=25)
            if resp.status_code == 200:
                for line in resp.text.strip().splitlines():
                    try:
                        import json as _json
                        obj = _json.loads(line)
                        url = obj.get('url', '')
                        if url and _is_juicy(url):
                            found.append(url)
                    except Exception:
                        pass
        except Exception:
            pass
        return found

    # ── SOURCE 3: AlienVault OTX ──────────────────────────────────────────
    def _fetch_otx(self) -> list:
        api_key = require_api_key('OTX_API_KEY', 'Wayback/OTX')
        if not api_key:
            return []

        found = []
        try:
            url = f"https://otx.alienvault.com/api/v1/indicators/domain/{self.domain}/url_list"
            headers = {**self.headers, 'X-OTX-API-KEY': api_key}
            page = 1
            while True:
                resp = requests.get(
                    url, headers=headers, params={'limit': 500, 'page': page}, timeout=20
                )
                if resp.status_code != 200:
                    break
                data = resp.json()
                url_list = data.get('url_list', [])
                if not url_list:
                    break
                for entry in url_list:
                    u = entry.get('url', '')
                    if u and _is_juicy(u):
                        found.append(u)
                if not data.get('has_next'):
                    break
                page += 1
                if page > 5:  # max 2500 URL da OTX
                    break
        except Exception:
            pass
        return found

    # ── SOURCE 4: URLScan.io (search gratuita senza key) ─────────────────
    def _fetch_urlscan(self) -> list:
        found = []
        try:
            headers = {**self.headers, 'Content-Type': 'application/json'}
            # La key non è obbligatoria per la search
            api_key = get_api_key('URLSCAN_API_KEY')
            if api_key:
                headers['API-Key'] = api_key

            params = {
                'q': f'domain:{self.domain}',
                'size': 100,
                'fields': 'page.url'
            }
            resp = requests.get(
                'https://urlscan.io/api/v1/search/',
                headers=headers, params=params, timeout=20
            )
            if resp.status_code == 200:
                data = resp.json()
                for result in data.get('results', []):
                    u = result.get('page', {}).get('url', '')
                    if u and _is_juicy(u):
                        found.append(u)
        except Exception:
            pass
        return found

    # ── PUBLIC METHOD ─────────────────────────────────────────────────────
    def find_secrets(self) -> dict:
        """
        Aggrega URL sensibili da tutte le fonti disponibili.
        Restituisce un dict con i risultati divisi per fonte e la lista deduplicata.
        """
        results_by_source = {}

        wb = self._fetch_wayback()
        if wb:
            results_by_source['wayback'] = wb

        cc = self._fetch_commoncrawl()
        if cc:
            results_by_source['commoncrawl'] = cc

        otx = self._fetch_otx()
        if otx:
            results_by_source['otx'] = otx

        us = self._fetch_urlscan()
        if us:
            results_by_source['urlscan'] = us

        # Deduplicazione globale
        all_urls = []
        for urls in results_by_source.values():
            all_urls.extend(urls)
        unique_urls = list(set(all_urls))

        return {
            'by_source': results_by_source,
            'all': unique_urls,
            'total': len(unique_urls)
        }