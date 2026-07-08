"""
html_extractor.py

Extrait le contenu textuel utile d'une page HTML en supprimant les
éléments non pertinents (menus, scripts, en-têtes, pieds de page, etc.).
Le texte obtenu est destiné aux étapes de nettoyage et de stockage.
"""

from bs4 import BeautifulSoup

def extraire_texte_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["nav", "footer", "script", 
                     "style", "header"]):
        tag.decompose()
    texte = soup.get_text(separator="\n")
    lignes = [l.strip() for l in texte.splitlines() if l.strip()]
    return "\n".join(lignes)