# Plateforme de Veille Financière

Veille financière augmentée par l'IA sur les sources institutionnelles 
marocaines — Bank Al-Maghrib, AMMC, Bourse de Casablanca.

## Prérequis
- Python 3.10+
- Docker Desktop

## Installation

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
cp .env.example .env
```
Remplir `DATABASE_URL` avec l'URL Supabase (demander à Khalid) et `LLM_API_KEY` 
avec votre propre clé Groq gratuite.

**4. Tester l'installation**
```bash
python -m tests.test_infra
```

Résultat attendu :
✓ Connecté : PostgreSQL 16...
✓ Nettoyage : ...
✓ Hash : ...
✓ Langue détectée : fr
✓ Tout fonctionne — prêt pour les collectors

### 4. Lancer PostgreSQL via Docker
```bash
docker compose up -d
```

Vérifier que le container tourne :
```bash
docker ps
# Vous devez voir pvf-postgres avec status "Up"
```

### 5. Initialiser la base de données
```bash
docker exec -i pvf-postgres psql -U pvf_admin -d pvf_db < database/schema.sql
```

### 6. Tester l'installation
```bash
python -m tests.test_infra
```

Résultat attendu :
✓ Connecté : PostgreSQL 16.14
✓ Nettoyage : ...
✓ Hash : ...
✓ Langue détectée : fr
✓ Tout fonctionne — prêt pour les collectors

---

## Clé API Groq (obligatoire pour le NLP)

Chaque membre doit créer **sa propre clé gratuite** :

1. Aller sur https://console.groq.com
2. Créer un compte
3. Cliquer sur "API Keys" → "Create API Key"
4. Copier la clé et la coller dans `.env` :
LLM_API_KEY=gsk_...

La clé reste sur votre machine — ne jamais la committer sur GitHub.


## Structure du Projet

```text
├── collectors/                # Scraping par source
│   ├── bam/                   # Bank Al-Maghrib (Fatima)
│   ├── ammc/                  # AMMC (Houda)
│   └── bourse/                # Bourse de Casablanca (Khalid) ✅
├── extractors/                # Extraction de texte (PDF, HTML) ✅
├── cleaners/                  # Nettoyage et déduplication ✅
├── storage/                   # Connexion PostgreSQL et requêtes ✅
├── nlp/                       # Résumé automatique + classification (risque/opportunité/neutre) via Groq/Gemini ✅
├── dashboard/                 # Interface Streamlit ✅
├── database/                  # Schéma SQL ✅
├── config/                    # Paramètres globaux
├── data/                      # Fichiers temporaires (ignorés par Git)
└── tests/                     # Tests d'infrastructure ✅

---

## Commandes utiles

```bash
# Tester l'infrastructure
python -m tests.test_infra

# Lancer un pipeline (exemple Bourse)
python -m collectors.bourse.bourse_pipeline

# Lancer le NLP sur les documents en attente
python -c "from nlp.run_nlp import run_nlp_pipeline; run_nlp_pipeline(limite=50)"

# Lancer la classification (risque / opportunité / neutre)
python -m nlp.run_classifier

# Lancer le dashboard
python -m streamlit run dashboard/app.py

# Vérifier les données en base
docker exec -it pvf-postgres psql -U pvf_admin -d pvf_db \
  -c "SELECT source, COUNT(*), SUM(CASE WHEN statut_nlp='done' THEN 1 ELSE 0 END) as resumes FROM documents GROUP BY source;"

# Arrêter Docker
docker compose down

# Redémarrer Docker (après redémarrage PC)
docker compose up -d
```

---

## Schéma de la base de données

Table principale `documents` :

| Colonne | Type | Description |
|---|---|---|
| id | SERIAL | Identifiant unique |
| source | VARCHAR | BAM / AMMC / BOURSE |
| type_document | VARCHAR | rapport / communique / resume_seance / ... |
| titre | TEXT | Titre du document |
| url_source | TEXT | URL d'origine |
| date_publication | DATE | Date de publication |
| langue | VARCHAR | fr / ar |
| texte_nettoye | TEXT | Texte extrait et nettoyé |
| hash | VARCHAR | Empreinte pour déduplication |
| resume | TEXT | Résumé généré par l'IA |
| classification | VARCHAR | RISQUE / OPPORTUNITE / NEUTRE |
| score_risque | INTEGER | 1 (faible) / 2 (modéré) / 3 (élevé) |
| statut_nlp | VARCHAR | pending / done / error |
| date_collecte | TIMESTAMP | Date d'insertion en base |
| metadata | JSONB | Données spécifiques à la source |

