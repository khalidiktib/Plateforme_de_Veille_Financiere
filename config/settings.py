"""
settings.py

Charge les variables de configuration du projet depuis le fichier .env
et les rend accessibles à l'ensemble des modules (PostgreSQL, API, NLP, Dashboard, etc.).

Toute nouvelle variable de configuration doit être ajoutée dans le fichier .env
puis récupérée ici.
"""

from dotenv import load_dotenv
import os

load_dotenv(override=True)   # ← ajoute override=True

DATABASE_URL = os.getenv("DATABASE_URL")
LLM_API_KEY  = os.getenv("LLM_API_KEY")

# Vérification au démarrage
if not DATABASE_URL:
    raise ValueError("DATABASE_URL manquant dans .env")

# Modèles Groq — répartis par quota pour éviter les conflits de rate limit
GROQ_MODEL_BULK = "qwen/qwen3.8-27b"          # résumé, classification
GROQ_MODEL_REASONING = "openai/gpt-oss-120b"  # synthèse hebdomadaire
GROQ_MODEL_FALLBACK = "openai/gpt-oss-20b"    # secours léger, toutes tâches