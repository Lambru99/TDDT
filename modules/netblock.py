import requests
import json
from rich.console import Console

console = Console()

class NetBlockAnalyzer:
    def __init__(self):
        self.api_url = "http://ip-api.com/batch"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (OSINT-Tool/1.0)'
        }

    def _chunk_list(self, data, size):
        for i in range(0, len(data), size):
            yield data[i:i + size]

    def analyze_ips(self, ip_list):
        clean_ips = list(set([ip for ip in ip_list if ip]))
        
        if not clean_ips:
            return []

        results = []
        
        fields = "status,message,query,countryCode,isp,org,as"

        chunks = list(self._chunk_list(clean_ips, 100))
        total_chunks = len(chunks)

        for i, chunk in enumerate(chunks, 1):
            payload = [{"query": ip, "fields": fields} for ip in chunk]
            
            try:
                console.log(f"[dim]   [batch {i}/{total_chunks}] Analyzing {len(chunk)} IPs...[/dim]")
                response = requests.post(
                    self.api_url, 
                    json=payload, 
                    headers=self.headers, 
                    timeout=15
                )
                
                if response.status_code == 200:
                    data = response.json()
                    for item in data:
                        if item.get('status') == 'success':
                            results.append({
                                "ip": item.get('query'),
                                "country": item.get('countryCode'),
                                "isp": item.get('isp'),
                                "org": item.get('org'),
                                "asn": item.get('as')
                            })
                        else:
                            results.append({
                                "ip": item.get('query'),
                                "error": "Private/Reserved"
                            })
                else:
                    console.print(f"[bold red][!] API Error batch {i}: {response.status_code}[/bold red]")

            except Exception as e:
                console.print(f"[bold red][!] Connection Error: {e}[/bold red]")

        return results