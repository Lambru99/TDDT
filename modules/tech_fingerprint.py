"""
tech_fingerprint.py — Wappalyzer-like offline technology detection.
Analizza headers HTTP, HTML, cookies e URL per identificare tecnologie.
Nessuna API key richiesta.
"""
import re
import requests
from bs4 import BeautifulSoup
from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# ── Signature database ────────────────────────────────────────────────────────
# Formato: { "Tech Name": { "check_type": pattern_or_list } }
# check_type: "header", "html", "cookie", "url", "meta", "script_src"
SIGNATURES = {
    # CMS
    "WordPress": {
        "html":       [r'/wp-content/', r'/wp-includes/'],
        "meta":       [r'name=["\']generator["\'].*WordPress'],
    },
    "Drupal": {
        "html":       [r'/sites/default/files/', r'Drupal\.settings'],
        "header":     {"X-Generator": r"Drupal"},
    },
    "Joomla": {
        "html":       [r'/components/com_', r'Joomla!'],
        "meta":       [r'name=["\']generator["\'].*Joomla'],
    },
    "Adobe Experience Manager": {
        "html":       [r'etc\.clientlibs/', r'/content/dam/', r'\.cq\.'],
        "header":     {"Server": r"Day-Servlet-Engine|Adobe"},
    },
    "Magento": {
        "html":       [r'Mage\.', r'/skin/frontend/', r'Magento'],
        "cookie":     [r'frontend'],
    },
    "Shopify": {
        "html":       [r'Shopify\.theme', r'cdn\.shopify\.com'],
    },
    "PrestaShop": {
        "html":       [r'prestashop', r'/themes/classic/'],
        "cookie":     [r'PrestaShop-'],
    },
    "Ghost": {
        "meta":       [r'name=["\']generator["\'].*Ghost'],
    },
    # Frontend Frameworks
    "React": {
        "html":       [r'__reactFiber', r'data-reactroot', r'_reactListening'],
        "script_src": [r'react\.min\.js', r'react-dom', r'chunk\.js'],
    },
    "Angular": {
        "html":       [r'ng-version=', r'ng-app=', r'ng-controller='],
        "script_src": [r'angular\.min\.js', r'angular\.js'],
    },
    "Vue.js": {
        "html":       [r'__vue_app__', r'data-v-', r'v-bind:', r'v-model='],
        "script_src": [r'vue\.min\.js', r'vue\.js'],
    },
    "Next.js": {
        "html":       [r'__NEXT_DATA__', r'/_next/static/'],
        "header":     {"X-Powered-By": r"Next\.js"},
    },
    "Nuxt.js": {
        "html":       [r'__NUXT__', r'/_nuxt/'],
    },
    # Backend / Servers
    "Apache": {
        "header":     {"Server": r"Apache"},
    },
    "Nginx": {
        "header":     {"Server": r"nginx"},
    },
    "IIS": {
        "header":     {"Server": r"Microsoft-IIS"},
    },
    "Caddy": {
        "header":     {"Server": r"Caddy"},
    },
    "Tomcat": {
        "header":     {"Server": r"Apache-Coyote|Tomcat"},
    },
    "Node.js / Express": {
        "header":     {"X-Powered-By": r"Express"},
    },
    "PHP": {
        "header":     {"X-Powered-By": r"PHP"},
        "cookie":     [r"PHPSESSID"],
    },
    "ASP.NET": {
        "header":     {"X-Powered-By": r"ASP\.NET", "X-AspNet-Version": r".+"},
        "cookie":     [r"ASP\.NET_SessionId"],
    },
    "Ruby on Rails": {
        "header":     {"X-Powered-By": r"Phusion Passenger"},
        "cookie":     [r"_rails_session", r"_session_id"],
    },
    # CDN / WAF
    "Cloudflare": {
        "header":     {"Server": r"cloudflare", "CF-RAY": r".+"},
    },
    "Akamai": {
        "header":     {"X-Check-Cacheable": r".+", "X-Akamai-Transformed": r".+"},
        "html":       [r'akamai', r'akam\.net'],
    },
    "Fastly": {
        "header":     {"X-Served-By": r"cache-", "Fastly-Stats": r".+"},
    },
    "AWS CloudFront": {
        "header":     {"Via": r"CloudFront", "X-Amz-Cf-Id": r".+"},
    },
    "Imperva / Incapsula": {
        "cookie":     [r"incap_ses", r"visid_incap"],
        "header":     {"X-CDN": r"Incapsula"},
    },
    "Sucuri": {
        "header":     {"X-Sucuri-ID": r".+"},
    },
    # Analytics & Monitoring
    "Google Analytics (GA4)": {
        "html":       [r'G-[A-Z0-9]{6,12}', r'gtag\('],
        "script_src": [r'googletagmanager\.com/gtag'],
    },
    "Google Tag Manager": {
        "html":       [r'GTM-[A-Z0-9]+'],
        "script_src": [r'googletagmanager\.com/gtm\.js'],
    },
    "Adobe Analytics": {
        "html":       [r's\.t\(\)', r'AppMeasurement'],
        "script_src": [r'omtrdc\.net', r'demdex\.net'],
    },
    "Dynatrace": {
        "html":       [r'ruxitagentjs_', r'data-dtconfig='],
        "script_src": [r'ruxitagentjs'],
    },
    "Hotjar": {
        "html":       [r'hjid:', r'hotjar\.com'],
        "script_src": [r'static\.hotjar\.com'],
    },
    "HubSpot": {
        "html":       [r'hs-analytics', r'hubspot\.com'],
        "script_src": [r'hs-scripts\.com', r'js\.hs-scripts'],
    },
    # E-commerce
    "WooCommerce": {
        "html":       [r'woocommerce', r'wc-cart'],
        "cookie":     [r"woocommerce_"],
    },
    # Search
    "Elasticsearch": {
        "html":       [r'elastic\.co'],
    },
    # Security Headers (not a tech, but useful)
}

