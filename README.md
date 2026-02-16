# TDDT
A modular, Python-based External Attack Surface Management (EASM) tool designed for corporate reconnaissance and OSINT.

This tool automates the gathering of intelligence on target domains, combining Passive OSINT (safe, legal, no-touch) with Active Reconnaissance capabilities. It features a beautiful terminal interface powered by the rich library.

## ⚠️ Legal Disclaimer

Usage of this tool for attacking targets without prior mutual consent is illegal.
It is the end user's responsibility to obey all applicable local, state, and federal laws. Developers assume no liability and are not responsible for any misuse or damage caused by this program.

* Use the `−l` (`−−light`) flag for purely passive OSINT research (safe mode).

* Active Mode (default) interacts with the target infrastructure (Port Scanning, etc.) and should only be used on assets you own or have explicit permission to test.

## ✨ Features

* 🕵️ Identity Recon: WHOIS data retrieval (Registrar, Admin, Tech contacts).

* 🌐 Subdomain Enumeration: Aggregates data from crt.sh and HackerTarget. Includes fallback logic if APIs are down.

* 📡 Port Scanning:

    *   Active: TCP Connect scan (requires authorization).

    * Passive: Historical port data via InternetDB/Shodan (safe).

* 📧 Email Harvesting: Scrapes Search Engines (Bing, DuckDuckGo) to find employee emails and infer naming conventions (e.g., name.surname@company.com).

* 🧠 Deep OSINT:

    * Favicon Hash: Fingerprints the website icon to find hidden assets on Shodan.

    * ID Analytics: Reverse search on Google Analytics/AdSense IDs to find correlated domains.

    * Wayback Machine: Time travels to find deleted secrets (.env, .sql, .bak files).

* 💾 JSON Export: Saves full reports for further analysis.

## 📦 Installation

This project is built with Python 3. It is recommended to use a Virtual Environment to manage dependencies.
1. Clone the Repository

```bash
git clone https://github.com/Lambru99/TDDT.git
cd TDDT
```
2. Create a Virtual Environment

Linux / macOS:
```bash
python3 -m venv venv
source venv/bin/activate
```

Windows:
```bash
python -m venv venv
.\venv\Scripts\activate
```
3. Install Dependencies

```bash
pip install -r requirements.txt
```

## 🚀 Usage

Run the tool by supplying the target domain.
Basic Command (Full/Active Mode)

```bash
python main.py example.com
```
Passive Mode (Safe / Light)

Recommended for initial OSINT without touching the target's ports.
```bash
python main.py example.com --light
```
Command Line Arguments

| Flag            | Description                                                                         |
|-----------------|-------------------------------------------------------------------------------------|
| domain          | The target domain (e.g., example.com).                                              |
| −h, −−help      | Show the advanced help menu.                                                        |
| −l, −−light     | PASSIVE MODE. Disables active port scanning. Includes Whois, Email, and Deep OSINT. |
| −d, −−deep      | Run Deep OSINT modules (Favicon hashing, ID Analytics, Wayback History).            |
| −e, −−email     | Run People/Email harvesting only.                                                   |
| −w, −−whois     | Run only WHOIS identity check.                                                      |
| −r, −−recon     | Run only Infrastructure Recon (Subdomains + Ports).                                 |
| "−o output.json | Save the final report to a JSON file.                                               |

## 🧩 How to Add New Modules

This tool is designed to be modular. All logic resides in the modules/ folder, orchestrated by main.py.
Step 1: Create the Module

Create a new Python file in the modules/ directory (e.g., modules/myn​ews​canner.py).
Define a class that performs a specific task.

```python
modules/my_new_scanner.py

import requests

class MyNewScanner:
def init(self, domain):
self.domain = domain

def run(self):
    # Your logic here
    return {"result": f"Scanned {self.domain}"}

```
Step 2: Import in Main

Open main.py and import your new class at the top.

```python
main.py

from modules.my_new_scanner import MyNewScanner
```
Step 3: Integrate Logic

Scroll down to the execution flow in main.py (e.g., create a new Phase or add to an existing one) and initialize your class.

```python
# Inside main() function...

# PHASE X: CUSTOM SCAN
print("Running custom scan...")
my_scanner = MyNewScanner(args.domain)
result = my_scanner.run()

# Add to report
full_report['custom_scan'] = result

# Print to console (using rich)
console.print(result)

```

## 🛠️ Technology Stack & Libraries

This project is Open Source (FOSS) and leverages the following powerful Python libraries:

*    Rich: For the beautiful terminal UI, tables, and progress bars.

*    Requests: For handling HTTP requests to APIs and Targets.

*    BeautifulSoup4: For HTML parsing (Email scraping, Title extraction).

*    DNSPython: For DNS resolution and verification.

*    mmh3: For MurmurHash3 calculation (Favicon fingerprinting).

## 📄 License

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.


Happy Hacking! 🕵️‍♂️

