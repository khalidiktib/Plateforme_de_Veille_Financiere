# collectors/bam/bam_collector.py
import re
import time
from datetime import datetime
from urllib.parse import quote, unquote, urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.bkam.ma"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9",
}

REQUEST_TIMEOUT = 20
REQUEST_DELAY = 0.5  # respecter le serveur
MAX_PAGES_PER_SECTION = 10  # garde-fou anti boucle infinie sur la pagination

# Scope "large" retenu avec Ky (25/08/2026) : principales sections
# publications du menu bkam.ma. Seule "Communiqués de presse politique
# monétaire" a été inspectée en détail et testée de bout en bout —
# les autres sont à valider au premier run (voir parse_listing : le
# scraper loggue et passe à la suite plutôt que de planter).
SEED_SECTIONS = [
    {"type_document": "communique_politique_monetaire",
     "url": "/Politique-monetaire/Cadre-strategique/Decision-de-la-politique-monetaire/Communiques-de-presse"},
    {"type_document": "rapport_politique_monetaire",
     "url": "/Publications-et-recherche/Documents-d-analyse/Rapport-sur-la-politique-monetaire"},
    {"type_document": "revue_conjoncture_economique",
     "url": "/Publications-et-recherche/Documents-d-analyse/Revue-de-la-conjoncture-economique"},
    {"type_document": "communique_stabilite_financiere",
     "url": "/Stabilite-financiere/Publications/Communiques-de-presse"},
    {"type_document": "rapport_annuel_stabilite_financiere",
     "url": "/Stabilite-financiere/Publications/Rapport-annuel-sur-la-stabilite-financiere"},
    {"type_document": "fiche_technique_stabilite_financiere",
     "url": "/Stabilite-financiere/Publications/Fiche-technique-sur-la-stabilite-financiere"},
    {"type_document": "rapport_annuel_roi",
     "url": "/Publications-et-recherche/Publications-institutionnelles/Rapport-annuel-presente-a-sm-le-roi"},
    {"type_document": "rapport_annuel_supervision_bancaire",
     "url": "/Publications-et-recherche/Publications-institutionnelles/Rapport-annuel-sur-la-supervision-bancaire"},
    {"type_document": "rapport_annuel_inclusion_financiere",
     "url": "/Publications-et-recherche/Publications-institutionnelles/Rapport-annuel-sur-l-inclusion-financiere"},
    {"type_document": "rapport_annuel_infrastructures_marches",
     "url": "/Publications-et-recherche/Publications-institutionnelles/Rapport-annuel-sur-les-infrastructures-des-marches-financiers-et-les-moyens-de-paiement-et-leur-surveillance"},
    {"type_document": "catalogue_publications",
     "url": "/Publications-et-recherche/Catalogue-des-publications"},
    {"type_document": "lettre_recherche",
     "url": "/Publications-et-recherche/Recherche2/La-lettre-de-la-recherche"},
    *[
        {"type_document": "document_travail_recherche",
         "url": f"/Publications-et-recherche/Recherche2/Documents-de-travail/{annee}"}
        for annee in range(2016, 2027)
    ],
    {"type_document": "stats_circulation_monnaie_fiduciaire",
     "url": "/Systemes-et-moyens-de-paiement/Publications/Statistiques-de-la-circulation-de-la-monnaie-fiduciaire"},
    {"type_document": "stats_moyens_paiement_scripturaux",
     "url": "/Systemes-et-moyens-de-paiement/Publications/Statistiques-des-moyens-de-paiement-scripturaux"},
    {"type_document": "revue_statistiques_monetaires",
     "url": "/Statistiques/Statistiques-monetaires/Revue-statistiques-monetaires"},
    {"type_document": "bulletin_trimestriel",
     "url": "/Statistiques/Chiffres-cles-de-l-economie-nationale/Bulletins-trimestriels"},
]

DATE_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")


def _parse_date(text_: str) -> str | None:
    """'Mis(e) en ligne :  23/06/2026' -> date ISO '2026-06-23'."""
    m = DATE_RE.search(text_)
    if not m:
        return None
    d, mo, y = m.groups()
    try:
        return datetime(int(y), int(mo), int(d)).date().isoformat()
    except ValueError:
        return None


def normalize_pdf_url(url: str) -> str:
    """Percent-encode le nom de fichier (bkam met parfois des espaces littéraux)."""
    if " " not in url and "%20" in url:
        return url
    parts = url.rsplit("/", 1)
    if len(parts) == 2:
        path, filename = parts
        return f"{path}/{quote(filename)}"
    return quote(url, safe="/:?=&")


def fetch_html(url: str) -> str | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        time.sleep(REQUEST_DELAY)
        return r.text
    except requests.RequestException as e:
        print(f"  Erreur réseau (page) : {e}")
        return None


