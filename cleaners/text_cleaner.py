"""
text_cleaner.py

Nettoie et prépare les textes extraits avant leur stockage.
Ce module supprime les caractères inutiles, normalise le contenu,
détecte la langue et tronque les textes trop volumineux afin de
faciliter les traitements NLP ultérieurs.
"""

import re

def nettoyer_texte(texte: str) -> str:
    texte = re.sub(r'Page\s*\d+\s*(sur|of|/)\s*\d+', '', texte)
    texte = re.sub(r'\s+', ' ', texte)
    texte = re.sub(
        r'[^\w\s\.\,\;\:\!\?\-\(\)\/\%\+\=]', ' ', texte
    )
    return texte.strip()

def detecter_langue(texte: str) -> str:
    try:
        from langdetect import detect
        return detect(texte[:500])
    except:
        return "fr"

def tronquer_texte(texte: str, max_chars: int = 8000) -> str:
    if len(texte) <= max_chars:
        return texte
    return texte[:max_chars].rsplit(' ', 1)[0] + "..."