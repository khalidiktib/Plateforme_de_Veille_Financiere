"""
repositories.py

Regroupe les opérations d'accès aux données (CRUD) de la plateforme.
Ce module centralise les interactions avec la table `documents` :
- insertion et vérification des documents,
- récupération des documents à traiter,
- mise à jour des résumés NLP,
- statistiques sur la base de données.

L'objectif est d'isoler la logique SQL du reste de l'application afin de
faciliter la maintenance et les évolutions du projet.
"""

import hashlib
from sqlalchemy import text
from storage.db import get_session

def hash_texte(texte: str) -> str:
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()

def document_existe(hash_doc: str) -> bool:
    with get_session() as s:
        r = s.execute(
            text("SELECT 1 FROM documents WHERE hash=:h"),
            {"h": hash_doc}
        ).fetchone()
        return r is not None

def inserer_document(doc: dict) -> bool:
    """
    Retourne True si inséré, False si déjà existant.
    doc doit contenir : source, type_document, titre,
    url_source, date_publication, langue,
    texte_nettoye, hash, metadata
    """
    with get_session() as s:
        result = s.execute(text("""
            INSERT INTO documents
                (source, type_document, titre, url_source,
                 date_publication, langue, texte_nettoye,
                 hash, metadata)
            VALUES
                (:source, :type_document, :titre, :url_source,
                 :date_publication, :langue, :texte_nettoye,
                 :hash, :metadata)
            ON CONFLICT (hash) DO NOTHING
            RETURNING id
        """), doc)
        return result.fetchone() is not None

def get_pending(limite: int = 20):
    with get_session() as s:
        return s.execute(text("""
            SELECT id, texte_nettoye, source, titre, type_document
            FROM documents
            WHERE statut_nlp = 'pending'
            AND texte_nettoye IS NOT NULL
            AND LENGTH(texte_nettoye) > 200
            ORDER BY date_collecte ASC
            LIMIT :l
        """), {"l": limite}).fetchall()

def marquer_resume(doc_id: int, resume: str):
    with get_session() as s:
        s.execute(text("""
            UPDATE documents
            SET resume = :r, statut_nlp = 'done'
            WHERE id = :id
        """), {"r": resume, "id": doc_id})

def hash_document(source: str, url: str) -> str:
    """
    Hash basé sur source + URL, utilisé quand le texte n'est pas encore
    disponible (ex: étape 1 du pipeline AMMC, insertion sans texte).
    Ne pas confondre avec hash_texte (hash du contenu textuel).
    """
    return hashlib.sha256(f"{source}:{url}".encode("utf-8")).hexdigest()

def get_documents_sans_texte(source: str, limite: int = 500):
    """
    Retourne les documents d'une source donnée dont texte_nettoye
    est encore NULL (utilisé pour le backfill du texte, étape 2 du
    pipeline AMMC). Retourne une liste de tuples (id, url_source, source).
    """
    with get_session() as s:
        return s.execute(text("""
            SELECT id, url_source, source
            FROM documents
            WHERE source = :source
            AND texte_nettoye IS NULL
            ORDER BY date_collecte ASC
            LIMIT :l
        """), {"source": source, "l": limite}).fetchall()

def mettre_a_jour_texte(doc_id: int, texte_nettoye: str, langue: str):
    """
    Met à jour le texte nettoyé et la langue d'un document déjà
    inséré (utilisé après extraction du PDF, étape 2 du pipeline AMMC).
    """
    with get_session() as s:
        s.execute(text("""
            UPDATE documents
            SET texte_nettoye = :texte, langue = :langue
            WHERE id = :id
        """), {"texte": texte_nettoye, "langue": langue, "id": doc_id})
        
def stats_base():
    with get_session() as s:
        return s.execute(text("""
            SELECT 
                source,
                COUNT(*) as total,
                SUM(CASE WHEN statut_nlp='done' 
                    THEN 1 ELSE 0 END) as resumes,
                SUM(CASE WHEN statut_nlp='pending' 
                    THEN 1 ELSE 0 END) as en_attente
            FROM documents
            GROUP BY source
            ORDER BY source
        """)).fetchall()