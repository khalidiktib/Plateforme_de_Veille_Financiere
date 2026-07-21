import re
from datetime import date

MOIS_FR = {
    "janvier": 1, "février": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "août": 8,
    "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12
}

def extraire_date_depuis_texte(texte: str) -> str | None:
    """
    Cherche une date dans les 500 premiers caractères du texte
    (souvent l'en-tête du document contient la date d'émission).
    Retourne une string ISO ou None si rien de fiable trouvé.
    """
    if not texte:
        return None

    debut = texte[:500].lower()

    # Format "13 juillet 2026"
    m = re.search(
        r"\b(\d{1,2})\s+(" + "|".join(MOIS_FR.keys()) + r")\s+(20\d{2})\b",
        debut
    )
    if m:
        jour, mois_nom, annee = m.groups()
        try:
            return date(int(annee), MOIS_FR[mois_nom], int(jour)).isoformat()
        except ValueError:
            pass

    # Format "13/07/2026" ou "13-07-2026"
    m = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](20\d{2})\b", debut)
    if m:
        jour, mois, annee = map(int, m.groups())
        try:
            return date(annee, mois, jour).isoformat()
        except ValueError:
            pass

    return None