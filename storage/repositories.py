"""
repositories.py

Regroupe les opérations d'accès aux données (CRUD) de la plateforme.
Ce module centralise les interactions avec la table `documents` :
- insertion et vérification des documents,
- récupération des documents à traiter,
- mise à jour des résumés NLP,
- extraction des signaux faibles et classifications,
- statistiques sur la base de données.

L'objectif est d'isoler la logique SQL du reste de l'application afin de
faciliter la maintenance et les évolutions du projet.
"""

import hashlib
import json
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
    est encore NULL.
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

def mettre_a_jour_texte_et_date(doc_id: int, texte_nettoye: str, 
                                 langue: str, date_publication: str | None):
    """
    Met à jour le texte nettoyé, la langue, et optionnellement
    la date de publication si elle a été extraite depuis le contenu.
    """
    with get_session() as s:
        if date_publication:
            s.execute(text("""
                UPDATE documents
                SET texte_nettoye = :texte, 
                    langue = :langue,
                    date_publication = :date_pub
                WHERE id = :id
                AND date_publication IS NULL
            """), {
                "texte": texte_nettoye, 
                "langue": langue,
                "date_pub": date_publication,
                "id": doc_id
            })
        else:
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

# ── Fonctions dédiées aux Signaux Faibles ─────────────────────────

def get_pending_signals(limite: int = 50):
    """Récupère les documents prêts pour l'extraction de signaux faibles."""
    with get_session() as s:
        return s.execute(text("""
            SELECT id, texte_nettoye, source, titre
            FROM documents
            WHERE statut_nlp = 'done'
            AND signal_info IS NULL
            AND texte_nettoye IS NOT NULL
            LIMIT :l
        """), {"l": limite}).fetchall()

def sauvegarder_signal(doc_id: int, signal_info: dict):
    """Sauvegarde le JSON du signal enrichi et synchronise les mots-clés."""
    with get_session() as s:
        s.execute(text("""
            UPDATE documents
            SET signal_info = :info,
                mots_cles = :mc
            WHERE id = :id
        """), {
            "info": json.dumps(signal_info),
            "mc": json.dumps(signal_info.get("mots_cles", [])),
            "id": doc_id
        })

def get_signaux_faibles(limite: int = 10):
    """Récupère les derniers signaux faibles validés pour le Dashboard."""
    with get_session() as s:
        return s.execute(text("""
            SELECT 
                id, titre, source, date_publication, url_source,
                signal_info->>'secteur' as secteur,
                signal_info->>'type_signal' as type_signal,
                signal_info->>'resume_signal' as resume_signal,
                signal_info->>'explication' as explication,
                signal_info->'mots_cles' as mots_cles
            FROM documents
            WHERE signal_info IS NOT NULL
            AND (signal_info->>'est_signal_faible')::boolean = true
            ORDER BY date_publication DESC
            LIMIT :l
        """), {"l": limite}).fetchall()

# ── Fonctions dédiées à la Classification & Impacts ─────────────────

def get_pending_classification(limite: int = 50):
    """Récupère les documents résumés n'ayant pas encore de classification."""
    with get_session() as s:
        return s.execute(text("""
            SELECT id, resume, source, titre
            FROM documents
            WHERE statut_nlp = 'done'
            AND resume IS NOT NULL
            AND classification IS NULL
            LIMIT :l
        """), {"l": limite}).fetchall()

def sauvegarder_classification(doc_id: int, classification: str, niveau_impact: int, justification_impact: str):
    """Sauvegarde le résultat de la classification, le niveau d'impact et sa justification."""
    with get_session() as s:
        s.execute(text("""
            UPDATE documents
            SET classification = :c,
                niveau_impact = :ni,
                justification_impact = :ji
            WHERE id = :id
        """), {
            "c": classification,
            "ni": niveau_impact,
            "ji": justification_impact,
            "id": doc_id
        })

def stats_classification():
    """Retourne la répartition des classifications et l'impact moyen."""
    with get_session() as s:
        return s.execute(text("""
            SELECT classification, 
                   COUNT(*) as total,
                   AVG(niveau_impact) as impact_moyen
            FROM documents
            WHERE classification IS NOT NULL
            GROUP BY classification
            ORDER BY total DESC
        """)).fetchall()