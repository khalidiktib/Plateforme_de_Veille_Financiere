import os
import json
import re
from groq import Groq
from dotenv import load_dotenv
from config.settings import GROQ_MODEL_REASONING, GROQ_MODEL_FALLBACK

load_dotenv()
client = Groq(api_key=os.getenv("LLM_API_KEY"))

PROMPT_SYNTHESE = """Tu es un analyste financier senior spécialisé sur le marché marocain. 
Voici les résumés des documents publiés récemment par Bank Al-Maghrib, l'AMMC et la Bourse de Casablanca.

Identifie s'il existe UNE tendance ou un signal notable qui ressort de PLUSIEURS documents (idéalement de sources différentes). 
Base-toi UNIQUEMENT sur les informations fournies ci-dessous.

Réponds STRICTEMENT sous forme de JSON valide avec cette structure exacte :
{{
  "alerte_detectee": true,
  "niveau": "risque",
  "titre": "Titre synthétique court (10 mots maximum)",
  "message": "D'après l'analyse croisée des publications collectées cette semaine sur le marché financier marocain, on remarque [poursuivre avec 2 à 3 phrases claires, synthétiques et descriptives expliquant le signal pour un analyste pressé].",
  "sources_citees": ["Titre exact du document 1", "Titre exact du document 2"]
}}

Consignes impératives pour les champs :
- "niveau" : choisir STRICTEMENT parmi ["risque", "opportunite", "neutre"].
- "message" : DOIT OBLIGATOIREMENT commencer par une phrase d'accroche descriptive contextualisant les faits (ex: "D'après les documents collectés et analysés cette semaine..."), suivie d'une explication claire et détaillée des faits marquants.
- Si les documents sont neutres ou sans lien direct, résume le climat général du marché avec "niveau": "neutre" et "alerte_detectee": true.

Documents de la semaine :
{contexte}
"""

def construire_contexte_hebdo(documents) -> str:
    lignes = []
    for doc in documents:
        # Récupération optionnelle des scores/classifications si déjà attribués
        classif = getattr(doc, 'classification', None)
        impact = getattr(doc, 'niveau_impact', None)
        meta = f" [{classif} - Impact: {impact}/3]" if classif and impact else ""
        
        lignes.append(
            f"[{doc.source} - {doc.date_publication}]{meta} {doc.titre}\n{doc.resume}"
        )
    return "\n---\n".join(lignes)

def _nettoyer_json(texte: str) -> str:
    """Nettoie le texte renvoyé par le LLM pour garantir un parsing JSON valide."""
    clean_text = texte.strip()
    clean_text = re.sub(r"^```json\s*", "", clean_text, flags=re.MULTILINE)
    clean_text = re.sub(r"^```\s*", "", clean_text, flags=re.MULTILINE)
    clean_text = re.sub(r"```$", "", clean_text, flags=re.MULTILINE).strip()
    return clean_text

def _appeler_groq(model: str, prompt: str) -> str:
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        max_tokens=1500,
        temperature=0.3
    )
    return response.choices[0].message.content.strip()

def generer_synthese(documents) -> dict:
    if not documents:
        return {"alerte_detectee": False}

    contexte = construire_contexte_hebdo(documents)
    prompt = PROMPT_SYNTHESE.format(contexte=contexte)

    for model in [GROQ_MODEL_REASONING, GROQ_MODEL_FALLBACK]:
        try:
            texte_brut = _appeler_groq(model, prompt)
            texte_clean = _nettoyer_json(texte_brut)
            return json.loads(texte_clean)
        except Exception as e:
            print(f"  ⚠ {model} échoué ({e})")

    return {"alerte_detectee": False}