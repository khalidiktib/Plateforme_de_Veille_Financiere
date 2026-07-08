"""
test_infra.py

Valide le bon fonctionnement de l'infrastructure de base du projet.
Ce script vérifie la connexion à PostgreSQL ainsi que les principaux
modules utilitaires (nettoyage de texte, génération de hash et
détection de langue) avant le développement des collectors et
des traitements NLP.
"""

# tests/test_infra.py
import sys, os
sys.path.insert(0, os.path.abspath("."))

from storage.db import test_connexion
from cleaners.text_cleaner import nettoyer_texte, detecter_langue
from cleaners.deduplicator import calculer_hash

def test_tout():
    # 1. Connexion base
    test_connexion()

    # 2. Nettoyage texte
    texte_brut = "Rapport   annuel  Page 1 sur 10  Bank Al-Maghrib"
    texte_propre = nettoyer_texte(texte_brut)
    assert "Page 1 sur 10" not in texte_propre
    print(f"✓ Nettoyage : {texte_propre}")

    # 3. Hash
    h = calculer_hash("test")
    assert len(h) == 64
    print(f"✓ Hash : {h[:20]}...")

    # 4. Langue
    langue = detecter_langue("Ceci est un texte en français")
    print(f"✓ Langue détectée : {langue}")

    print("\nTout fonctionne — prêt pour les collectors")

if __name__ == "__main__":
    test_tout()