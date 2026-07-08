"""
deduplicator.py

Calcule une empreinte SHA-256 du contenu textuel afin d'identifier
les documents déjà collectés. Le hash est utilisé pour éviter
l'insertion de doublons dans la base PostgreSQL.
"""

import hashlib

def calculer_hash(texte: str) -> str:
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()