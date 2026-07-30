import argparse
import sys
import json
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box
from rich.progress import track

from modules.email_harvester import EmailHarvester
from modules.recon import DomainRecon
from modules.whois_info import WhoisRecon
from modules.netblock import NetBlockAnalyzer
from modules.http_inspector import HttpInspector
from modules.vuln_scan import VulnScanner
from modules.favicon_recon import FaviconRecon
from modules.id_analytics import AnalyticsRecon
from modules.wayback_recon import WaybackRecon
from modules.js_secrets import JsSecrets
from modules.tech_fingerprint import TechFingerprint
from modules.dns_deep import DnsDeep
from modules.urldna_recon import UrlDnaRecon
from modules.bucket_finder import BucketFinder
# ── External tools wrappers ──────────────────────────────────────────────────
from modules.photon_wrapper import PhotonRunner

console = Console()


def show_custom_help():
    console.print("\n")
    console.print(Panel("[bold cyan]Total Domain Discovery Tool [/bold cyan] - Advanced Attack Surface Mapper", border_style="cyan"))

    console.print("[bold yellow]USAGE:[/bold yellow]")
    console.print("  python main.py [bold white]<target_domain>[/bold white] [flags]")

    t_flags = Table(box=box.SIMPLE, show_header=True, header_style="bold green")
    t_flags.add_column("Flag", style="cyan", width=20)
    t_flags.add_column("Description", style="white")

    t_flags.add_row("-h, --help",     "Show this help message and exit.")
    t_flags.add_row("-l, --light",    "[bold green]PASSIVE MODE (Safe)[/bold green]. Disables active port scanning. Includes Whois, Email, Deep OSINT.")
    t_flags.add_row("-d, --deep",     "Run Deep OSINT modules (Favicon, ID Analytics, Wayback, JS Secrets, urlDNA).")
    t_flags.add_row("-e, --email",    "Run People/Email harvesting (Bing/DDG/GitHub/Phonebook/Hunter.io).")
    t_flags.add_row("-w, --whois",    "Run only WHOIS identity check.")
    t_flags.add_row("-r, --recon",    "Run only Infrastructure Recon (Subdomains + Ports).")
    t_flags.add_row("--dns",          "Run Deep DNS Recon (MX, SPF, DMARC, NS, Subdomain Takeover).")
    t_flags.add_row("--buckets",      "Run Cloud Bucket Finder (S3, Azure, GCP).")
    t_flags.add_row("--photon",       "Run external tool Photon via CLI subprocess (if installed/configured in PATH or .env).")
    t_flags.add_row("-o <file.json>", "Save the final report to a JSON file.")

    console.print(t_flags)

    console.print("\n[bold yellow]MODULES EXPLAINED:[/bold yellow]")

    t_mods = Table(box=box.ROUNDED, show_header=True, header_style="bold magenta")
    t_mods.add_column("Module", style="bold white", width=25)
    t_mods.add_column("Type",   width=10)
    t_mods.add_column("Details", style="dim")

    t_mods.add_row("Identity (Whois)",  "Passive", "Retrieves registrar info, organization name, and abuse contacts.")
    t_mods.add_row("Recon (Subs)",      "Passive", "Aggregates subdomains from crt.sh and HackerTarget.")
    t_mods.add_row("Port Scan",         "Mixed",   "Light: Queries Shodan InternetDB. Full: Connects via Socket.")
    t_mods.add_row("Tech Fingerprint",  "Passive", "Wappalyzer-like offline: 40+ tech signatures (CMS, CDN, WAF...).")
    t_mods.add_row("Email Harvest",     "Passive", "Bing/DuckDuckGo/GitHub/Phonebook.cz/Hunter.io.")
    t_mods.add_row("Deep DNS",          "Passive", "MX, SPF, DMARC, NS, CNAME, IPv6, Subdomain Takeover check.")
    t_mods.add_row("Deep: Favicon",     "Passive", "HTML-first favicon parse + MurmurHash3 + Shodan dork.")
    t_mods.add_row("Deep: Analytics",   "Passive", "Extracts UA/G-Tag IDs to find correlated domains.")
    t_mods.add_row("Deep: Wayback",     "Passive", "4 sources: Wayback Machine, CommonCrawl, OTX, URLScan.")
    t_mods.add_row("Deep: JS Secrets",  "Passive", "Photon-like: crawls JS files for API keys, tokens, endpoints.")
    t_mods.add_row("Deep: urlDNA",      "Passive", "urlDNA.io: threat verdict, technologies, cookies, network transactions.")
    t_mods.add_row("Bucket Finder",     "Passive", "GrayhatWarfare + brute-force S3/Azure/GCP bucket names.")
    t_mods.add_row("External: Photon",  "Active",  "Executes Photon web crawler CLI to dump secret keys & deep intel.")

    console.print(t_mods)

    console.print("\n[bold red]LEGAL DISCLAIMER:[/bold red]")
    console.print("  Usage of this tool for attacking targets without prior mutual consent is illegal.")
    console.print("  Use the [bold green]--light[/bold green] flag for passive-only research (OSINT).")
    console.print("\n")
    sys.exit(0)


