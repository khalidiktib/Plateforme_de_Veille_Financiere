import os
import time
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
client = Groq(api_key=os.getenv("LLM_API_KEY"))

def classifier_document(resume: str, source: str) -> dict:
    """
    Retourne {"classification": "RISQUE"|"OPPORTUNITE"|"NEUTRE",
              "score_risque": 1|2|3}
    """
    prompt = f"""Tu es un analyste financier senior spécialisé 
sur le marché marocain.

Analyse ce résumé financier et réponds UNIQUEMENT en JSON 
avec ce format exact, sans aucun texte avant ou après :
{{"classification": "RISQUE" ou "OPPORTUNITE" ou "NEUTRE",
  "score_risque": 1 ou 2 ou 3}}

Règles de classification :
- RISQUE : baisse d'indices, volume faible, tension réglementaire
- OPPORTUNITE : hausse d'indices, volume élevé, signal positif
- NEUTRE : information factuelle sans signal clair

Score de risque :
- 1 = faible (variation < 0.5%)
- 2 = modéré (variation entre 0.5% et 1.5%)
- 3 = élevé (variation > 1.5% ou signal fort)

Source : {source}
Résumé : {resume}"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=50,
        temperature=0.1
    )

    import json
    texte = response.choices[0].message.content.strip()
    try:
        return json.loads(texte)
    except:
        return {"classification": "NEUTRE", "score_risque": 1}