import os
from pathlib import Path
from rich.console import Console

console = Console()

# Carica il file .env dalla root del progetto (se esiste)
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=_env_path, override=False)
    except ImportError:
        console.print(
            "[bold red][!] ATTENZIONE:[/bold red] 'python-dotenv' non trovato. "
            "Le API key nel .env NON vengono caricate.\n"
            "    Esegui: [bold]pip install python-dotenv[/bold] oppure attiva il virtualenv con "
            "[bold].venv\\Scripts\\Activate.ps1[/bold]"
        )
else:
    console.print(
        "[bold yellow][!] File .env non trovato.[/bold yellow] "
        "Copia [bold].env.example[/bold] in [bold].env[/bold] e inserisci le tue API key."
    )


def get_api_key(key_name: str) -> str | None:
    """Restituisce il valore della chiave API o None se non configurata."""
    value = os.environ.get(key_name, "").strip()
    return value if value else None


def require_api_key(key_name: str, module_name: str) -> str | None:
    """
    Restituisce la chiave API se presente.
    Stampa un warning rich e restituisce None se assente,
    cosi il modulo chiamante puo saltare l'esecuzione.
    """
    key = get_api_key(key_name)
    if not key:
        console.print(
            f"[dim]   [-] {module_name}: chiave [bold]{key_name}[/bold] non trovata in .env → modulo saltato.[/dim]"
        )
    return key
