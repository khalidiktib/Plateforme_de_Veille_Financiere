"""
pdf_extractor.py

Extrait le texte brut des documents PDF à l'aide de pdfplumber.
Ce module est utilisé par les collectors pour convertir les rapports,
communiqués et publications PDF en texte exploitable par les étapes
de nettoyage, de stockage et de traitement NLP.
"""

import pdfplumber

def extraire_texte_pdf(chemin: str) -> str:
    texte = ""
    try:
        with pdfplumber.open(chemin) as pdf:
            for page in pdf.pages:
                contenu = page.extract_text()
                if contenu:
                    texte += contenu + "\n"
    except Exception as e:
        print(f"Erreur extraction PDF {chemin} : {e}")
    return texte.strip()

