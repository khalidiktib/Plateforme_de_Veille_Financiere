import json
import time
from sqlalchemy import text
from storage.db import get_session
from nlp.signal_extractor import extraire_signaux

def run_signals_pipeline(limite: int = 50):
    print("=" * 50)
    print("Pipeline Extraction Signaux Faibles")
    print("=" * 50)

    with get_session() as s:
        docs = s.execute(text("""
            SELECT id, texte_nettoye, source, titre
            FROM documents
            WHERE statut_nlp = 'done'
            AND mots_cles IS NULL
            AND texte_nettoye IS NOT NULL
            LIMIT :l
        """), {"l": limite}).fetchall()

    print(f"{len(docs)} documents à traiter\n")
    succes, erreurs = 0, 0

    for doc in docs:
        try:
            print(f"Signaux {doc.id} — {doc.titre[:45]}...", end=" ")
            result = extraire_signaux(doc.texte_nettoye, doc.source)

            with get_session() as s:
                s.execute(text("""
                    UPDATE documents
                    SET mots_cles = :mc
                    WHERE id = :id
                """), {
                    "mc": json.dumps(result["mots_cles"]),
                    "id": doc.id
                })

            print(f"✓ niveau {result['niveau']} — {result['mots_cles']}")
            succes += 1
            time.sleep(1)

        except Exception as e:
            print(f"✗ ({e})")
            erreurs += 1

    print(f"\n→ {succes} traités | {erreurs} erreurs")

if __name__ == "__main__":
    run_signals_pipeline()