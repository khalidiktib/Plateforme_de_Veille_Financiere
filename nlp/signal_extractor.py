import os
import json
from google import genai
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
groq_client = Groq(api_key=os.getenv("LLM_API_KEY"))

def _prompt(texte: str, source: str) -> str:
    return f"""Lis ce document financier marocain et extrais 
UNIQUEMENT les signaux faibles — mentions discrètes de risques, 
tensions, ou changements émergents.

Réponds UNIQUEMENT en JSON, sans texte avant ou après :
{{"mots_cles": ["mot1", "mot2"], "niveau": 0}}

niveau : 0 = aucun signal, 1 = faible, 2 = modéré, 3 = fort

Source : {source}
Document :
{texte[:4000]}"""

def extraire_signaux(texte: str, source: str) -> dict:
    prompt = _prompt(texte, source)

    try:
        response = gemini_client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        return json.loads(response.text.strip())
    except Exception as e:
        print(f"  ⚠ Gemini échoué ({e}) — bascule Groq")

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100
        )
        return json.loads(response.choices[0].message.content.strip())
    except Exception as e:
        print(f"  ✗ Groq aussi échoué ({e})")
        return {"mots_cles": [], "niveau": 0}