import requests
import socket

class VulnScanner:
    def __init__(self):
        self.api_url = "https://internetdb.shodan.io/{}"
        
        self.critical_ports = {
            21: "FTP", 22: "SSH", 23: "Telnet", 80: "HTTP", 443: "HTTPS",
            3389: "RDP", 5900: "VNC", 3306: "MySQL", 5432: "PostgreSQL",
            8080: "HTTP-Alt", 8443: "HTTPS-Alt", 27017: "MongoDB"
        }

    def _check_port_socket(self, ip, port):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.5)
            result = s.connect_ex((ip, int(port)))
            s.close()
            return result == 0
        except Exception:
            return False

    def scan_ip(self, ip, passive_only=False):
        try:
            # Passive Recon (InternetDB)
            response = requests.get(self.api_url.format(ip), timeout=5)
            
            if response.status_code != 200:
                return {"ports": [], "cves": [], "tags": [], "hostnames": []}

            data = response.json()
            potential_ports = data.get('ports', [])
            
            # Active Verification
            verified_ports = []
            
            if passive_only:
                verified_ports = potential_ports
            else:
                if len(potential_ports) < 100:
                    for port in potential_ports:
                        if self._check_port_socket(ip, port):
                            verified_ports.append(port)
                else:
                    verified_ports = potential_ports

            return {
                "ports": verified_ports,       
                "cves": data.get('vulns', []), 
                "tags": data.get('tags', []),
                "hostnames": data.get('hostnames', [])
            }

        except Exception:
            return {"error": "Connection Failed"}

    def is_critical(self, ports):
        found_critical = []
        for p in ports:
            if p in self.critical_ports:
                found_critical.append(f"{p}({self.critical_ports[p]})")
        return found_critical