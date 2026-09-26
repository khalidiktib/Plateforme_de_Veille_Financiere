import os
import json
import re
from google import genai
from groq import Groq
from dotenv import load_dotenv
from config.settings import GROQ_MODEL_FALLBACK

load_dotenv()

gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
groq_client = Groq(api_key=os.getenv("LLM_API_KEY"))

def _nettoyer_et_parser_json(raw_text: str) -> dict:
    """Extrait et parse proprement le contenu JSON, même entouré de balises markdown."""
    clean_text = raw_text.strip()
    clean_text = re.sub(r"^```json\s*", "", clean_text, flags=re.MULTILINE)
    clean_text = re.sub(r"^```\s*", "", clean_text, flags=re.MULTILINE)
    clean_text = re.sub(r"```$", "", clean_text, flags=re.MULTILINE).strip()
    return json.loads(clean_text)

def _prompt(texte: str, source: str) -> str:
    return f"""En tant qu'analyste financier spécialisé sur le marché marocain, analyse ce document ({source}) et identifie s'il contient un SIGNAL FAIBLE.
Un signal faible est une mention discrète, un changement réglementaire subtil, ou une tension émergente qui pourrait devenir un risque ou une opportunité majeur à l'avenir.

Réponds STRICTEMENT sous forme de JSON valide avec cette structure exacte :
{{
  "est_signal_faible": true,
  "force_signal": 2,
  "type_signal": "RISQUE_EMERGENT", 
  "secteur": "Bancaire",
  "resume_signal": "Mentions discrètes de hausse des impayés sur le segment PME.",
  "mots_cles": ["impayés", "PME", "liquidité"],
  "explication": "Inscrit en note de bas de page mais indique une fragilisation du portefeuille PME."
}}

Remarques pour les champs :
- "force_signal" : entier de 0 à 3 évaluant la puissance ou la clarté du signal émergent (0 si aucun signal, 3 pour un signal très net).
- "type_signal" : choisir uniquement parmi ["RISQUE_EMERGENT", "OPPORTUNITE_EMERGENTE", "AUCUN"]
- "secteur" : ex. Bancaire, BTP, Immobilier, Énergie, Agroalimentaire, Marché Financier, ou Neutre.
- Si AUCUN signal faible n'est détecté, renvoie :
{{"est_signal_faible": false, "type_signal": "AUCUN", "secteur": "Neutre", "resume_signal": "", "mots_cles": [], "explication": ""}}

Document :
{texte[:4000]}"""

def extraire_signaux(texte: str, source: str) -> dict:
    prompt = _prompt(texte, source)

    # 1. Essai avec Gemini 3.6 Flash
    try:
        response = gemini_client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt
        )
        return _nettoyer_et_parser_json(response.text)
    except Exception as e:
        print(f"  ⚠ Gemini échoué ({e}) — bascule Groq")

    # 2. Fallback Groq
    try:
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL_FALLBACK,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=500
        )
        content = response.choices[0].message.content
        return _nettoyer_et_parser_json(content)
    except Exception as e:
        print(f"  ✗ Groq aussi échoué ({e})")
        return {
            "est_signal_faible": False,
            "force_signal": 0,
            "type_signal": "AUCUN",
            "secteur": "Neutre",
            "resume_signal": "",
            "mots_cles": [],
            "explication": ""
        }