import requests
import mmh3
import codecs
import time
import random
from bs4 import BeautifulSoup
from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

class FaviconRecon:
    def __init__(self, domain):
        self.domain = domain
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
        }
        self.signatures = {
            116323821: "Spring Boot",
            -1566948357: "Jenkins",
            81586312: "Jenkins (Old)",
            -674393285: "Docker",
            -205568434: "Kubernetes",
            1768625805: "Atlassian Jira",
            -1255745778: "Cobalt Strike Beacon",
            366968058: "Outlook Web Access",
            -446862803: "Plesk",
            -1473489816: "cPanel"
        }

    def _search_ddg(self, query):
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

    def analyze(self):
        candidates = [
            f"https://{self.domain}/favicon.ico",
            f"http://{self.domain}/favicon.ico",
            f"https://www.{self.domain}/favicon.ico"
        ]

        favicon_data = {"found": False}

        for url in candidates:
            try:
                response = requests.get(url, headers=self.headers, timeout=5, verify=False)
                if response.status_code == 200:
                    # Hash MurmurHash3
                    favicon = codecs.encode(response.content, "base64")
                    hash_val = mmh3.hash(favicon)
                    
                    favicon_data = {
                        "found": True,
                        "url": url,
                        "hash": hash_val,
                        "tech": self.signatures.get(hash_val, "Unknown"),
                        "related_hosts": []
                    }

                    dork = f'site:shodan.io "http.favicon.hash:{hash_val}"'
                    found_links = self._search_ddg(dork)
                    
                    ips = []
                    for link in found_links:
                        parts = link.split('/')
                        if len(parts) > 0:
                            ips.append(parts[-1])
                    
                    favicon_data["related_hosts"] = list(set(ips))
                    break 

            except Exception:
                continue
        
        return favicon_data