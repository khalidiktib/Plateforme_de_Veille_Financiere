import json
from sqlalchemy import text
from storage.db import get_session
from nlp.synthese_hebdo import generer_synthese

def get_documents_semaine():
    with get_session() as s:
        return s.execute(text("""
            WITH derniere_date AS (
                SELECT MAX(date_publication) as max_date
                FROM documents
                WHERE resume IS NOT NULL
            )
            SELECT source, titre, date_publication, resume
            FROM documents, derniere_date
            WHERE date_publication >= derniere_date.max_date - INTERVAL '14 days'
            AND resume IS NOT NULL
            ORDER BY date_publication DESC
        """)).fetchall()

def sauvegarder_alerte(alerte: dict):
    with get_session() as s:
        s.execute(text("""
            INSERT INTO alertes_synthese
                (niveau, titre, message, sources_citees)
            VALUES
                (:niveau, :titre, :message, :sources)
        """), {
            "niveau": alerte.get("niveau", "neutre"),
            "titre": alerte.get("titre", ""),
            "message": alerte.get("message", ""),
            "sources": json.dumps(alerte.get("sources_citees", []))
        })

def run_synthese_hebdo():
    print("=" * 50)
    print("Synthèse hebdomadaire — génération de l'alerte")
    print("=" * 50)

    documents = get_documents_semaine()
    print(f"{len(documents)} documents cette semaine")

    if not documents:
        print("Aucun document cette semaine — pas de synthèse")
        return

    alerte = generer_synthese(documents)

    if alerte.get("alerte_detectee"):
        sauvegarder_alerte(alerte)
        print(f"✓ Alerte générée : {alerte['titre']}")
        print(f"  Niveau : {alerte['niveau']}")
        print(f"  Sources : {alerte.get('sources_citees', [])}")
    else:
        print("Aucun signal clair détecté cette semaine")

if __name__ == "__main__":
    run_synthese_hebdo()