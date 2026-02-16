import requests
import json
import time
import dns.resolver
from concurrent.futures import ThreadPoolExecutor
from rich.console import Console

console = Console()

class DomainRecon:
    def __init__(self, target_domain):
        self.target = target_domain
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*'
        }

    def _fetch_crt(self):
        """SOURCE A: Certificate Transparency Logs (crt.sh)"""
        console.print(f"[dim]   [debug] Querying crt.sh...[/dim]")
        url = f"https://crt.sh/?q=%.{self.target}&output=json"
        found_domains = set()

        for attempt in range(1, 4):
            try:
                response = requests.get(url, headers=self.headers, timeout=40)
                if response.status_code == 200:
                    try:
                        data = response.json()
                        for entry in data:
                            name_value = entry.get('name_value', '')
                            for line in name_value.split('\n'):
                                sub = line.strip().lower()
                                if '*' not in sub and sub.endswith(self.target):
                                    found_domains.add(sub)
                        return list(found_domains)
                    except json.JSONDecodeError:
                        pass
                elif response.status_code == 404:
                     pass 
                time.sleep(2)
            except Exception:
                time.sleep(2)

        return list(found_domains)

    def _fetch_hackertarget(self):
        """SOURCE B: HackerTarget Host Search"""
        console.print(f"[dim]   [debug] Querying HackerTarget...[/dim]")
        url = f"https://api.hackertarget.com/hostsearch/?q={self.target}"
        found_domains = set()

        try:
            response = requests.get(url, headers=self.headers, timeout=20)
            text = response.text

            if "API count exceeded" in text:
                console.print(f"[bold yellow]   [!] HackerTarget API Quota Exceeded (Skipping source)[/bold yellow]")
                return []
            
            if response.status_code == 200:
                lines = text.split('\n')
                for line in lines:
                    if ',' in line:
                        sub = line.split(',')[0].strip().lower()
                        if sub.endswith(self.target):
                            found_domains.add(sub)
            
            return list(found_domains)

        except Exception:
            return []

    def get_subdomains(self):
        all_results = set()
        
        crt_data = self._fetch_crt()
        if crt_data: all_results.update(crt_data)
        
        ht_data = self._fetch_hackertarget()
        if ht_data: all_results.update(ht_data)

        return sorted(list(all_results))

    def resolve_domain(self, subdomain):
        try:
            answers = dns.resolver.resolve(subdomain, 'A')
            return str(answers[0])
        except Exception:
            return None

    def verify_live_domains(self, subdomain_list, threads=20):
        live_data = {}
        with ThreadPoolExecutor(max_workers=threads) as executor:
            future_to_sub = {executor.submit(self.resolve_domain, sub): sub for sub in subdomain_list}
            for future in future_to_sub:
                sub = future_to_sub[future]
                try:
                    ip = future.result()
                    if ip:
                        live_data[sub] = ip
                except Exception:
                    pass
        return live_data