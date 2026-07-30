"""
urldna_recon.py — urlDNA.io Deep Analysis
Usa il package Python ufficiale 'urldna' per ottenere analisi completa:
technologies, threat intel, cookies, HTTP metadata, console messages e network transactions.
Richiede URLDNA_API_KEY nel .env.
"""
import time
from modules.config import require_api_key


class UrlDnaRecon:
    def __init__(self, domain):
        self.domain = domain

    def analyze(self) -> dict:
        """
        Esegue la scansione o cerca nello storico immediato di urlDNA e ritorna un dict strutturato.
        Ritorna {} se la API key non è configurata.
        """
        api_key = require_api_key('URLDNA_API_KEY', 'urlDNA.io')
        if not api_key:
            return {}

        try:
            from urldna import UrlDNA
        except ImportError:
            return {"error": "Package 'urldna' non installato. Esegui: pip install urldna"}

        try:
            client = UrlDNA(api_key)
            target_url = f"https://{self.domain}"
            scan_id = None

            # 1. Cerchiamo prima se esiste già una scansione recente del dominio
            try:
                search_results = client.search(self.domain)
                if search_results and len(search_results) > 0:
                    scan_id = search_results[0].id
            except Exception:
                pass

            # 2. Se non c'è nello storico, avviamo una nuova scansione
            if not scan_id:
                scan_result = client.create_scan(target_url)
                scan_id = scan_result.scan.id
                # Attendiamo qualche secondo che i server di urlDNA elaborino
                time.sleep(5)

            # 3. Recuperiamo l'oggetto scansione completo
            data = client.get_scan(scan_id)

            result = {
                "scan_id": str(scan_id),
                "url": target_url,
                "verdict": "Unknown",
                "technologies": [],
                "cookies": [],
                "http_transactions": [],
                "console_messages": [],
                "registrar": "Unknown"
            }

            # Threat classification / verdict (data.classification.verdict)
            try:
                if hasattr(data, 'classification') and data.classification:
                    verdict = getattr(data.classification, 'verdict', 'Unknown')
                    result["verdict"] = str(verdict)
            except Exception:
                pass

            # Technologies (data.technologies)
            try:
                if hasattr(data, 'technologies') and data.technologies:
                    for t in data.technologies:
                        name = getattr(t, 'name', 'Unknown')
                        version = getattr(t, 'version', None)
                        cat = getattr(t, 'category', '')
                        v_str = f" v{version}" if version else f" ({cat})" if cat else ""
                        result["technologies"].append(f"{name}{v_str}")
            except Exception:
                pass

            # Cookies (data.cookies)
            try:
                if hasattr(data, 'cookies') and data.cookies:
                    for c in data.cookies:
                        c_name = getattr(c, 'name', '')
                        c_val = getattr(c, 'value', '')
                        c_dom = getattr(c, 'domain', '')
                        result["cookies"].append(f"{c_name}={c_val[:20]}... [dom: {c_dom}]")
            except Exception:
                pass

            # HTTP Transactions / Endpoints
            try:
                if hasattr(data, 'http_transactions') and data.http_transactions:
                    for tr in data.http_transactions[:20]: # I primi 20 URL per non sovraccaricare
                        u = getattr(tr, 'url', '')
                        if u and u not in result["http_transactions"]:
                            result["http_transactions"].append(u)
            except Exception:
                pass

            # Console messages (allarmi CSP, errori JavaScript sul client, ecc.)
            try:
                if hasattr(data, 'console_messages') and data.console_messages:
                    for m in data.console_messages:
                        txt = getattr(m, 'text', '')
                        mtype = getattr(m, 'type', 'log')
                        if txt:
                            result["console_messages"].append(f"[{mtype}] {txt}")
            except Exception:
                pass

            # Whois dal report di urlDNA
            try:
                if hasattr(data, 'scan_whois') and data.scan_whois:
                    result["registrar"] = str(getattr(data.scan_whois, 'registrar', 'Unknown'))
            except Exception:
                pass

            return result

        except Exception as e:
            return {"error": str(e)}
