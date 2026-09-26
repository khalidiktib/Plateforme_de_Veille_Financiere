import os
from groq import Groq
from dotenv import load_dotenv
from config.settings import GROQ_MODEL_BULK, GROQ_MODEL_FALLBACK

load_dotenv()
client = Groq(api_key=os.getenv("LLM_API_KEY"))

def _appeler_groq(model: str, prompt: str) -> str:
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=300,
        temperature=0.3
    )
    return response.choices[0].message.content.strip()

def resumer_document(texte: str, source: str, type_doc: str) -> str:
    texte_tronque = texte[:6000]
    prompt = f"""Tu es un analyste financier senior spécialisé 
sur le marché marocain. Résume ce document en 4-5 phrases 
maximum en français.

Mentionne : sujet principal, chiffres clés si présents, 
impact potentiel pour les institutions financières.

Source : {source} | Type : {type_doc}

Document :
{texte_tronque}

Résumé :"""

    try:
        return _appeler_groq(GROQ_MODEL_BULK, prompt)
    except Exception as e:
        print(f"  ⚠ {GROQ_MODEL_BULK} échoué ({e}) — bascule fallback")
        return _appeler_groq(GROQ_MODEL_FALLBACK, prompt)