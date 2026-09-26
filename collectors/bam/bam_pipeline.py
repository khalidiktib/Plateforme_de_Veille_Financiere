# collectors/bam/bam_pipeline.py
import tempfile
import os
import json
from collectors.bam.bam_collector import collecter_toutes_sections, collecter_section, SEED_SECTIONS
from extractors.pdf_extractor import extraire_texte_pdf
from cleaners.text_cleaner import nettoyer_texte, detecter_langue
from cleaners.deduplicator import calculer_hash
from storage.repositories import document_existe, inserer_document


def run_bam_pipeline(limite_par_section: int | None = None, sections: list[dict] | None = None):
    """
    limite_par_section : plafonne le nb de PDF collectés par section (utile
    pour tester rapidement sans lancer les 18 sections en entier).
    sections : sous-ensemble de SEED_SECTIONS à tester (par défaut : toutes).
    """
    print("=" * 50)
    print("Pipeline BAM (Bank Al-Maghrib)")
    print("=" * 50)

    if sections:
        documents = []
        for section in sections:
            documents.extend(collecter_section(section, limite=limite_par_section))
        print(f"\n→ {len(documents)} PDFs collectés sur {len(sections)} section(s)")
    else:
        documents = collecter_toutes_sections(limite_par_section=limite_par_section)

    nouveaux = 0
    ignores = 0
    erreurs = 0

    for doc in documents:
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(doc["contenu_pdf"])
                chemin_tmp = tmp.name

            texte_brut = extraire_texte_pdf(chemin_tmp)
            os.unlink(chemin_tmp)

            if not texte_brut or len(texte_brut) < 100:
                print(f"  ⚠ PDF vide : {doc['titre']}")
                erreurs += 1
                continue

            texte_propre = nettoyer_texte(texte_brut)
            hash_doc = calculer_hash(texte_propre)

            if document_existe(hash_doc):
                ignores += 1
                continue

            inserer_document({
                "source": "BAM",
                "type_document": doc["type_document"],
                "titre": doc["titre"],
                "url_source": doc["url"],
                "date_publication": doc["date_publication"],
                "langue": detecter_langue(texte_propre),
                "texte_nettoye": texte_propre,
                "hash": hash_doc,
                "metadata": json.dumps({
                    "url_originale": doc["url"],
                    "type": doc["type_document"],
                }),
            })
            nouveaux += 1
            print(f"  ✓ Stocké : {doc['titre']}")

        except Exception as e:
            print(f"  ✗ Erreur sur {doc.get('titre')} : {e}")
            erreurs += 1

    print("\n" + "=" * 50)
    print(f"Résultat : {nouveaux} nouveaux | "
          f"{ignores} déjà en base | {erreurs} erreurs")
    print("=" * 50)
    return nouveaux, erreurs


if __name__ == "__main__":
    # Premier passage : toutes les sections, sans limite
    run_bam_pipeline()