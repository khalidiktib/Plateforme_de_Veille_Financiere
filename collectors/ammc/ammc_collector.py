import json
import re
import time
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, unquote

import pandas as pd
import requests
from bs4 import BeautifulSoup
from storage.repositories import inserer_document, hash_document

BASE_URL = "https://www.ammc.ma"
PUBLICATIONS_URL = "https://www.ammc.ma/fr/publications"
DAHIRS_URL = "https://www.ammc.ma/fr/reglementations/dahirs-lois"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def fetch_page(url: str) -> str:
    """Télécharge le HTML d'une page."""
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.text


def clean_text(text: str | None) -> str | None:
    """Nettoie un texte simple (espaces, retours ligne)."""
    if not text:
        return None
    return " ".join(text.split()).strip()


def clean_pdf_title(raw_title: str | None) -> str:
    if not raw_title:
        return "Titre non trouvé"

    title = unquote(raw_title).strip()
    title = re.sub(r"\.pdf$", "", title, flags=re.IGNORECASE)

    # suffixe technique Drupal (doublon de nom de fichier) : "_0", "_1"...
    # UNE seule fois, 1-2 chiffres max, pour ne pas manger une année (4 chiffres)
    title = re.sub(r"_\d{1,2}$", "", title)

    title = title.replace("_", " ")
    title = re.sub(r"(?<=[a-zà-ÿ])(?=[A-ZÀ-Ÿ])", " ", title)
    title = re.sub(r"(?i)\brapport\s*profil\b", "Rapport profil", title)
    title = re.sub(r"(?i)\bde\s*bonne\b", "de bonne", title)

    for token in ["VFR", "VF", "VA", "WEB"]:
        title = re.sub(rf"\b{token}\b", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\bV\d{3,5}\b", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\bFR\b$", "", title, flags=re.IGNORECASE)

    title = re.sub(r"\s*-\s*", " ", title)
    title = re.sub(r"\s+", " ", title).strip()
    title = re.sub(r"\bt\s*([1-4])\b", r"T\1", title, flags=re.IGNORECASE)

    title = title.lower().title()
    replacements = {
        "Opcvm": "OPCVM", "Opci": "OPCI", "Opcc": "OPCC",
        "Pea": "PEA", "Ape": "APE", "Rmc": "RMC", "Rie": "RIE",
    }
    for wrong, correct in replacements.items():
        title = title.replace(wrong, correct)

    return title.strip() if title.strip() else "Titre non trouvé"


def extract_date_from_title(title: str) -> str | None:
    """
    Tente d'extraire une date de publication depuis le titre nettoyé.
    Retourne une string ISO (YYYY-MM-DD) ou None si rien de fiable trouvé.

    Note : ceci reste une approximation basée sur le nom du fichier
    (ex: "T1 26" -> 1er jour du trimestre), pas une date exacte de publication.
    """
    # cas "RMC N13 29 12 2025" -> jour mois année explicites
    m = re.search(r"\b(\d{1,2})\s+(\d{1,2})\s+(20\d{2})\b", title)
    if m:
        jour, mois, annee = map(int, m.groups())
        try:
            return date(annee, mois, jour).isoformat()
        except ValueError:
            pass  # jour/mois invalides, on continue vers les autres cas

    # cas "T1 26" ou "T4 25" -> trimestre + année sur 2 chiffres
    m = re.search(r"\bT([1-4])\s+(\d{2})\b", title)
    if m:
        trimestre, annee_courte = int(m.group(1)), int(m.group(2))
        annee = 2000 + annee_courte
        mois = {1: 1, 2: 4, 3: 7, 4: 10}[trimestre]
        return date(annee, mois, 1).isoformat()

    # cas "T3 2025" -> trimestre + année sur 4 chiffres
    m = re.search(r"\bT([1-4])\s+(20\d{2})\b", title)
    if m:
        trimestre, annee = int(m.group(1)), int(m.group(2))
        mois = {1: 1, 2: 4, 3: 7, 4: 10}[trimestre]
        return date(annee, mois, 1).isoformat()

    # cas année seule -> "2025", "2024"
    m = re.search(r"\b(20\d{2})\b", title)
    if m:
        return date(int(m.group(1)), 1, 1).isoformat()

    return None


