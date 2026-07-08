# Plateforme de Veille Financière

Veille financière augmentée par l'IA sur les sources institutionnelles 
marocaines — Bank Al-Maghrib, AMMC, Bourse de Casablanca.

## Prérequis
- Python 3.10+
- Docker Desktop

## Installation

**1. Cloner le projet**
```bash
git clone https://github.com/khalidiktib/Plateforme_de_Veille_Financiere.git
cd Plateforme_de_Veille_Financiere
```

**2. Environnement Python**
```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Mac/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

**3. Variables d'environnement**
```bash
# Copier le fichier exemple et remplir les valeurs
cp .env.example .env
```

**4. Lancer PostgreSQL**
```bash
docker compose up -d
docker exec -i pvf-postgres psql -U pvf_admin -d pvf_db < database/schema.sql
```

**5. Tester l'installation**
```bash
python -m tests.test_infra
```

## Structure du projet
collectors/   → Scraping par source (bam / ammc / bourse)

extractors/   → Extraction de texte (PDF, HTML)

cleaners/     → Nettoyage et déduplication

storage/      → Connexion PostgreSQL et requêtes

nlp/          → Résumé automatique via API LLM

dashboard/    → Interface Streamlit

database/     → Schéma SQL

config/       → Paramètres globaux

data/         → Fichiers temporaires (raw / processed)

docs/         → Documentation

tests/        → Tests d'infrastructure

## Commandes utiles
```bash
# Tester l'infrastructure
python -m tests.test_infra

# Vérifier les données en base
docker exec -it pvf-postgres psql -U pvf_admin -d pvf_db \
  -c "SELECT source, COUNT(*) FROM documents GROUP BY source;"
```