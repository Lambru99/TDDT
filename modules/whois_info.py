import subprocess
import shutil

class WhoisRecon:
    def __init__(self, domain):
        self.domain = domain

    def get_raw_whois(self):

        if not shutil.which("whois"):
            return None, "CRITICAL: 'whois' command not found."

        try:
            result = subprocess.run(
                ['whois', self.domain], 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            

            if result.returncode != 0 and not result.stdout:
                return None, f"Error whois: {result.stderr.strip()}"
                
            return result.stdout, None

        except subprocess.TimeoutExpired:
            return None, "Error: whois timeout."
        except Exception as e:
            return None, str(e)