import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from bs4 import BeautifulSoup 

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

class HttpInspector:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; CorporateRecon/1.0)'
        }

    def inspect(self, domain):
        protocols = ['https', 'http']
        
        for proto in protocols:
            url = f"{proto}://{domain}"
            try:
                response = requests.get(
                    url, 
                    headers=self.headers, 
                    timeout=5, 
                    verify=False,
                    allow_redirects=True
                )
                
                soup = BeautifulSoup(response.text, 'html.parser')
                title = soup.title.string.strip() if soup.title else "N/A"
                if len(title) > 50: title = title[:47] + "..."

                server = response.headers.get('Server', 'N/A')

                return {
                    "alive": True,
                    "url": response.url,
                    "status_code": response.status_code,
                    "title": title,
                    "server": server
                }

            except Exception:
                continue

        return {
            "alive": False,
            "url": f"http://{domain}",
            "status_code": 0,
            "title": "Unreachable",
            "server": "N/A"
        }