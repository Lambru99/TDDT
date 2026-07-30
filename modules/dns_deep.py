"""
dns_deep.py — DNS Recon approfondito.
Recupera MX, TXT, SPF, DMARC, NS, CNAME, AAAA, SOA e verifica
pattern di subdomain takeover noti. Usa DNSPython (già nel requirements).
"""
import dns.resolver
import dns.exception


# Pattern CNAME che indicano possibile subdomain takeover
# (servizio non più attivo o non rivendicato)
TAKEOVER_PATTERNS = {
    "AWS S3":             r'\.s3\.amazonaws\.com$',
    "AWS S3 Website":     r'\.s3-website[.-]',
    "GitHub Pages":       r'\.github\.io$',
    "Heroku":             r'\.herokuapp\.com$',
    "Fastly":             r'\.fastly\.net$|\.fastlylb\.net$',
    "Zendesk":            r'\.zendesk\.com$',
    "Shopify":            r'\.myshopify\.com$',
    "Tumblr":             r'\.tumblr\.com$',
    "Cargo":              r'\.cargocollective\.com$',
    "Surge.sh":           r'\.surge\.sh$',
    "Bitbucket":          r'\.bitbucket\.io$',
    "Desk":               r'\.desk\.com$',
    "Helpjuice":          r'\.helpjuice\.com$',
    "HelpScout":          r'\.helpscoutdocs\.com$',
    "Ghost":              r'\.ghost\.io$',
    "Pingdom":            r'\.pingdom\.net$',
    "Readme.io":          r'\.readme\.io$',
}

import re


def _resolve(domain, rtype):
    """Risolve un record DNS e restituisce la lista di valori o []."""
    try:
        answers = dns.resolver.resolve(domain, rtype, lifetime=5)
        return [str(r) for r in answers]
    except Exception:
        return []


class DnsDeep:
    def __init__(self, domain):
        self.domain = domain

    def _check_spf(self, txt_records: list) -> dict:
        """Analizza i record TXT per trovare e valutare SPF."""
        for record in txt_records:
            if record.startswith('"v=spf1') or record.startswith('v=spf1'):
                spf = record.strip('"')
                strength = "Unknown"
                if '~all' in spf:
                    strength = "SoftFail (~all) — medium"
                elif '-all' in spf:
                    strength = "Fail (-all) — strict"
                elif '+all' in spf:
                    strength = "Pass (+all) — DANGEROUS: accepts all"
                elif '?all' in spf:
                    strength = "Neutral (?all) — weak"
                return {"found": True, "record": spf, "strength": strength}
        return {"found": False}

    def _check_dmarc(self) -> dict:
        """Recupera e valuta il record DMARC."""
        records = _resolve(f"_dmarc.{self.domain}", 'TXT')
        for r in records:
            r = r.strip('"')
            if 'v=DMARC1' in r:
                policy = "none"
                m = re.search(r'p=(\w+)', r)
                if m:
                    policy = m.group(1)
                strength = {
                    "none":       "Monitor only (no enforcement)",
                    "quarantine": "Quarantine — medium protection",
                    "reject":     "Reject — strict protection",
                }.get(policy, "Unknown")
                return {"found": True, "record": r, "policy": policy, "strength": strength}
        return {"found": False}

    def _check_subdomain_takeover(self, cname_targets: list) -> list:
        """Verifica CNAME contro pattern noti di subdomain takeover."""
        vulnerable = []
        for cname in cname_targets:
            for service, pattern in TAKEOVER_PATTERNS.items():
                if re.search(pattern, cname, re.IGNORECASE):
                    vulnerable.append({
                        "cname": cname,
                        "service": service,
                        "risk": "Potential Subdomain Takeover"
                    })
        return vulnerable

    def _infer_mail_provider(self, mx_records: list) -> str:
        """Inferisce il provider email dai record MX."""
        mx_str = " ".join(mx_records).lower()
        if 'google' in mx_str or 'googlemail' in mx_str:
            return "Google Workspace"
        if 'outlook' in mx_str or 'protection.outlook' in mx_str or 'microsoft' in mx_str:
            return "Microsoft 365"
        if 'pphosted' in mx_str or 'proofpoint' in mx_str:
            return "Proofpoint"
        if 'mimecast' in mx_str:
            return "Mimecast"
        if 'messagelabs' in mx_str or 'symantec' in mx_str:
            return "Broadcom/Symantec Email Security"
        if 'mailgun' in mx_str:
            return "Mailgun"
        if 'amazonses' in mx_str:
            return "Amazon SES"
        return "Self-hosted / Custom"

    def analyze(self) -> dict:
        """Esegue il DNS recon completo. Nessuna API key necessaria."""
        result = {}

        # MX records
        mx = _resolve(self.domain, 'MX')
        result['mx'] = {
            'records': mx,
            'provider': self._infer_mail_provider(mx) if mx else "None found"
        }

        # NS records
        ns = _resolve(self.domain, 'NS')
        result['ns'] = ns

        # TXT records (inclusi SPF)
        txt = _resolve(self.domain, 'TXT')
        result['txt'] = txt
        result['spf'] = self._check_spf(txt)

        # DMARC
        result['dmarc'] = self._check_dmarc()

        # AAAA (IPv6)
        aaaa = _resolve(self.domain, 'AAAA')
        result['ipv6'] = {'supported': bool(aaaa), 'addresses': aaaa}

        # SOA
        soa = _resolve(self.domain, 'SOA')
        result['soa'] = soa[0] if soa else None

        # CNAME su www e su subdomain wildcard comuni
        cname_targets = []
        for sub in ['www', 'mail', 'ftp', 'blog', 'shop', 'api', 'dev', 'staging', 'app']:
            cnames = _resolve(f"{sub}.{self.domain}", 'CNAME')
            for c in cnames:
                cname_targets.append(c)

        result['cname_targets'] = cname_targets

        # Subdomain takeover check
        takeover_risks = self._check_subdomain_takeover(cname_targets)
        result['takeover_risks'] = takeover_risks

        return result
