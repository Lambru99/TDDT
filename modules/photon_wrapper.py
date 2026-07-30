import subprocess
import shutil
import tempfile
import os
from rich.console import Console
from modules.config import get_api_key

console = Console()


class PhotonRunner:
    def __init__(self, domain):
        self.domain = domain
        self.target_url = f"https://{domain}"

    def _find_photon_exec(self) -> list | None:
        """
        Cerca come invocare Photon:
        1. Se l'utente ha PHOTON_PATH nel .env (es. /usr/share/photon/photon.py)
        2. Se 'photon' è presente direttamente in PATH
        3. Se 'photon.py' è in PATH o nella directory corrente
        """
        env_path = get_api_key("PHOTON_PATH")
        if env_path and os.path.exists(env_path):
            return ["python3", env_path]
        
        if shutil.which("photon"):
            return ["photon"]
            
        if shutil.which("photon.py"):
            return ["photon.py"]
            
        return None

    def run(self) -> dict:
        """
        Esegue Photon con profondità 3, 10 thread, ricerca chiavi e supporto wayback.
        Parsa rigorosamente TUTTI i file di output generati (internal, external, scripts, ecc.).
        """
        cmd_prefix = self._find_photon_exec()
        if not cmd_prefix:
            return {
                "error": "Comando 'photon' non trovato in PATH e PHOTON_PATH non impostato in .env.",
                "installed": False
            }

        temp_dir = tempfile.mkdtemp(prefix="tddt_photon_")
        output_folder = os.path.join(temp_dir, "out")

        command = cmd_prefix + [
            "-u", self.target_url,
            "-l", "3",        # Aumentato a livello 3 per un crawling più approfondito
            "-t", "10",       # 10 thread simultanei per velocizzare la scansione
            "--keys",         # Estrae chiavi API e segreti dal codice
            "--wayback",      # Usa Wayback Machine come sorgente seed di URL storici
            "-o", output_folder
        ]

        try:
            console.print(f"[dim]   [!] Esecuzione comando: {' '.join(command)}[/dim]")
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=180  # Timeout di 3 minuti per dare tempo al livello 3 e wayback
            )

            if result.returncode != 0 and not os.path.exists(output_folder):
                return {
                    "error": f"Errore durante l'esecuzione di Photon: {result.stderr.strip()}",
                    "installed": True
                }

            # I veri nomi dei file che Photon crea nel proprio folder di output
            photon_files = [
                "internal.txt",   # URL interni del target
                "external.txt",   # URL o sottodomini esterni citati
                "scripts.txt",    # File Javascript trovati (.js)
                "fuzzable.txt",   # URL che accettano parametri GET (?id=1) utilissimi per attacchi
                "endpoints.txt",  # API o rotte endpoint sottratte
                "keys.txt",       # Chiavi e token estratti con regex
                "intel.txt",      # Email, social accounts, analytics ID
                "files.txt"       # Documenti (.pdf, .xml, .txt, ecc.)
            ]

            findings = {
                "installed": True,
                "command_run": " ".join(command),
            }
            # Inizializziamo tutte le liste vuote
            for fname in photon_files:
                findings[fname.replace(".txt", "")] = []

            if os.path.exists(output_folder):
                for fname in photon_files:
                    fpath = os.path.join(output_folder, fname)
                    if os.path.exists(fpath):
                        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                            lines = [l.strip() for l in f.readlines() if l.strip()]
                            key_name = fname.replace(".txt", "")
                            findings[key_name] = lines

            return findings

        except subprocess.TimeoutExpired:
            return {"error": "Timeout: l'esecuzione di Photon ha superato i 180 secondi.", "installed": True}
        except Exception as e:
            return {"error": str(e), "installed": True}
        finally:
            # Pulizia della cartella temporanea di Photon
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass
