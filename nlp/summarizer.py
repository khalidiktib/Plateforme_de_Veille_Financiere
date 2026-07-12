import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("LLM_API_KEY"))

def resumer_document(texte: str, source: str,
                     type_doc: str) -> str:
    texte_tronque = texte[:6000]

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{
            "role": "user",
            "content": f"""Tu es un analyste financier senior 
spécialisé sur le marché marocain. Résume ce document en 
4-5 phrases maximum en français.

Mentionne : sujet principal, chiffres clés si présents 
(volumes, indices, variations), impact potentiel pour 
les institutions financières.

Source : {source} | Type : {type_doc}

Document :
{texte_tronque}

Résumé :"""
        }],
        max_tokens=300,
        temperature=0.3
    )
    return response.choices[0].message.content.strip()