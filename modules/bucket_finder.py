"""
bucket_finder.py — Cloud Storage Bucket Finder
Cerca bucket S3/Azure/GCP esposti associati al dominio target.
Dual mode:
  1. GrayhatWarfare API (richiede GRAYHAT_API_KEY)
  2. Brute-force naming patterns (no key)
"""
import re
import requests
from modules.config import require_api_key

# Pattern di naming comuni per i bucket
BUCKET_PATTERNS = [
    "{name}",
    "{name}-backup",
    "{name}-backups",
    "{name}-dev",
    "{name}-staging",
    "{name}-prod",
    "{name}-production",
    "{name}-assets",
    "{name}-static",
    "{name}-files",
    "{name}-media",
    "{name}-images",
    "{name}-uploads",
    "{name}-data",
    "{name}-logs",
    "{name}-archive",
    "{name}-dump",
    "{name}-public",
    "{name}-private",
    "{name}-internal",
    "{name}-test",
    "{name}-qa",
    "{name}data",
    "{name}backup",
    "{name}dev",
    "{name}prod",
]

CLOUD_CHECKS = [
    # (provider_name, url_template, success_indicator)
    ("AWS S3",        "https://{bucket}.s3.amazonaws.com/",      "ListBucketResult"),
    ("AWS S3 (Path)", "https://s3.amazonaws.com/{bucket}/",      "ListBucketResult"),
    ("Azure Blob",    "https://{bucket}.blob.core.windows.net/", "EnumerationResults"),
    ("GCP Storage",   "https://storage.googleapis.com/{bucket}/", "ListBucketResult"),
]


class BucketFinder:
    def __init__(self, domain):
        self.domain = domain
        # Estrae il nome base (es. "enel.it" → "enel")
        self.company_name = domain.split('.')[0].lower()
        self.headers = {'User-Agent': 'Mozilla/5.0 (OSINT-Tool/1.0)'}

    # ── SOURCE 1: GrayhatWarfare ───────────────────────────────────────────
    def _fetch_grayhat(self) -> list:
        api_key = require_api_key('GRAYHAT_API_KEY', 'BucketFinder/GrayhatWarfare')
        if not api_key:
            return []

        found = []
        try:
            url = f"https://buckets.grayhatwarfare.com/api/v1/buckets/{self.domain}"
            headers = {**self.headers, 'Authorization': f'Bearer {api_key}'}
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                for bucket in data.get('buckets', []):
                    found.append({
                        "name":     bucket.get('bucket', ''),
                        "provider": bucket.get('cloud', 'Unknown'),
                        "url":      bucket.get('url', ''),
                        "source":   "grayhatwarfare"
                    })
        except Exception:
            pass
        return found

    # ── SOURCE 2: Brute-force naming patterns ──────────────────────────────
    def _bruteforce_buckets(self) -> list:
        found = []
        bucket_names = [p.format(name=self.company_name) for p in BUCKET_PATTERNS]

        for bucket_name in bucket_names:
            for provider, url_tpl, indicator in CLOUD_CHECKS:
                url = url_tpl.format(bucket=bucket_name)
                try:
                    resp = requests.get(url, headers=self.headers, timeout=5)
                    if resp.status_code == 200 and indicator in resp.text:
                        found.append({
                            "name":     bucket_name,
                            "provider": provider,
                            "url":      url,
                            "source":   "bruteforce",
                            "status":   "OPEN (publicly readable)"
                        })
                    elif resp.status_code == 403:
                        # Il bucket esiste ma non è pubblico — comunque interessante
                        found.append({
                            "name":     bucket_name,
                            "provider": provider,
                            "url":      url,
                            "source":   "bruteforce",
                            "status":   "EXISTS (403 - access denied)"
                        })
                except Exception:
                    continue

        return found

    # ── PUBLIC METHOD ──────────────────────────────────────────────────────
    def find(self) -> dict:
        """
        Cerca bucket esposti.
        Ritorna: { 'found': [...], 'total': int, 'open': [...] }
        """
        all_found = []

        gh = self._fetch_grayhat()
        all_found.extend(gh)

        bf = self._bruteforce_buckets()
        # Aggiungi solo quelli non già trovati da GrayhatWarfare
        known_names = {b['name'] for b in all_found}
        for b in bf:
            if b['name'] not in known_names:
                all_found.append(b)

        open_buckets = [b for b in all_found if 'OPEN' in b.get('status', '')]

        return {
            'found': all_found,
            'total': len(all_found),
            'open': open_buckets,
            'open_count': len(open_buckets)
        }
