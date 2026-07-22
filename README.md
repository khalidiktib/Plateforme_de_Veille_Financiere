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

Chaque membre crée **ses propres clés gratuites** :

| Usage | Fournisseur | Où l'obtenir |
|---|---|---|
| Résumé + classification | Groq | https://console.groq.com |
| Extraction de signaux faibles | Gemini | https://aistudio.google.com/apikey |

```dotenv
LLM_API_KEY=gsk_...
GEMINI_API_KEY=AIza...
```

Les clés restent sur votre machine — ne jamais les committer sur GitHub.

---


## Structure du Projet
```text
├── collectors/                 # Scraping par source
│   ├── bam/                    # Bank Al-Maghrib (Fatima)
│   ├── ammc/                   # AMMC (Houda) ✅
│   └── bourse/                 # Bourse de Casablanca (Khalid) ✅
├── extractors/                 # Extraction de texte (PDF, HTML) ✅
├── cleaners/
│   ├── text_cleaner.py         # Nettoyage, détection de langue ✅
│   ├── deduplicator.py         # Hash de déduplication ✅
│   ├── date_extractor.py       # Date depuis le contenu du PDF ✅
│   └── http_date_extractor.py  # Date depuis le header HTTP Last-Modified ✅
├── storage/                    # Connexion Supabase et requêtes ✅
├── nlp/
│   ├── summarizer.py           # Résumé automatique (Groq) ✅
│   ├── run_nlp.py               
│   ├── classifier.py           # Classification risque/opportunité (Groq) ✅
│   ├── run_classifier.py
│   ├── signal_extractor.py     # Extraction signaux faibles (Gemini + fallback Groq) ✅
│   ├── run_signals.py
│   └── backfill_dates_ammc.py  # Rattrapage des dates manquantes AMMC ✅
├── dashboard/                   # Interface Streamlit ✅
├── database/                    # Schéma SQL ✅
├── config/                      # Paramètres globaux
├── data/                        # Fichiers temporaires (ignorés par Git)
└── tests/                       # Tests d'infrastructure ✅
```

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

# Extraction de signaux faibles
python -c "from nlp.run_signals import run_signals_pipeline; run_signals_pipeline(limite=50)"

# Rattraper les dates manquantes (AMMC)
python -m nlp.backfill_dates_ammc

# Vérifier l'état de la base (Supabase SQL Editor ou psql)
SELECT source, COUNT(*), 
       SUM(CASE WHEN statut_nlp='done' THEN 1 ELSE 0 END) as resumes,
       SUM(CASE WHEN mots_cles IS NOT NULL THEN 1 ELSE 0 END) as avec_signaux
FROM documents GROUP BY source;

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
| date_publication | DATE | Date de publication (voir cascade d'extraction ci-dessous) |
| langue | VARCHAR | fr / ar |
| texte_nettoye | TEXT | Texte extrait et nettoyé |
| hash | VARCHAR | Empreinte pour déduplication |
| resume | TEXT | Résumé généré par l'IA |
| classification | VARCHAR | RISQUE / OPPORTUNITE / NEUTRE |
| score_risque | INTEGER | 1 (faible) / 2 (modéré) / 3 (élevé) |
| mots_cles | JSONB | Signaux faibles extraits par le LLM (liste de termes) |
| statut_nlp | VARCHAR | pending / done / error |
| date_collecte | TIMESTAMP | Date d'insertion en base |
| metadata | JSONB | Données spécifiques à la source |

---

### Fiabilisation de `date_publication`

En cascade, par ordre de priorité :
1. Date extraite du titre du fichier (par le collector de la source)
2. Date extraite du contenu du PDF (`cleaners/date_extractor.py`)
3. Header HTTP `Last-Modified` du fichier source (`cleaners/http_date_extractor.py`)
4. À défaut, la colonne reste `NULL` — le document est exclu des requêtes 
   temporelles plutôt que de lui assigner une date approximative.

---

## Mécanisme des signaux faibles

Deux logiques distinctes à ne pas confondre :

- **`mots_cles` (colonne en base)** : décidés par le LLM à partir du texte 
  brut du document — extraction sémantique, pas une liste de mots fixée à 
  l'avance. Utilisés pour la détection automatique de tendances (comptage 
  d'occurrences sur 90 jours, toutes sources confondues).
- **Barre de recherche du dashboard** : recherche texte simple (`ILIKE`) 
  choisie par l'analyste, sur résumé/titre/texte. Aucun lien avec `mots_cles`.

Un signal est considéré comme fort quand il apparaît **dans plusieurs 
sources** sur la même période (badge "Multi-sources" dans le dashboard).

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
| Infrastructure Supabase (partagée) | ✅ Fait | Khalid |
| Pipeline Bourse de Casablanca | ✅ Fait | Khalid |
| Pipeline AMMC | ✅ Fait | Houda |
| Résumé automatique (NLP) | ✅ Fait | Khalid |
| Classification risque / opportunité | ✅ Fait | Khalid |
| Fiabilisation des dates (cascade titre→PDF→HTTP) | ✅ Fait | Khalid |
| Détection de signaux faibles (mots_cles) | ✅ Fait — branche `khalid-work` | Khalid |
| Détection multi-sources (AMMC + Bourse) | ✅ Validé | Khalid |
| Recherche par mot-clé (dashboard) | ✅ Fait — branche `khalid-work` | Khalid |
| Dashboard — KPIs, alertes, score du jour, signaux | ✅ Fait | Khalid |
| Pipeline BAM | 🔄 En cours | Fatima |
| Merge `khalid-work` → `main` | 🔄 À faire | Khalid |