SECURITY_HEADERS = [
    "Strict-Transport-Security",
    "Content-Security-Policy",
    "X-Frame-Options",
    "X-Content-Type-Options",
    "Referrer-Policy",
    "Permissions-Policy",
]


class TechFingerprint:
    def __init__(self):
        self.headers_http = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

    def _match(self, patterns, text) -> bool:
        if isinstance(patterns, list):
            return any(re.search(p, text, re.IGNORECASE) for p in patterns)
        if isinstance(patterns, str):
            return bool(re.search(patterns, text, re.IGNORECASE))
        return False

    def detect(self, domain: str) -> dict:
        """
        Rileva tecnologie per un dominio.
        Ritorna: { 'technologies': [...], 'security_headers': {header: present/missing} }
        """
        detected = []
        sec_headers = {}
        raw_headers = {}
        cookies_str = ""
        html_content = ""
        script_srcs = ""

        # Fetch della pagina
        for proto in ['https', 'http']:
            url = f"{proto}://{domain}"
            try:
                resp = requests.get(
                    url, headers=self.headers_http, timeout=8,
                    verify=False, allow_redirects=True
                )
                raw_headers = {k.lower(): v for k, v in resp.headers.items()}
                cookies_str = " ".join(resp.cookies.keys())
                html_content = resp.text[:80000]  # primi 80KB

                soup = BeautifulSoup(html_content, 'html.parser')
                script_srcs = " ".join(
                    tag.get('src', '') for tag in soup.find_all('script', src=True)
                )
                break
            except Exception:
                continue

        if not html_content:
            return {'technologies': [], 'security_headers': {}}

        # Applica le signature
        for tech_name, checks in SIGNATURES.items():
            matched = False

            if 'html' in checks and self._match(checks['html'], html_content):
                matched = True
            if not matched and 'meta' in checks and self._match(checks['meta'], html_content):
                matched = True
            if not matched and 'script_src' in checks and self._match(checks['script_src'], script_srcs):
                matched = True
            if not matched and 'cookie' in checks and self._match(checks['cookie'], cookies_str):
                matched = True
            if not matched and 'header' in checks:
                for hdr_name, hdr_pattern in checks['header'].items():
                    val = raw_headers.get(hdr_name.lower(), '')
                    if val and re.search(hdr_pattern, val, re.IGNORECASE):
                        matched = True
                        break

            if matched:
                detected.append(tech_name)

        # Security headers check
        for hdr in SECURITY_HEADERS:
            sec_headers[hdr] = hdr.lower() in raw_headers

        return {
            'technologies': detected,
            'security_headers': sec_headers,
            'missing_security_headers': [h for h, present in sec_headers.items() if not present]
        }
