# cleaners/http_date_extractor.py
import requests
from datetime import datetime

def extraire_date_last_modified(url: str, headers: dict) -> str | None:
    """
    Récupère la date Last-Modified depuis les headers HTTP du fichier.
    Retourne une date ISO ou None si absente/invalide.
    """
    try:
        response = requests.head(url, headers=headers, timeout=10)
        last_mod = response.headers.get("Last-Modified")
        if not last_mod:
            return None
        dt = datetime.strptime(last_mod, "%a, %d %b %Y %H:%M:%S %Z")
        return dt.date().isoformat()
    except Exception:
        return None