def deduplicate_documents(documents: list[dict]) -> list[dict]:
    """Supprime les doublons à partir du document_url."""
    seen = set()
    unique_docs = []

    for doc in documents:
        key = doc.get("document_url")
        if key and key not in seen:
            seen.add(key)
            unique_docs.append(doc)

    return unique_docs


def extract_pdf_links(html: str) -> list:
    """
    Extrait tous les liens PDF d'une page.
    Pour le MVP, on s'appuie sur les liens PDF présents dans la page.
    """
    soup = BeautifulSoup(html, "lxml")
    links = soup.find_all("a", href=True)

    pdf_links = []
    for link in links:
        href = link.get("href", "")
        if ".pdf" in href.lower():
            pdf_links.append(link)

    return pdf_links


def get_last_page_number(html: str) -> int:
    """
    Cherche tous les liens de pagination (?page=N) sur la page et
    retourne le plus grand numéro trouvé. Retourne 0 si pas de
    pagination détectée (ex: une seule page de résultats).

    On prend le max sur TOUS les liens page=N plutôt que de chercher
    un lien précis "Dernière page" par son texte, car ce texte est
    souvent réparti sur plusieurs éléments imbriqués dans le HTML
    (icônes, texte d'accessibilité caché), ce qui rend une recherche
    par texte exact peu fiable.

    On lit ce numéro directement depuis le site plutôt que de le coder
    en dur, et on évite une boucle "jusqu'à page vide", car AMMC ne
    renvoie jamais de page vide au-delà de la dernière : toute page
    hors limites est automatiquement redirigée (clampée) vers la
    dernière page réelle, qui contient toujours des documents. Une
    boucle "jusqu'à vide" tournerait donc indéfiniment sur ce site.
    """
    soup = BeautifulSoup(html, "lxml")
    page_numbers = []
    for a in soup.find_all("a", href=True):
        m = re.search(r"[?&]page=(\d+)", a["href"])
        if m:
            page_numbers.append(int(m.group(1)))
    return max(page_numbers) if page_numbers else 0


def collect_all_pages(base_url: str, parser) -> list[dict]:
    """
    Récupère tous les documents en parcourant toutes les pages d'une
    section AMMC, en se basant sur le vrai nombre de pages annoncé par
    le site (voir get_last_page_number).
    """
    first_html = fetch_page(base_url)
    documents = parser(first_html)

    last_page = get_last_page_number(first_html)
    print(f"{last_page + 1} pages détectées")

    for page in range(1, last_page + 1):
        print(f"  page {page}/{last_page}")
        time.sleep(0.5)  # rester correct vis-à-vis du serveur AMMC
        html = fetch_page(f"{base_url}?page={page}")
        documents.extend(parser(html))

    return deduplicate_documents(documents)


def parse_publications(html: str) -> list[dict]:
    """Parse la page Publications AMMC."""
    documents = []
    pdf_links = extract_pdf_links(html)

    for link in pdf_links:
        href = link.get("href")
        text = clean_text(link.get_text(separator=" "))

        if not href:
            continue

        document_url = urljoin(BASE_URL, href)

        # si le texte visible est vide, on prend le nom du fichier depuis l'URL
        raw_title = text if text else href.split("/")[-1]
        clean_title = clean_pdf_title(raw_title)

        documents.append({
            "source": "AMMC",
            "rubrique": "publications",
            "type_document": "publication",
            "title": clean_title,
            "date_publication": extract_date_from_title(clean_title),
            "page_url": PUBLICATIONS_URL,
            "document_url": document_url
        })

    return deduplicate_documents(documents)


def parse_dahirs_lois(html: str) -> list[dict]:
    """Parse la page Dahirs et lois AMMC."""
    documents = []
    pdf_links = extract_pdf_links(html)

    for link in pdf_links:
        href = link.get("href")
        text = clean_text(link.get_text(separator=" "))

        if not href:
            continue

        document_url = urljoin(BASE_URL, href)

        raw_title = text if text else href.split("/")[-1]
        clean_title = clean_pdf_title(raw_title)

        documents.append({
            "source": "AMMC",
            "rubrique": "dahirs_lois",
            "type_document": "texte_reglementaire",
            "title": clean_title,
            "date_publication": extract_date_from_title(clean_title),
            "page_url": DAHIRS_URL,
            "document_url": document_url
        })

    return deduplicate_documents(documents)


