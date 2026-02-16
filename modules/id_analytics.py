import requests
import re
import time
import random
from bs4 import BeautifulSoup
from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

class AnalyticsRecon:
    def __init__(self, domain):
        self.domain = domain
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        self.patterns = {
            'UA-Code': r'UA-\d{4,10}-\d{1,4}',
            'G-Tag': r'G-[A-Z0-9]{6,12}',
            'AdSense': r'pub-\d{10,20}',
            'GTM': r'GTM-[A-Z0-9]{4,10}'
        }

    def _reverse_search(self, tracking_id):
        """Reverse lookup on DuckDuckGo"""
        url = "https://html.duckduckgo.com/html/"
        query = f'"{tracking_id}" -site:{self.domain}'
        found_domains = set()
        
        try:
            time.sleep(random.uniform(1.5, 3.0))
            resp = requests.post(url, data={'q': query}, headers=self.headers, timeout=10)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                for link in soup.find_all('a', class_='result__a'):
                    href = link.get('href')
                    if href and href.startswith('http'):
                        domain_match = re.search(r'https?://([^/]+)', href)
                        if domain_match:
                            d = domain_match.group(1)
                            if self.domain not in d and 'duckduckgo' not in d:
                                found_domains.add(d)
        except Exception:
            pass
        
        return list(found_domains)

    def search_ids(self):
        target_url = f"https://{self.domain}"
        results = {}
        
        try:
            response = requests.get(target_url, headers=self.headers, timeout=10, verify=False)
            html = response.text

            for name, pattern in self.patterns.items():
                matches = list(set(re.findall(pattern, html)))
                if matches:
                    correlated = []
                    for mid in matches[:1]: 
                        sites = self._reverse_search(mid)
                        if sites:
                            correlated.extend(sites)
                    
                    results[name] = {
                        "ids": matches,
                        "related_domains": list(set(correlated))
                    }
            
            return results

        except Exception as e:
            return {}