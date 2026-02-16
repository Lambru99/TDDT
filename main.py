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

console = Console()

def show_custom_help():
    console.print("\n")
    console.print(Panel("[bold cyan]Total Domain Discovery Tool [/bold cyan] - Advanced Attack Surface Mapper", border_style="cyan"))
    
    # Usage
    console.print("[bold yellow]USAGE:[/bold yellow]")
    console.print("  python main.py [bold white]<target_domain>[/bold white] [flags]")
    
    # Flags Table
    t_flags = Table(box=box.SIMPLE, show_header=True, header_style="bold green")
    t_flags.add_column("Flag", style="cyan", width=15)
    t_flags.add_column("Description", style="white")
    
    t_flags.add_row("-h, --help", "Show this help message and exit.")
    t_flags.add_row("-l, --light", "[bold green]PASSIVE MODE (Safe)[/bold green]. Disables active port scanning. Includes Whois, Email, Deep OSINT.")
    t_flags.add_row("-d, --deep", "Run Deep OSINT modules (Favicon hashing, ID Analytics, Wayback History).")
    t_flags.add_row("-e, --email", "Run People/Email harvesting (Search Engine Scraping).")
    t_flags.add_row("-w, --whois", "Run only WHOIS identity check.")
    t_flags.add_row("-r, --recon", "Run only Infrastructure Recon (Subdomains + Ports).")
    t_flags.add_row("-o <file.json>", "Save the final report to a JSON file.")
    
    console.print(t_flags)

    # Modules Explanation
    console.print("\n[bold yellow]MODULES EXPLAINED:[/bold yellow]")
    
    t_mods = Table(box=box.ROUNDED, show_header=True, header_style="bold magenta")
    t_mods.add_column("Module", style="bold white", width=20)
    t_mods.add_column("Type", width=10)
    t_mods.add_column("Details", style="dim")
    
    t_mods.add_row("Identity (Whois)", "Passive", "Retrieves registrar info, organization name, and abuse contacts.")
    t_mods.add_row("Recon (Subs)", "Passive", "Aggregates subdomains from crt.sh and HackerTarget.")
    t_mods.add_row("Port Scan", "Mixed", "Checks open ports. [green]Light Mode[/green]: Queries Shodan. [red]Full Mode[/red]: Connects via Socket.")
    t_mods.add_row("Email Harvest", "Passive", "Scrapes Bing/DuckDuckGo for employee emails and infers naming conventions.")
    t_mods.add_row("Deep: Favicon", "Passive", "Fingerprints favicon hash and searches Shodan for hidden servers.")
    t_mods.add_row("Deep: Analytics", "Passive", "Extracts UA/G-Tag IDs to find correlated domains (Reverse Analytics).")
    t_mods.add_row("Deep: Wayback", "Passive", "Travels back in time to find deleted sensitive files (.env, .sql, .bak).")
    
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
    parser.add_argument("domain", help="Target domain")
    parser.add_argument("-w", "--whois", action="store_true")
    parser.add_argument("-r", "--recon", action="store_true")
    parser.add_argument("-e", "--email", action="store_true")
    parser.add_argument("-d", "--deep", action="store_true")
    parser.add_argument("-l", "--light", action="store_true")
    parser.add_argument("-o", "--output", default=None)
    
    args = parser.parse_args()

    run_all = not (args.whois or args.recon or args.email or args.deep)
    is_light_mode = args.light
    
    do_whois = args.whois or is_light_mode or run_all
    do_recon = args.recon or is_light_mode or run_all
    do_email = args.email or is_light_mode or run_all
    do_deep  = args.deep  or is_light_mode or run_all

    full_report = {
        "target": args.domain,
        "scan_date": datetime.now().isoformat(),
        "mode": "LIGHT (Passive)" if is_light_mode else "FULL (Active)",
        "identity": {},
        "attack_surface": []
    }

    mode_color = "green" if is_light_mode else "red"
    console.print(Panel(f"[bold blue]Target Analysis:[/bold blue] {args.domain}\n[white]Mode:[/white] [bold {mode_color}]{full_report['mode']}[/bold {mode_color}]", border_style="blue"))

    # PHASE 1: WHOIS
    if do_whois:
        console.print(f"\n[bold yellow][*] Fetching Identity Data (Whois)...[/bold yellow]")
        whois_engine = WhoisRecon(args.domain)
        raw_text, error = whois_engine.get_raw_whois()
        full_report['identity'] = {"raw_output": raw_text if not error else error}
        if error:
            console.print(f"[bold red][!] Whois Error:[/bold red] {error}")
        else:
            console.print(Panel(Text(raw_text, style="white"), title="WHOIS DATA", border_style="green", box=box.ROUNDED))

    # PHASE 2: RECON (SUBDOMAINS & PORTS)
    if do_recon:
        recon_engine = DomainRecon(args.domain)
        
        with console.status(f"[bold green]Harvesting subdomains...[/bold green]"):
            subs = recon_engine.get_subdomains()
        
        if not subs:
            console.print("[bold red][!] No subdomains found (or API limit reached).[/bold red]")
            console.print(f"[bold green]   [+] Switching fallback: Scanning main target '{args.domain}' only.[/bold green]")
            subs = [args.domain]
        else:
            if args.domain not in subs:
                subs.append(args.domain)
            console.print(f"   [dim]> Found {len(subs)} historical subdomains.[/dim]")
        
        with console.status(f"[bold green]Verifying DNS resolution...[/bold green]"):
            live_results = recon_engine.verify_live_domains(subs)
        
        if not live_results:
             console.print("[bold red][CRITICAL] Target unreachable. DNS resolution failed for main domain.[/bold red]")
        else:
            unique_ips = list(set(live_results.values()))
            nb_analyzer = NetBlockAnalyzer()
            with console.status(f"[bold green]Analyzing NetBlocks (ISP/ASN)...[/bold green]"):
                net_data = nb_analyzer.analyze_ips(unique_ips)
                ip_map = {item['ip']: item for item in net_data if 'ip' in item}

            http_engine = HttpInspector()
            vuln_engine = VulnScanner()
            
            port_header = "Ports (Passive)" if is_light_mode else "Ports (Active)"
            main_table = Table(title=f"Attack Surface Map: {args.domain}", border_style="cyan", box=box.HEAVY_HEAD)
            main_table.add_column("Subdomain", style="cyan")
            main_table.add_column("IP / Info", style="white")
            main_table.add_column(port_header, style="red")
            main_table.add_column("HTTP", style="bold")
            main_table.add_column("Tech", style="magenta")

            console.print(f"\n[bold yellow][*] Deep Inspection...[/bold yellow]")

            target_list = sorted(live_results.keys())

            for domain in track(target_list, description="[green]Scanning assets...[/green]"):
                ip = live_results[domain]
                infra = ip_map.get(ip, {})
                vuln_data = vuln_engine.scan_ip(ip, passive_only=is_light_mode)
                web = http_engine.inspect(domain)
                found_ports = vuln_data.get('ports', [])
                
                ports_display = "-"
                if found_ports:
                    criticals = vuln_engine.is_critical(found_ports)
                    if criticals:
                        ports_display = f"[bold red]{', '.join(criticals)}[/bold red]"
                    else:
                        ports_display = f"[dim]{len(found_ports)} ports[/dim]"

                asset_object = {
                    "subdomain": domain, "ip": ip, "security": vuln_data,
                    "web": {"url": web['url'], "status": web['status_code'], "title": web['title']}
                }
                full_report['attack_surface'].append(asset_object)

                status_str = str(web['status_code'])
                if web['status_code'] == 200: status_str = f"[green]{status_str}[/green]"
                org = infra.get('org', 'N/A')
                main_table.add_row(domain, f"{ip}\n[dim]{org}[/dim]", ports_display, status_str, f"{web['title'][:30]}")

            console.print(main_table)

    # PHASE 3: DEEP OSINT
    if do_deep:
        console.print(Panel(f"[bold purple]DEEP OSINT MODULES[/bold purple]", border_style="purple"))

        # 3.1 Favicon Analysis
        fav_engine = FaviconRecon(args.domain)
        with console.status("[bold purple]Hunting Favicon Hash & Fingerprinting...[/bold purple]"):
            fav_data = fav_engine.analyze()
        
        if fav_data['found']:
            console.print(f"[bold green][+] Favicon Found![/bold green] Hash: [cyan]{fav_data['hash']}[/cyan]")
            if fav_data['tech'] != "Unknown":
                console.print(f"    [bold red](!) Technology Detected:[/bold red] {fav_data['tech']}")
            if fav_data['related_hosts']:
                console.print(f"    [bold yellow][*] Related Hosts (via Shodan Index):[/bold yellow] {', '.join(fav_data['related_hosts'][:3])}")
            full_report['favicon'] = fav_data
        else:
            console.print("[dim][-] No favicon data found.[/dim]")

        # 3.2 ID Analytics
        id_engine = AnalyticsRecon(args.domain)
        with console.status("[bold purple]Analyzing Tracker IDs...[/bold purple]"):
            ids = id_engine.search_ids()
        
        if ids:
            console.print(f"\n[bold green][+] Detected Trackers:[/bold green]")
            for tech, data in ids.items():
                console.print(f"    - [cyan]{tech}:[/cyan] {', '.join(data['ids'])}")
                if data['related_domains']:
                    console.print(f"      [bold red](!) Shared with:[/bold red] {', '.join(data['related_domains'])}")
            full_report['analytics'] = ids
        else:
            console.print("[dim][-] No Analytics IDs found (clean or hidden).[/dim]")

        # 3.3 Wayback
        wb_engine = WaybackRecon(args.domain)
        with console.status("[bold purple]Time Traveling (Archive.org)...[/bold purple]"):
            secrets = wb_engine.find_secrets()
        
        if secrets:
            console.print(f"\n[bold red][!] Found {len(secrets)} historical sensitive files:[/bold red]")
            for url in secrets[:5]:
                console.print(f"    [dim]- {url}[/dim]")
            if len(secrets) > 5: console.print(f"    [dim]... and {len(secrets)-5} more.[/dim]")
            full_report['historical_secrets'] = secrets
        else:
            console.print("[dim][-] No sensitive historical files found in Archive.org.[/dim]")

    # PHASE 4: EMAIL
    if do_email:
        console.print(f"\n[bold yellow][*] Harvesting Emails (Bing/DDG)...[/bold yellow]")
        harvester = EmailHarvester(args.domain)
        with console.status(f"[bold green]Searching for employees...[/bold green]"):
            email_data = harvester.harvest()

        if "error" in email_data:
            console.print(f"[bold red][!] Error:[/bold red] {email_data['error']}")
        else:
            full_report['people'] = email_data
            console.print(f"   [dim]> Found {email_data['total_found']} addresses.[/dim]")
            if email_data['people']:
                console.print(f"   [bold cyan]> Pattern:[/bold cyan] {email_data['naming_convention']}")
                p_table = Table(title="Employee Intelligence", border_style="magenta", box=box.SIMPLE)
                p_table.add_column("Email Address", style="white")
                p_table.add_column("Type", style="dim")
                for email in email_data['people'][:10]:
                    p_table.add_row(email, "Employee")
                console.print(p_table)

    # PHASE 5: SAVE
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(full_report, f, indent=4)
            console.print(f"\n[bold blue][SAVE][/bold blue] Report saved: [underline]{args.output}[/underline]")
        except Exception as e:
            console.print(f"[bold red][ERROR][/bold red] Save failed: {e}")

if __name__ == "__main__":
    main()