from sqlalchemy import text
from storage.db import get_session
from cleaners.date_extractor import extraire_date_depuis_texte
from cleaners.http_date_extractor import extraire_date_last_modified
from collectors.ammc.ammc_collector import HEADERS

def backfill_dates():
    with get_session() as s:
        docs = s.execute(text("""
            SELECT id, texte_nettoye, url_source
            FROM documents
            WHERE source = 'AMMC'
            AND date_publication IS NULL
        """)).fetchall()

    print(f"{len(docs)} documents AMMC sans date à traiter")
    trouvees_texte = 0
    trouvees_http = 0

    for doc in docs:
        date_extraite = None

        # 1. Tentative depuis le texte (si disponible)
        if doc.texte_nettoye:
            date_extraite = extraire_date_depuis_texte(doc.texte_nettoye)
            if date_extraite:
                trouvees_texte += 1

        # 2. Fallback : header HTTP Last-Modified
        if not date_extraite and doc.url_source:
            date_extraite = extraire_date_last_modified(
                doc.url_source, HEADERS
            )
            if date_extraite:
                trouvees_http += 1

        if date_extraite:
            with get_session() as s:
                s.execute(text("""
                    UPDATE documents
                    SET date_publication = :d
                    WHERE id = :id
                """), {"d": date_extraite, "id": doc.id})
            print(f"  ✓ doc #{doc.id} → {date_extraite}")
        else:
            print(f"  ✗ doc #{doc.id} → aucune date trouvée")

    total = trouvees_texte + trouvees_http
    print(f"\n{total}/{len(docs)} dates récupérées")
    print(f"  (dont {trouvees_texte} depuis le texte, "
          f"{trouvees_http} depuis Last-Modified HTTP)")

if __name__ == "__main__":
    backfill_dates()