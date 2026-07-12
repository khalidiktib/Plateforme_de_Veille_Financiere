# collectors/bourse/bourse_collector.py
import requests
import time
from datetime import datetime, timedelta
from pathlib import Path
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning) #Fixer le warning SSL 


BASE_MEDIA_URL = "https://media.casablanca-bourse.com/sites/default/files"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36"
}

def generer_urls_par_date(date: datetime) -> list[dict]:
    """
    Génère toutes les URLs possibles pour une date donnée.
    On essaie de télécharger chaque URL — si 404, la publication
    n'existe pas pour cette date (jour férié, week-end).
    """
    date_str = date.strftime("%Y%m%d")
    year_month = date.strftime("%Y-%m")

    return [
        {
            "url": f"{BASE_MEDIA_URL}/es-auto-upload/fr/"
                   f"resume_seance_{date_str}.pdf",
            "type_document": "resume_seance",
            "titre": f"Résumé de séance du {date.strftime('%d/%m/%Y')}"
        },
        {
            "url": f"{BASE_MEDIA_URL}/es-auto-upload/fr/"
                   f"Instructions_{date_str}.pdf",
            "type_document": "bulletin_cote",
            "titre": f"Bulletin de la cote du {date.strftime('%d/%m/%Y')}"
        }
    ]

def telecharger_pdf(url: str) -> bytes | None:
    """
    Télécharge un PDF depuis une URL.
    Retourne None si 404 (publication inexistante pour cette date).
    """
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=30,
            verify=False #LIGNE pour ignorer l'erreur SSL
        )
        if response.status_code == 200:
            content_type = response.headers.get("Content-Type", "")
            if "pdf" in content_type or len(response.content) > 1000:
                return response.content
        return None
    except requests.RequestException as e:
        print(f"  Erreur réseau : {e}")
        return None

def collecter_periode(nb_jours: int = 30) -> list[dict]:
    """
    Collecte tous les PDFs disponibles sur les nb_jours derniers jours.
    Retourne une liste de dicts {url, type_document, titre, contenu_pdf}
    """
    resultats = []
    aujourd_hui = datetime.now()

    for i in range(nb_jours):
        date = aujourd_hui - timedelta(days=i)

        # Ignorer week-ends
        if date.weekday() >= 5:
            continue

        urls = generer_urls_par_date(date)

        for item in urls:
            print(f"  Essai : {item['url'][-40:]}", end=" ")
            contenu = telecharger_pdf(item["url"])

            if contenu:
                print("✓")
                resultats.append({
                    **item,
                    "contenu_pdf": contenu,
                    "date_publication": date.date()
                })
            else:
                print("✗ (absent)")

            time.sleep(0.5)  # Respecter le serveur

    print(f"\n→ {len(resultats)} PDFs collectés sur {nb_jours} jours")
    return resultats