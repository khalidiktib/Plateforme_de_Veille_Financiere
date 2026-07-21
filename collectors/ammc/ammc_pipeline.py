"""
ammc_pipeline.py

Pipeline complet pour la source AMMC :
Collecte -> Insertion des métadonnées -> Extraction du texte des PDF
-> Nettoyage -> Mise à jour en base.

Le pipeline est volontairement découpé en DEUX étapes indépendantes :

1. collecter_metadonnees()
   Scrape les pages Publications / Dahirs et lois (avec pagination),
   sauvegarde en JSON/CSV, et insère les nouveaux documents en base
   (texte_nettoye vide à ce stade). Rapide, pas de téléchargement PDF.

2. enrichir_textes()
   Va chercher en base tous les documents dont texte_nettoye est
   encore NULL (peu importe quand ils ont été insérés), télécharge
   chaque PDF en mémoire (aucun fichier écrit sur disque), en extrait
   le texte, le nettoie, détecte la langue, et met à jour la ligne.

Ce découpage est nécessaire car l'insertion utilise
"ON CONFLICT (hash) DO NOTHING" : réinsérer un document déjà présent
en base ne mettrait jamais à jour son texte. Il faut donc un vrai
UPDATE séparé (voir get_documents_sans_texte / mettre_a_jour_texte
dans storage.repositories).

Ce découpage a aussi l'avantage d'être reprenable : si l'extraction
plante à mi-parcours (certains PDF AMMC dépassent 15 Mo), on peut
relancer enrichir_textes() sans dupliquer le travail déjà fait.
"""

import io
import time

import requests

from cleaners.date_extractor import extraire_date_depuis_texte
from cleaners.text_cleaner import detecter_langue, nettoyer_texte, tronquer_texte
from cleaners.http_date_extractor import extraire_date_last_modified
from collectors.ammc.ammc_collector import HEADERS, collect_ammc_documents, save_results, transform_for_db
from extractors.pdf_extractor import extraire_texte_pdf
from storage.repositories import (
    get_documents_sans_texte, 
    inserer_document, 
    mettre_a_jour_texte_et_date  # ← nouveau, remplace mettre_a_jour_texte
)


TAILLE_MAX_PDF = 30 * 1024 * 1024  # 30 Mo au lieu de 20


def telecharger_pdf_en_memoire(url: str) -> io.BytesIO | None:
    """
    Télécharge un PDF en mémoire (aucun fichier écrit sur disque) et le
    retourne sous forme de BytesIO, directement utilisable par
    pdfplumber.open(). Retourne None si le téléchargement échoue ou si
    le fichier dépasse TAILLE_MAX_PDF.
    """
    response = requests.get(url, headers=HEADERS, timeout=60, stream=True)
    response.raise_for_status()

    taille_annoncee = response.headers.get("Content-Length")
    if taille_annoncee and int(taille_annoncee) > TAILLE_MAX_PDF:
        print(f"    ! PDF trop volumineux ({int(taille_annoncee) / 1_000_000:.1f} Mo), ignoré")
        return None

    return io.BytesIO(response.content)


def collecter_metadonnees():
    """Étape 1 : scraping + insertion des métadonnées (sans texte)."""
    print("=== Collecte des métadonnées AMMC ===")
    publications_docs, dahirs_docs, all_docs = collect_ammc_documents()
    save_results(publications_docs, dahirs_docs, all_docs)

    inserted = 0
    skipped = 0
    for doc in all_docs:
        db_doc = transform_for_db(doc)
        if inserer_document(db_doc):
            inserted += 1
        else:
            skipped += 1

    print(f"{inserted} nouveaux documents insérés")
    print(f"{skipped} documents déjà existants (ignorés)")
    return inserted, skipped


def enrichir_textes(limite: int = 500, pause: float = 1.0):
    """
    Étape 2 : backfill du texte pour tous les documents AMMC en base
    dont texte_nettoye est encore NULL.
    """
    a_traiter = get_documents_sans_texte(source="AMMC", limite=limite)
    print(f"\n=== Extraction du texte pour {len(a_traiter)} documents AMMC sans texte ===")

    mis_a_jour = 0
    vides = 0
    erreurs = 0

    for i, row in enumerate(a_traiter, start=1):
        doc_id, url_source, source = row
        print(f"  [{i}/{len(a_traiter)}] doc #{doc_id} : {url_source}")

        try:
            pdf_en_memoire = telecharger_pdf_en_memoire(url_source)
        except Exception as e:
            print(f"    ! erreur téléchargement : {e}")
            erreurs += 1
            time.sleep(pause)
            continue

        if pdf_en_memoire is None:
            vides += 1
            time.sleep(pause)
            continue

        try:
            texte_brut = extraire_texte_pdf(pdf_en_memoire)
        except Exception as e:
            print(f"    ! erreur extraction : {e}")
            erreurs += 1
            time.sleep(pause)
            continue

        if not texte_brut:
            print("    (aucun texte extrait, PDF probablement scanné ou vide)")
            vides += 1
            time.sleep(pause)
            continue

        texte_propre = nettoyer_texte(texte_brut)
        texte_propre = tronquer_texte(texte_propre)
        langue = detecter_langue(texte_propre)

        # Tentative d'extraction de date depuis le contenu du PDF
        date_extraite = extraire_date_depuis_texte(texte_propre)
        if not date_extraite:
            date_extraite = extraire_date_last_modified(url_source, HEADERS)

        mettre_a_jour_texte_et_date(
            doc_id, texte_propre, langue, date_extraite
        )
        mis_a_jour += 1

        if date_extraite:
            print(f"    ✓ date récupérée depuis le texte : {date_extraite}")

        time.sleep(pause)  # rester correct vis-à-vis du serveur AMMC

    print(f"\n{mis_a_jour} documents mis à jour avec leur texte")
    print(f"{vides} PDF sans texte extractible")
    print(f"{erreurs} erreurs de téléchargement/extraction")


def run_ammc_pipeline():
    collecter_metadonnees()
    enrichir_textes()


if __name__ == "__main__":
    run_ammc_pipeline()