import requests
import re
import time
import random
from collections import Counter
from rich.console import Console

console = Console()

class EmailHarvester:
    def __init__(self, domain):
        self.domain = domain
        self.found_emails = set()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36 Edge/115.0.1901.188',
            'Referer': 'https://www.google.com/'
        }
        # Regex standard for email
        self.email_regex = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

    def _extract_emails(self, text):
        """Helper for extracting email from html"""
        matches = re.findall(self.email_regex, text)
        for email in matches:
            email = email.lower().strip()
            junk_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.css', '.js')
            if email.endswith(f"@{self.domain}") and not email.endswith(junk_extensions):
                self.found_emails.add(email)

    def _search_bing(self):
        """Bing Search"""
        base_url = "https://www.bing.com/search?q=%22%40{}%22&first={}"
        
        for page in range(0, 10, 1):
            try:
                console.log(f"[dim]   Querying Bing (page {int(page/10)+1})...[/dim]")
                url = base_url.format(self.domain, page)
                response = requests.get(url, headers=self.headers, timeout=10)
                
                if response.status_code == 200:
                    self._extract_emails(response.text)
                time.sleep(random.uniform(0.5, 1.5))
                
            except Exception:
                continue

    def _search_duckduckgo(self):
        """DuckDuckGo HTML Version"""
        url = "https://html.duckduckgo.com/html/"
        payload = {'q': f'"@{self.domain}"'}
        
        try:
            response = requests.post(url, data=payload, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                self._extract_emails(response.text)
            elif response.status_code == 403:
                console.print("[dim]   [!] DuckDuckGo rate limit (403). Skipping.[/dim]")
            
        except Exception:
            pass

    def _deduce_pattern(self):
        """Analyze found email"""
        if not self.found_emails:
            return "Unknown"

        patterns = []
        for email in self.found_emails:
            local_part = email.split('@')[0]            
            if local_part in ['info', 'admin', 'contact', 'support', 'sales']:
                continue

            if '.' in local_part:
                parts = local_part.split('.')
                if len(parts) == 2:
                    if len(parts[0]) == 1:
                        patterns.append("{initial}.{surname}") # m.rossi
                    else:
                        patterns.append("{name}.{surname}")   # mario.rossi
            elif len(local_part) > 3:
                 patterns.append("{surname}{initial} or {name}") # rossim or mario

        if not patterns:
            return "Custom/Mixed"
        
        most_common = Counter(patterns).most_common(1)
        return most_common[0][0]

    def harvest(self):
        try:
            self._search_bing()
            self._search_duckduckgo()
            
            pattern = self._deduce_pattern()
            
            generic_keywords = ['info', 'admin', 'contact', 'support', 'sales', 'hr', 'job', 'recruit', 'office', 'privacy', 'press']
            people = []
            generic = []

            for email in self.found_emails:
                local = email.split('@')[0]
                if any(k in local for k in generic_keywords):
                    generic.append(email)
                else:
                    people.append(email)

            return {
                "total_found": len(self.found_emails),
                "naming_convention": pattern,
                "people": sorted(people),
                "generic": sorted(generic)
            }

        except Exception as e:
            return {"error": str(e)}