def collect_ammc_documents():
    """Collecte les documents AMMC depuis Publications + Dahirs/Lois, toutes pages confondues."""
    print("Scraping Publications...")
    publications_docs = collect_all_pages(PUBLICATIONS_URL, parse_publications)
    print(f"{len(publications_docs)} publications trouvées")

    print("Scraping Dahirs et lois...")
    dahirs_docs = collect_all_pages(DAHIRS_URL, parse_dahirs_lois)
    print(f"{len(dahirs_docs)} textes réglementaires trouvés")

    all_docs = deduplicate_documents(publications_docs + dahirs_docs)

    return publications_docs, dahirs_docs, all_docs


def save_results(publications_docs, dahirs_docs, all_docs):
    """Sauvegarde les résultats en JSON + CSV."""
    Path("data/raw").mkdir(parents=True, exist_ok=True)
    Path("data/processed").mkdir(parents=True, exist_ok=True)

    pd.DataFrame(publications_docs).to_json(
        "data/raw/ammc_publications.json",
        orient="records",
        force_ascii=False,
        indent=2
    )

    pd.DataFrame(dahirs_docs).to_json(
        "data/raw/ammc_dahirs_lois.json",
        orient="records",
        force_ascii=False,
        indent=2
    )

    pd.DataFrame(all_docs).to_json(
        "data/processed/ammc_documents.json",
        orient="records",
        force_ascii=False,
        indent=2
    )

    pd.DataFrame(all_docs).to_csv(
        "data/processed/ammc_documents.csv",
        index=False,
        encoding="utf-8-sig"
    )

    print("Fichiers sauvegardés dans data/raw et data/processed")


def debug_page_structure(html: str, page_name: str, max_blocks: int = 10):
    """
    Debug : affiche les premiers liens PDF et leur parent HTML.
    À utiliser seulement si tu veux inspecter la structure d'une page.
    """
    soup = BeautifulSoup(html, "lxml")

    print(f"\n========== DEBUG {page_name} ==========")

    links = soup.find_all("a", href=True)
    pdf_links = [a for a in links if ".pdf" in a.get("href", "").lower()]

    print(f"Nombre total de liens PDF trouvés : {len(pdf_links)}")

    for i, link in enumerate(pdf_links[:max_blocks], start=1):
        text = clean_text(link.get_text())
        href = link.get("href")

        print(f"\n--- PDF {i} ---")
        print("TEXT:", text)
        print("HREF:", href)

        parent = link.parent
        if parent:
            print("PARENT TAG:", parent.name)
            print("PARENT HTML:")
            print(parent.prettify()[:1500])


def transform_for_db(doc: dict) -> dict:
    """
    Transforme un document collecté AMMC vers le schéma de la table documents.
    """
    return {
        "source": doc["source"],
        "type_document": doc["type_document"],
        "titre": doc["title"],
        "url_source": doc["document_url"],   # lien du PDF
        "date_publication": doc["date_publication"],
        "langue": "fr",
        "texte_nettoye": None,   # pas encore extrait à cette étape
        "hash": hash_document(doc["source"], doc["document_url"]),
        "metadata": json.dumps({
            "rubrique": doc["rubrique"],
            "page_url": doc["page_url"],
            "document_url": doc["document_url"]
        })
    }


def save_to_database(all_docs: list[dict]):
    """
    Insère les documents AMMC dans PostgreSQL.
    """
    inserted = 0
    skipped = 0

    for doc in all_docs:
        db_doc = transform_for_db(doc)
        ok = inserer_document(db_doc)

        if ok:
            inserted += 1
        else:
            skipped += 1

    print(f"{inserted} documents insérés en base")
    print(f"{skipped} documents ignorés (déjà existants)")


if __name__ == "__main__":
    publications_docs, dahirs_docs, all_docs = collect_ammc_documents()

    # Sauvegarde fichiers JSON / CSV
    save_results(publications_docs, dahirs_docs, all_docs)

    # Insertion PostgreSQL
    save_to_database(all_docs)

    print("\nAperçu des 10 premiers documents :")
    for doc in all_docs[:10]:
        print(doc)