---

## Intégrer votre pipeline (Fatima / Houda)

Votre collector doit appeler les fonctions partagées dans cet ordre :

```python
from extractors.pdf_extractor import extraire_texte_pdf
from cleaners.text_cleaner import nettoyer_texte, detecter_langue
from cleaners.deduplicator import calculer_hash
from storage.repositories import document_existe, inserer_document

# 1. Extraire le texte
texte_brut = extraire_texte_pdf(chemin_pdf)

# 2. Nettoyer
texte_propre = nettoyer_texte(texte_brut)

# 3. Dédupliquer
hash_doc = calculer_hash(texte_propre)
if document_existe(hash_doc):
    continue  # déjà en base

# 4. Insérer
inserer_document({
    "source": "BAM",          # ou "AMMC"
    "type_document": "rapport",
    "titre": "...",
    "url_source": "...",
    "date_publication": date,
    "langue": detecter_langue(texte_propre),
    "texte_nettoye": texte_propre,
    "hash": hash_doc,
    "metadata": json.dumps({})
})
```

Le NLP tourne séparément — vous n'avez pas à appeler le summarizer
dans votre pipeline. Il suffit d'insérer avec `statut_nlp='pending'`
(valeur par défaut) et le pipeline NLP s'en charge.

---

---

## Guide de démarrage par membre

### 🟢 Fatima — première connexion

Tu commences directement avec Supabase, pas besoin de Docker.

1. Suis les 4 étapes d'installation ci-dessus
2. Une fois `test_infra` ✅, commence la **phase de reconnaissance** du site 
   BAM (avant de coder quoi que ce soit) : explore le site manuellement, 
   note les URLs, le format des fichiers (PDF/HTML), la structure des liens
3. Documente ça dans `notebooks/bam_exploration.ipynb`
4. Une fois la structure du site claire, code ton collector dans 
   `collectors/bam/` en suivant le template de la section "Intégrer votre pipeline"
5. Chaque document inséré apparaît automatiquement dans le dashboard commun

### 🟡 Houda — migration depuis ta base locale

Tu as déjà des données collectées en local avec Docker+PostgreSQL. On migre 
ce que tu as vers Supabase, puis tu continues directement sur Supabase.

**1. Pull le repo à jour** (contient le script de migration)
```bash
git pull
```

**2. Garde ton `.env` actuel pointé sur ta base locale Docker** le temps de migrer

**3. Ajoute temporairement l'URL Supabase dans ton `.env` :**
```dotenv
DATABASE_URL=postgresql://pvf_admin:TON_MDP@localhost:5433/pvf_db
SUPABASE_URL=postgresql://postgres.bekjvudmczejrebmhtry:MDP_SUPABASE@aws-0-eu-west-3.pooler.supabase.com:5432/postgres
```

**4. Lance la migration** (script déjà dans le repo : `storage/migrate_to_supabase.py`)
```bash
python -m storage.migrate_to_supabase
```

**5. Une fois la migration confirmée** (`✅ X documents sur Supabase`), 
remplace définitivement `DATABASE_URL` par l'URL Supabase et supprime 
`SUPABASE_URL`. Tu peux arrêter Docker :
```bash
docker compose down
```

**6. Vérifie que tout fonctionne sur Supabase :**
```bash
python -m tests.test_infra
```

Continue ton pipeline AMMC directement sur Supabase à partir de maintenant.
## État d'avancement

| Composant | Statut | Responsable |
|---|---|---|
| Infrastructure PostgreSQL | ✅ Fait | Khalid |
| Pipeline Bourse de Casablanca | ✅ Fait | Khalid |
| Module NLP — résumé automatique | ✅ Fait | Khalid |
| Module NLP — classification (risque/opportunité) | ✅ Fait | Khalid |
| Dashboard — KPIs + alertes + score du jour | ✅ Fait | Khalid |
| Pipeline BAM | 🔄 En cours | Fatima |
| Pipeline AMMC | 🔄 En cours | Houda |