def telecharger_pdf(url: str) -> bytes | None:
    """Même interface que bourse_collector.telecharger_pdf : bytes ou None."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if r.status_code == 200:
            content_type = r.headers.get("Content-Type", "")
            if "pdf" in content_type or len(r.content) > 1000:
                time.sleep(REQUEST_DELAY)
                return r.content
        return None
    except requests.RequestException as e:
        print(f"  Erreur réseau (pdf) : {e}")
        return None


def parse_listing(html: str, listing_url: str) -> list[dict]:
    """
    Retourne [{"titre", "date_publication", "article_url"|"pdf_url"}].
    Pattern confirmé : h5 titre + span.date-pos + a.link "Lire la suite".
    Repli 1 : lien PDF direct sur le listing. Repli 2 : tout <a href=*.pdf>.
    """
    soup = BeautifulSoup(html, "html.parser")
    items = []

    for h5 in soup.select("h5"):
        titre = h5.get_text(strip=True)
        if not titre:
            continue
        container = h5.find_parent() or h5
        date_span = container.find("span", class_="date-pos")
        link = container.find("a", class_="link") or container.find("a")
        if link and link.get("href"):
            date_pub = _parse_date(date_span.get_text(strip=True)) if date_span else None
            items.append({
                "titre": titre,
                "date_publication": date_pub,
                "article_url": urljoin(BASE_URL, link["href"]),
            })
    if items:
        return items

    for a in soup.select("a.link-pdf, a.pdf"):
        href = a.get("href")
        if href and href.lower().endswith(".pdf"):
            items.append({
                "titre": a.get_text(strip=True) or href.rsplit("/", 1)[-1],
                "date_publication": None,
                "pdf_url": urljoin(BASE_URL, href),
            })
    if items:
        return items

    for a in soup.select("a[href$='.pdf'], a[href*='.pdf']"):
        href = a.get("href")
        if not href:
            continue
        items.append({
            "titre": a.get_text(strip=True) or href.rsplit("/", 1)[-1],
            "date_publication": None,
            "pdf_url": urljoin(BASE_URL, href),
        })

    if not items:
        print(f"  ⚠ Aucun item trouvé sur {listing_url} (pattern inconnu)")
    return items


def find_next_page(html: str, current_url: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    candidate = (
        soup.select_one("a[rel='next']")
        or soup.select_one("a.next")
        or soup.select_one("a.pager-next")
    )
    if candidate is None:
        for a in soup.select("a"):
            if a.get_text(strip=True).lower() in ("suivant", "next", ">"):
                candidate = a
                break
    if candidate and candidate.get("href"):
        next_url = urljoin(BASE_URL, candidate["href"])
        if next_url != current_url:
            return next_url
    return None


def parse_detail_page(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    link = soup.select_one("a.link-pdf") or soup.select_one("a.pdf") or soup.select_one("a[href$='.pdf']")
    if link and link.get("href"):
        return urljoin(BASE_URL, link["href"])
    return None


def collecter_section(section: dict, limite: int | None = None) -> list[dict]:
    """
    Parcourt une section (avec pagination) et retourne une liste de dicts
    {url, type_document, titre, date_publication, contenu_pdf} — même
    forme que ce que renvoie bourse_collector.collecter_periode().
    """
    resultats = []
    url = BASE_URL + section["url"]
    seen_urls = set()

    for _ in range(MAX_PAGES_PER_SECTION):
        if url in seen_urls:
            break
        seen_urls.add(url)

        html = fetch_html(url)
        if html is None:
            break

        items = parse_listing(html, url)
        print(f"[{section['type_document']}] {len(items)} item(s) sur {url}")

        for item in items:
            pdf_url = item.get("pdf_url")
            article_url = item.get("article_url") or pdf_url

            if not pdf_url:
                detail_html = fetch_html(article_url)
                if detail_html is None:
                    continue
                pdf_url = parse_detail_page(detail_html)
                if not pdf_url:
                    print(f"  ⚠ Pas de PDF trouvé sur : {article_url}")
                    continue

            pdf_url = normalize_pdf_url(pdf_url)
            print(f"  Essai : {unquote(pdf_url)[-50:]}", end=" ")
            contenu = telecharger_pdf(pdf_url)

            if contenu:
                print("✓")
                resultats.append({
                    "url": article_url,
                    "type_document": section["type_document"],
                    "titre": item["titre"],
                    "date_publication": item.get("date_publication"),
                    "contenu_pdf": contenu,
                })
            else:
                print("✗ (absent)")

            if limite and len(resultats) >= limite:
                return resultats

        next_url = find_next_page(html, url)
        if not next_url:
            break
        url = next_url

    return resultats


def collecter_toutes_sections(limite_par_section: int | None = None) -> list[dict]:
    """Boucle sur SEED_SECTIONS, retourne tous les documents collectés."""
    resultats = []
    for section in SEED_SECTIONS:
        try:
            docs = collecter_section(section, limite=limite_par_section)
            resultats.extend(docs)
        except Exception as e:
            print(f"✗ Section {section['type_document']} en échec : {e}")

    print(f"\n→ {len(resultats)} PDFs collectés sur {len(SEED_SECTIONS)} sections")
    return resultats