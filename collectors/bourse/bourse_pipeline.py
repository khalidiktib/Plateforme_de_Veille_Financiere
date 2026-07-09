# collectors/bourse/bourse_pipeline.py
import tempfile
import os
from collectors.bourse.bourse_collector import collecter_periode
from extractors.pdf_extractor import extraire_texte_pdf
from cleaners.text_cleaner import nettoyer_texte, detecter_langue
from cleaners.deduplicator import calculer_hash
from storage.repositories import document_existe, inserer_document
import json

def run_bourse_pipeline(nb_jours: int = 30):
    print("=" * 50)
    print("Pipeline Bourse de Casablanca")
    print("=" * 50)

    documents = collecter_periode(nb_jours=nb_jours)

    nouveaux = 0
    ignores = 0
    erreurs = 0

    for doc in documents:
        try:
            # Sauvegarder PDF temporairement
            with tempfile.NamedTemporaryFile(
                suffix=".pdf", delete=False
            ) as tmp:
                tmp.write(doc["contenu_pdf"])
                chemin_tmp = tmp.name

            # Extraire texte
            texte_brut = extraire_texte_pdf(chemin_tmp)
            os.unlink(chemin_tmp)

            if not texte_brut or len(texte_brut) < 100:
                print(f"  ⚠ PDF vide : {doc['titre']}")
                erreurs += 1
                continue

            # Nettoyer
            texte_propre = nettoyer_texte(texte_brut)
            hash_doc = calculer_hash(texte_propre)

            # Dédupliquer
            if document_existe(hash_doc):
                ignores += 1
                continue

            # Stocker
            inserer_document({
                "source": "BOURSE",
                "type_document": doc["type_document"],
                "titre": doc["titre"],
                "url_source": doc["url"],
                "date_publication": doc["date_publication"],
                "langue": detecter_langue(texte_propre),
                "texte_nettoye": texte_propre,
                "hash": hash_doc,
                "metadata": json.dumps({
                    "url_originale": doc["url"],
                    "type": doc["type_document"]
                })
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
    # Collecte historique initiale — 90 jours
    run_bourse_pipeline(nb_jours=90)