def main():
    if "-h" in sys.argv or "--help" in sys.argv:
        show_custom_help()

    parser = argparse.ArgumentParser(description="EASM Tool", add_help=False)
    parser.add_argument("domain",  help="Target domain")
    parser.add_argument("-w", "--whois",   action="store_true")
    parser.add_argument("-r", "--recon",   action="store_true")
    parser.add_argument("-e", "--email",   action="store_true")
    parser.add_argument("-d", "--deep",    action="store_true")
    parser.add_argument("-l", "--light",   action="store_true")
    parser.add_argument("--dns",           action="store_true")
    parser.add_argument("--buckets",       action="store_true")
    parser.add_argument("--photon",        action="store_true")
    parser.add_argument("-o", "--output",  default=None)

    args = parser.parse_args()

    # Se non c'è nessun flag specifico → run all (compresa la prova di lanciare tool esterni come photon se presenti)
    run_all = not (args.whois or args.recon or args.email or args.deep or args.dns or args.buckets or args.photon)
    is_light_mode = args.light

    do_whois   = args.whois   or is_light_mode or run_all
    do_recon   = args.recon   or is_light_mode or run_all
    do_email   = args.email   or is_light_mode or run_all
    do_deep    = args.deep    or is_light_mode or run_all
    do_dns     = args.dns     or is_light_mode or run_all
    do_buckets = args.buckets or run_all
    do_photon  = args.photon  or run_all

    full_report = {
        "target":         args.domain,
        "scan_date":      datetime.now().isoformat(),
        "mode":           "LIGHT (Passive)" if is_light_mode else "FULL (Active)",
        "identity":       {},
        "dns":            {},
        "attack_surface": [],
        "deep_osint":     {},
        "people":         {},
        "buckets":        {},
        "external_tools": {}
    }

    mode_color = "green" if is_light_mode else "red"
    console.print(Panel(
        f"[bold blue]Target Analysis:[/bold blue] {args.domain}\n"
        f"[white]Mode:[/white] [bold {mode_color}]{full_report['mode']}[/bold {mode_color}]",
        border_style="blue"
    ))

    # ──────────────────────────────────────────────────────────────────────
    # PHASE 1: WHOIS
    # ──────────────────────────────────────────────────────────────────────
    if do_whois:
        console.print(f"\n[bold yellow][*] Fetching Identity Data (Whois)...[/bold yellow]")
        whois_engine = WhoisRecon(args.domain)
        raw_text, error = whois_engine.get_raw_whois()
        full_report['identity'] = {"raw_output": raw_text if not error else error}
        if error:
            console.print(f"[bold red][!] Whois Error:[/bold red] {error}")
        else:
            console.print(Panel(Text(raw_text, style="white"), title="WHOIS DATA", border_style="green", box=box.ROUNDED))

    # ──────────────────────────────────────────────────────────────────────
    # PHASE 2: DEEP DNS
    # ──────────────────────────────────────────────────────────────────────
    if do_dns:
        console.print(f"\n[bold yellow][*] Running Deep DNS Recon...[/bold yellow]")
        dns_engine = DnsDeep(args.domain)
        with console.status("[bold green]Analyzing DNS records...[/bold green]"):
            dns_data = dns_engine.analyze()
        full_report['dns'] = dns_data

        dns_table = Table(title="DNS Deep Recon", border_style="blue", box=box.SIMPLE)
        dns_table.add_column("Record Type", style="cyan", width=22)
        dns_table.add_column("Value", style="white")

        mx_str = ", ".join(dns_data.get('mx', {}).get('records', [])) or "None"
        dns_table.add_row("MX / Mail Provider", f"{mx_str}\n[dim]{dns_data.get('mx', {}).get('provider', '')}[/dim]")
        dns_table.add_row("NS", ", ".join(dns_data.get('ns', [])) or "None")

        spf = dns_data.get('spf', {})
        spf_str = spf.get('strength', 'Not found') if spf.get('found') else "[bold red]NOT FOUND[/bold red]"
        dns_table.add_row("SPF", spf_str)

        dmarc = dns_data.get('dmarc', {})
        dmarc_str = f"p={dmarc.get('policy','?')} — {dmarc.get('strength','')}" if dmarc.get('found') else "[bold red]NOT FOUND[/bold red]"
        dns_table.add_row("DMARC", dmarc_str)

        dns_table.add_row("IPv6", "[green]Supported[/green]" if dns_data.get('ipv6', {}).get('supported') else "[dim]Not supported[/dim]")

        takeovers = dns_data.get('takeover_risks', [])
        if takeovers:
            t_str = "\n".join(f"[bold red]{t['cname']}[/bold red] → {t['service']}" for t in takeovers)
            dns_table.add_row("[bold red]⚠ Takeover Risk[/bold red]", t_str)

        console.print(dns_table)

    # ──────────────────────────────────────────────────────────────────────
    # PHASE 3: RECON (SUBDOMAINS & PORTS)
    # ──────────────────────────────────────────────────────────────────────
    if do_recon:
        recon_engine = DomainRecon(args.domain)

        with console.status("[bold green]Harvesting subdomains...[/bold green]"):
            subs = recon_engine.get_subdomains()

        if not subs:
            console.print("[bold red][!] No subdomains found (or API limit reached).[/bold red]")
            console.print(f"[bold green]   [+] Switching fallback: Scanning main target '{args.domain}' only.[/bold green]")
            subs = [args.domain]
        else:
            if args.domain not in subs:
                subs.append(args.domain)
            console.print(f"   [dim]> Found {len(subs)} historical subdomains.[/dim]")

        with console.status("[bold green]Verifying DNS resolution...[/bold green]"):
            live_results = recon_engine.verify_live_domains(subs)

        if not live_results:
            console.print("[bold red][CRITICAL] Target unreachable. DNS resolution failed for main domain.[/bold red]")
        else:
            unique_ips = list(set(live_results.values()))
            nb_analyzer = NetBlockAnalyzer()
            with console.status("[bold green]Analyzing NetBlocks (ISP/ASN)...[/bold green]"):
                net_data = nb_analyzer.analyze_ips(unique_ips)
                ip_map = {item['ip']: item for item in net_data if 'ip' in item}

            http_engine = HttpInspector()
            vuln_engine = VulnScanner()
            tech_engine = TechFingerprint()

            port_header = "Ports (Passive)" if is_light_mode else "Ports (Active)"
            main_table = Table(
                title=f"Attack Surface Map: {args.domain}",
                border_style="cyan", box=box.HEAVY_HEAD
            )
            main_table.add_column("Subdomain",  style="cyan")
            main_table.add_column("IP / Info",  style="white")
            main_table.add_column(port_header,  style="red")
            main_table.add_column("HTTP",       style="bold")
            main_table.add_column("Tech Stack", style="magenta")

            console.print(f"\n[bold yellow][*] Deep Inspection...[/bold yellow]")

            for domain in track(sorted(live_results.keys()), description="[green]Scanning assets...[/green]"):
                ip        = live_results[domain]
                infra     = ip_map.get(ip, {})
                vuln_data = vuln_engine.scan_ip(ip, passive_only=is_light_mode)
                web       = http_engine.inspect(domain)
                tech_data = tech_engine.detect(domain)
                found_ports = vuln_data.get('ports', [])

                ports_display = "-"
                if found_ports:
                    criticals = vuln_engine.is_critical(found_ports)
                    ports_display = (
                        f"[bold red]{', '.join(criticals)}[/bold red]"
                        if criticals else f"[dim]{len(found_ports)} ports[/dim]"
                    )

                tech_list = tech_data.get('technologies', [])
                tech_str  = ", ".join(tech_list[:3]) if tech_list else "N/A"
                missing_sec = tech_data.get('missing_security_headers', [])
                sec_warn = f"\n[dim red]⚠ {', '.join(missing_sec[:2])}[/dim red]" if missing_sec else ""

                full_report['attack_surface'].append({
                    "subdomain": domain,
                    "ip":        ip,
                    "security":  vuln_data,
                    "web":       {"url": web['url'], "status": web['status_code'], "title": web['title']},
                    "tech":      tech_data
                })

                status_str = str(web['status_code'])
                if web['status_code'] == 200:
                    status_str = f"[green]{status_str}[/green]"

                org = infra.get('org', 'N/A')
                main_table.add_row(
                    domain,
                    f"{ip}\n[dim]{org}[/dim]",
                    ports_display,
                    status_str,
                    f"{tech_str}{sec_warn}"
                )

            console.print(main_table)

    # ──────────────────────────────────────────────────────────────────────
    # PHASE 4: DEEP OSINT
    # ──────────────────────────────────────────────────────────────────────
    if do_deep:
        console.print(Panel("[bold purple]DEEP OSINT MODULES[/bold purple]", border_style="purple"))
        deep_results = {}

        # 4.1 Favicon (HTML-first)
        fav_engine = FaviconRecon(args.domain)
        with console.status("[bold purple]Hunting Favicon Hash & Fingerprinting...[/bold purple]"):
            fav_data = fav_engine.analyze()

        if fav_data['found']:
            source_label = "HTML <link>" if fav_data.get('source') == 'html_tag' else "/favicon.ico fallback"
            console.print(f"[bold green][+] Favicon Found![/bold green] [dim]({source_label})[/dim] Hash: [cyan]{fav_data['hash']}[/cyan]")
            if fav_data['tech'] != "Unknown":
                console.print(f"    [bold red](!) Technology:[/bold red] {fav_data['tech']}")
            if fav_data['related_hosts']:
                console.print(f"    [bold yellow][*] Related Hosts (Shodan):[/bold yellow] {', '.join(fav_data['related_hosts'][:3])}")
            deep_results['favicon'] = fav_data
        else:
            console.print("[dim][-] No favicon data found.[/dim]")

        # 4.2 ID Analytics
        id_engine = AnalyticsRecon(args.domain)
        with console.status("[bold purple]Analyzing Tracker IDs...[/bold purple]"):
            ids = id_engine.search_ids()

        if ids:
            console.print(f"\n[bold green][+] Detected Trackers:[/bold green]")
            for tech, data in ids.items():
                console.print(f"    - [cyan]{tech}:[/cyan] {', '.join(data['ids'])}")
                if data['related_domains']:
                    console.print(f"      [bold red](!) Shared with:[/bold red] {', '.join(data['related_domains'])}")
            deep_results['analytics'] = ids
        else:
            console.print("[dim][-] No Analytics IDs found.[/dim]")

        # 4.3 Wayback Multi-Source
        wb_engine = WaybackRecon(args.domain)
        with console.status("[bold purple]Time Traveling (Wayback + CommonCrawl + OTX + URLScan)...[/bold purple]"):
            wb_result = wb_engine.find_secrets()

        secrets    = wb_result.get('all', [])
        by_source  = wb_result.get('by_source', {})
        if secrets:
            console.print(f"\n[bold red][!] Found {len(secrets)} historical sensitive files:[/bold red]")
            for source, urls in by_source.items():
                if urls:
                    console.print(f"    [dim]({source}: {len(urls)} files)[/dim]")
            for url in secrets[:5]:
                console.print(f"    [dim]- {url}[/dim]")
            if len(secrets) > 5:
                console.print(f"    [dim]... and {len(secrets)-5} more.[/dim]")
            deep_results['historical_secrets'] = wb_result
        else:
            console.print("[dim][-] No sensitive historical files found.[/dim]")

        # 4.4 JS Secrets (Photon-like Python engine)
        console.print(f"\n[bold purple][*] Scanning JS files for secrets & hidden endpoints (Internal Engine)...[/bold purple]")
        js_engine = JsSecrets(args.domain)
        with console.status("[bold purple]Crawling JS files...[/bold purple]"):
            js_data = js_engine.scan()

        if js_data.get('found'):
            if js_data['secrets']:
                console.print(f"[bold red][!] SECRETS FOUND ({js_data['js_files_scanned']} JS files scanned):[/bold red]")
                for stype, matches in js_data['secrets'].items():
                    preview = matches[0][:60] + ('...' if len(matches[0]) > 60 else '')
                    console.print(f"    [bold red]• {stype}:[/bold red] {preview}")
            if js_data['endpoints']:
                console.print(f"[bold yellow][*] Hidden API endpoints: {len(js_data['endpoints'])}[/bold yellow]")
                for ep in js_data['endpoints'][:5]:
                    console.print(f"    [dim]- {ep}[/dim]")
            if js_data['emails']:
                console.print(f"[bold green][+] Emails in JS: {', '.join(js_data['emails'][:3])}[/bold green]")
            deep_results['js_secrets'] = js_data
        else:
            console.print(f"[dim][-] No secrets found in JS ({js_data.get('js_files_scanned', 0)} files scanned).[/dim]")

        # 4.5 urlDNA (Enriched Display)
        console.print(f"\n[bold purple][*] urlDNA.io Deep Analysis...[/bold purple]")
        urldna_engine = UrlDnaRecon(args.domain)
        with console.status("[bold purple]Fetching urlDNA intelligence...[/bold purple]"):
            urldna_data = urldna_engine.analyze()

        if urldna_data and 'error' not in urldna_data and urldna_data:
            verdict = urldna_data.get('verdict', 'Unknown')
            v_lower = verdict.lower()
            verdict_color = "green" if "clean" in v_lower or "safe" in v_lower else ("red" if any(w in v_lower for w in ["malicious", "phishing", "unsafe"]) else "yellow")
            
            console.print(f"[bold {verdict_color}]   [+] [urlDNA] Verdict: {verdict}[/bold {verdict_color}] (Scan ID: {urldna_data.get('scan_id')})")
            
            if urldna_data.get('technologies'):
                console.print(f"   [bold cyan]   • Technologies:[/bold cyan] {', '.join(urldna_data['technologies'])}")
            if urldna_data.get('cookies'):
                console.print(f"   [bold yellow]   • Cookies Detected:[/bold yellow]")
                for c in urldna_data['cookies'][:5]:
                    console.print(f"     [dim]- {c}[/dim]")
            if urldna_data.get('http_transactions'):
                console.print(f"   [bold magenta]   • Observed Endpoints ({len(urldna_data['http_transactions'])} total):[/bold magenta]")
                for tx in urldna_data['http_transactions'][:5]:
                    console.print(f"     [dim]- {tx}[/dim]")
            if urldna_data.get('console_messages'):
                console.print(f"   [bold red]   • Browser Console Warnings:[/bold red]")
                for msg in urldna_data['console_messages'][:3]:
                    console.print(f"     [dim]{msg}[/dim]")
            
            deep_results['urldna'] = urldna_data
        elif "error" in urldna_data:
            console.print(f"   [dim red]   [-] urlDNA Error: {urldna_data['error']}[/dim red]")
        else:
            console.print("   [dim]   [-] Nessuna informazione urlDNA trovata per questo target.[/dim]")

        full_report['deep_osint'] = deep_results

    # ──────────────────────────────────────────────────────────────────────
    # PHASE 5: EMAIL
    # ──────────────────────────────────────────────────────────────────────
    if do_email:
        console.print(f"\n[bold yellow][*] Harvesting Emails (multi-source)...[/bold yellow]")
        harvester = EmailHarvester(args.domain)
        with console.status("[bold green]Searching for employees...[/bold green]"):
            email_data = harvester.harvest()

        if "error" in email_data:
            console.print(f"[bold red][!] Error:[/bold red] {email_data['error']}")
        else:
            full_report['people'] = email_data
            console.print(f"   [dim]> Found {email_data['total_found']} addresses.[/dim]")
            active_sources = [s for s, v in email_data.get('sources_used', {}).items() if v]
            console.print(f"   [dim]> Sources: {', '.join(active_sources)}[/dim]")
            all_found = email_data.get('people', []) + email_data.get('generic', [])
            if all_found:
                console.print(f"   [bold cyan]> Pattern (Employees):[/bold cyan] {email_data['naming_convention']}")
                p_table = Table(title="Email Intelligence & Domain Contacts", border_style="magenta", box=box.SIMPLE)
                p_table.add_column("Email Address", style="bold white")
                p_table.add_column("Type", style="dim")
                for email in email_data.get('people', [])[:15]:
                    p_table.add_row(email, "[cyan]Employee / Personal[/cyan]")
                for email in email_data.get('generic', [])[:15]:
                    p_table.add_row(email, "[yellow]Domain / Department[/yellow]")
                console.print(p_table)
            else:
                console.print("[dim]   [-] Nessun indirizzo email pubblico rilevato.[/dim]")

    # ──────────────────────────────────────────────────────────────────────
    # PHASE 6: BUCKET FINDER
    # ──────────────────────────────────────────────────────────────────────
    if do_buckets:
        console.print(f"\n[bold yellow][*] Cloud Bucket Finder (S3/Azure/GCP)...[/bold yellow]")
        bucket_engine = BucketFinder(args.domain)
        with console.status("[bold green]Searching for exposed buckets...[/bold green]"):
            bucket_data = bucket_engine.find()

        full_report['buckets'] = bucket_data
        if bucket_data['open_count'] > 0:
            console.print(f"[bold red][!] {bucket_data['open_count']} OPEN buckets found![/bold red]")
            for b in bucket_data['open']:
                console.print(f"    [bold red]• {b['provider']}: {b['url']}[/bold red]")
        elif bucket_data['total'] > 0:
            console.print(f"[dim][+] {bucket_data['total']} bucket(s) exist but access-restricted (403).[/dim]")
        else:
            console.print("[dim][-] No exposed buckets found.[/dim]")

    # ──────────────────────────────────────────────────────────────────────
    # PHASE 7: EXTERNAL CLI TOOLS (Photon) — Full Output Display
    # ──────────────────────────────────────────────────────────────────────
    if do_photon:
        console.print(f"\n[bold yellow][*] External Tools: Photon Web Crawler CLI...[/bold yellow]")
        photon_engine = PhotonRunner(args.domain)
        with console.status("[bold green]Running Photon via CLI subprocess...[/bold green]"):
            photon_data = photon_engine.run()

        full_report['external_tools']['photon'] = photon_data
        if not photon_data.get("installed", False):
            console.print("[dim]   [-] Photon non trovato in PATH (o PHOTON_PATH). Modulo saltato.[/dim]")
        elif "error" in photon_data and photon_data.get("error"):
            console.print(f"[bold red]   [!] Errore da Photon:[/bold red] {photon_data['error']}")
        else:
            console.print(f"[bold green]   [+] Photon scan completato con successo![/bold green]\n")

            # 1. CHIAVI E SEGRETI
            keys = photon_data.get("keys", [])
            if keys:
                t_keys = Table(title="[!][!][!] PHOTON: EXTRACTED SECRETS & KEYS [!][!][!]", border_style="bold red", box=box.ROUNDED)
                t_keys.add_column("Secret / Token match", style="bold yellow")
                for k in keys:
                    t_keys.add_row(k)
                console.print(t_keys)
            else:
                console.print("[dim]   • Keys/Secrets: Nessun token segreto rilevato direttamente.[/dim]")

            # 2. URL INTERNI CRAWLATI (internal.txt)
            internal_urls = photon_data.get("internal", [])
            if internal_urls:
                console.print(f"   [bold cyan]• URL Interni Esplorati ({len(internal_urls)}):[/bold cyan]")
                for u in internal_urls[:12]: # Primi 12 a schermo
                    console.print(f"     [dim]- {u}[/dim]")
                if len(internal_urls) > 12:
                    console.print(f"     [dim]... e altri {len(internal_urls)-12} nel report JSON.[/dim]")

            # 3. URL ESTERNI RILEVATI (external.txt)
            external_urls = photon_data.get("external", [])
            if external_urls:
                console.print(f"\n   [bold yellow]• Link & Domini Esterni Citati ({len(external_urls)}):[/bold yellow]")
                for eu in external_urls[:8]:
                    console.print(f"     - [white]{eu}[/white]")
                if len(external_urls) > 8:
                    console.print(f"     [dim]... e altri {len(external_urls)-8} nel report JSON.[/dim]")

            # 4. SCRIPT JAVASCRIPT (scripts.txt)
            scripts = photon_data.get("scripts", [])
            if scripts:
                console.print(f"\n   [bold magenta]• Script JS analizzati ({len(scripts)}):[/bold magenta]")
                for sc in scripts[:6]:
                    console.print(f"     [dim]- {sc}[/dim]")

            # 5. URL FUZZABLE (con parametri GET, fuzzable.txt)
            fuzzable = photon_data.get("fuzzable", [])
            if fuzzable:
                console.print(f"\n   [bold red]• URL con parametri 'Fuzzable' (Ottimi per Pentest/Injection):[/bold red]")
                for fz in fuzzable:
                    console.print(f"     [bold underline red]! {fz}[/bold underline red]")

            # 6. INTEL & FILES
            intel = photon_data.get("intel", [])
            if intel:
                console.print(f"\n   [bold green]• Intel / Metadata ({len(intel)}):[/bold green]")
                for idx, i in enumerate(intel[:5]):
                    console.print(f"     - {i}")

            files = photon_data.get("files", [])
            if files:
                console.print(f"\n   [bold blue]• File documentali scovati ({len(files)}):[/bold blue]")
                for doc in files:
                    console.print(f"     - {doc}")

    # ──────────────────────────────────────────────────────────────────────
    # PHASE 8: SAVE REPORT
    # ──────────────────────────────────────────────────────────────────────
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(full_report, f, indent=4)
            console.print(f"\n[bold blue][SAVE][/bold blue] Report saved: [underline]{args.output}[/underline]")
        except Exception as e:
            console.print(f"[bold red][ERROR][/bold red] Save failed: {e}")


if __name__ == "__main__":
    main()