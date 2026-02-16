import requests

class WaybackRecon:
    def __init__(self, domain):
        self.domain = domain
        self.cdx_api = "http://web.archive.org/cdx/search/cdx"
        self.juicy_extensions = [
            '.bak', '.old', '.backup', '.sql', '.zip', '.rar', 
            '.env', '.config', '.xml', '.json', '.git', '.sh', '.yaml'
        ]

    def find_secrets(self):
        params = {
            'url': f"*.{self.domain}/*",
            'collapse': 'urlkey',
            'output': 'json',
            'fl': 'original',
            'filter': 'statuscode:200',
            'limit': 3000
        }

        found_urls = []
        try:
            response = requests.get(self.cdx_api, params=params, timeout=20)
            if response.status_code == 200:
                data = response.json()
                if not data: return []

                for row in data[1:]:
                    url = row[0]
                    if any(url.lower().endswith(ext) for ext in self.juicy_extensions):
                        found_urls.append(url)
            
            return list(set(found_urls))

        except Exception:
            return []