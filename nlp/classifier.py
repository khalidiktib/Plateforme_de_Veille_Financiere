import os
import json
from groq import Groq
from dotenv import load_dotenv
from config.settings import GROQ_MODEL_BULK, GROQ_MODEL_FALLBACK

load_dotenv()
client = Groq(api_key=os.getenv("LLM_API_KEY"))

def _appeler_groq(model: str, prompt: str) -> dict:
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=100,
        temperature=0.1
    )
    texte = response.choices[0].message.content.strip()
    texte = texte.replace("```json", "").replace("```", "").strip()
    return json.loads(texte)

def classifier_document(texte_document: str, source: str) -> dict:
    prompt = f"""Tu es un analyste financier senior spécialisé sur le marché marocain.

Analyse ce document financier et réponds UNIQUEMENT en JSON avec ce format exact, sans aucun texte avant ou après :
{{
  "classification": "RISQUE" ou "OPPORTUNITE" ou "NEUTRE",
  "niveau_impact": 1 ou 2 ou 3,
  "justification_impact": "courte explication factuelle, ex: Croissance des virements (+167%)"
}}

Règles de classification :
- RISQUE : baisse d'indices, volume faible, tension réglementaire
- OPPORTUNITE : hausse d'indices, volume élevé, signal positif
- NEUTRE : information factuelle sans signal clair

Niveau d'impact :
- 1 = faible (variation < 0.5%)
- 2 = modéré (variation entre 0.5% et 1.5%)
- 3 = élevé (variation > 1.5% ou signal fort)

Source : {source}
Document : {texte_document}"""

    try:
        return _appeler_groq(GROQ_MODEL_BULK, prompt)
    except Exception as e:
        print(f"  ⚠ {GROQ_MODEL_BULK} échoué ({e}) — bascule fallback")
        try:
            return _appeler_groq(GROQ_MODEL_FALLBACK, prompt)
        except Exception:
            return {
                "classification": "NEUTRE",
                "niveau_impact": 1,
                "justification_impact": "Non déterminé (échec des modèles)"
            }