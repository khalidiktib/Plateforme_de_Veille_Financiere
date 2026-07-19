import time
from sqlalchemy import text
from storage.db import get_session
from nlp.classifier import classifier_document
import socket

def verifier_connexion():
    try:
        socket.getaddrinfo("aws-0-eu-west-3.pooler.supabase.com", 5432)
        print("✓ Connexion Supabase accessible")
    except socket.gaierror:
        print("✗ Supabase inaccessible — utilise le hotspot ou un VPN")
        exit(1)


def run_classifier_pipeline(limite: int = 69):
    print("=" * 50)
    print("Pipeline Classification")
    print("=" * 50)
    verifier_connexion()

    with get_session() as s:
        docs = s.execute(text("""
            SELECT id, resume, source, titre
            FROM documents
            WHERE statut_nlp = 'done'
            AND resume IS NOT NULL
            AND classification IS NULL
            LIMIT :l
        """), {"l": limite}).fetchall()

    print(f"{len(docs)} documents à classifier\n")
    succes = 0
    erreurs = 0

    for doc in docs:
        try:
            print(f"Classification {doc.id} — "
                  f"{doc.titre[:45]}...", end=" ")

            result = classifier_document(doc.resume, doc.source)

            with get_session() as s:
                s.execute(text("""
                    UPDATE documents
                    SET classification = :c,
                        score_risque = :s
                    WHERE id = :id
                """), {
                    "c": result["classification"],
                    "s": result["score_risque"],
                    "id": doc.id
                })

            print(f"✓ {result['classification']} "
                  f"(score: {result['score_risque']})")
            succes += 1
            time.sleep(1)

        except Exception as e:
            print(f"✗ ({e})")
            erreurs += 1

    print(f"\n→ {succes} classifiés | {erreurs} erreurs")

    # Résumé des résultats
    with get_session() as s:
        stats = s.execute(text("""
            SELECT classification, 
                   COUNT(*) as nb,
                   AVG(score_risque) as score_moyen
            FROM documents
            WHERE classification IS NOT NULL
            GROUP BY classification
            ORDER BY nb DESC
        """)).fetchall()

    print("\n── Résultats ──────────────────")
    for row in stats:
        print(f"{row.classification:15} "
              f"{row.nb:3} docs | "
              f"score moyen: {row.score_moyen:.1f}")

if __name__ == "__main__":
    run_classifier_pipeline()