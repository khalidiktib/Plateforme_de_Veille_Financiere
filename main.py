import time
from datetime import datetime
import sys
from sqlalchemy import text
from storage.db import get_session

# --- IMPORTS COLLECTEURS ---
try:
    from collectors.bourse.bourse_pipeline import run_bourse_pipeline
    from collectors.bam.bam_pipeline import run_bam_pipeline
    from collectors.ammc.ammc_pipeline import run_ammc_pipeline
except ImportError as e:
    print(f"Erreur d'import des collecteurs : {e}")
    sys.exit(1)

# --- IMPORTS NLP ---
try:
    from nlp.run_nlp import run_nlp_pipeline
    from nlp.run_classifier import run_classifier_pipeline
    from nlp.run_signals import run_signals_pipeline
    from nlp.run_synthese import run_synthese_hebdo
except ImportError as e:
    print(f"Erreur d'import des modules NLP : {e}")
    sys.exit(1)

# Nombre de documents traités par étape NLP à chaque run
# (même valeur partout pour que résumé/classification/signaux
# portent sur le même lot, pas sur des volumes incohérents)
NB_DOCS_PAR_RUN = 10


def print_section(title: str):
    print("\n" + "=" * 70)
    print(f" 🚀 {title.upper()}")
    print("=" * 70)


def synthese_deja_faite_aujourdhui() -> bool:
    """Évite de regénérer une synthèse hebdo (coûteuse en tokens) 
    plusieurs fois le même jour si main.py est relancé pour debug."""
    with get_session() as s:
        r = s.execute(text("""
            SELECT 1 FROM alertes_synthese 
            WHERE date_generation::date = CURRENT_DATE
        """)).fetchone()
        return r is not None


def main():
    start_time = time.time()
    resultats = {}

    print_section("Plateforme de Veille Financière — Exécution Globale (MVP)")
    print(f" Horodatage : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # ---------------------------------------------------------
    # 1. COLLECTE MULTI-SOURCES
    # ---------------------------------------------------------
    print_section("Étape 1 : Collecte (Bourse, BAM, AMMC)")

    print("-> 1/3 Collecte Bourse de Casablanca...")
    try:
        run_bourse_pipeline(nb_jours=5)
        resultats["Collecte Bourse"] = "✓"
    except Exception as e:
        print(f"❌ Erreur Bourse : {e}")
        resultats["Collecte Bourse"] = "❌"

    print("\n-> 2/3 Collecte Bank Al-Maghrib...")
    try:
        run_bam_pipeline(nb_jours=5)
        resultats["Collecte BAM"] = "✓"
    except Exception as e:
        print(f"❌ Erreur BAM : {e}")
        resultats["Collecte BAM"] = "❌"

    print("\n-> 3/3 Collecte AMMC...")
    try:
        # Contrairement à Bourse/BAM, run_ammc_pipeline() n'a pas de
        # paramètre nb_jours — il traite les métadonnées + le backlog
        # de textes manquants en une fois. Peut être plus long.
        run_ammc_pipeline(max_pages=1, limite_texte=NB_DOCS_PAR_RUN)
        resultats["Collecte AMMC"] = "✓"
    except Exception as e:
        print(f"❌ Erreur AMMC : {e}")
        resultats["Collecte AMMC"] = "❌"

    # ---------------------------------------------------------
    # 2. GÉNÉRATION DES RÉSUMÉS
    # ---------------------------------------------------------
    print_section("Étape 2 : Résumés des nouveaux documents")
    try:
        run_nlp_pipeline(limite=NB_DOCS_PAR_RUN)
        print(f"✓ Résumés terminés (batch limité à {NB_DOCS_PAR_RUN}).")
        resultats["Résumés"] = "✓"
    except Exception as e:
        print(f"❌ Erreur Résumés : {e}")
        resultats["Résumés"] = "❌"

    # ---------------------------------------------------------
    # 3. CLASSIFICATION & IMPACT
    # ---------------------------------------------------------
    print_section("Étape 3 : Classification (Risque / Opportunité / Neutre)")
    try:
        run_classifier_pipeline(limite=NB_DOCS_PAR_RUN)
        print("✓ Classification terminée.")
        resultats["Classification"] = "✓"
    except Exception as e:
        print(f"❌ Erreur Classification : {e}")
        resultats["Classification"] = "❌"

    # ---------------------------------------------------------
    # 4. EXTRACTION DES SIGNAUX FAIBLES
    # ---------------------------------------------------------
    print_section("Étape 4 : Extraction des signaux (JSON)")
    try:
        run_signals_pipeline(limite=NB_DOCS_PAR_RUN)
        print("✓ Signaux extraits et sauvegardés.")
        resultats["Signaux faibles"] = "✓"
    except Exception as e:
        print(f"❌ Erreur Signaux : {e}")
        resultats["Signaux faibles"] = "❌"

    # ---------------------------------------------------------
    # 5. SYNTHÈSE HEBDOMADAIRE
    # ---------------------------------------------------------
    print_section("Étape 5 : Synthèse Hebdomadaire")
    try:
        if synthese_deja_faite_aujourdhui():
            print("⏭ Synthèse déjà générée aujourd'hui — étape ignorée.")
            resultats["Synthèse hebdo"] = "⏭ (déjà faite)"
        else:
            run_synthese_hebdo()
            print("✓ Synthèse hebdomadaire actualisée.")
            resultats["Synthèse hebdo"] = "✓"
    except Exception as e:
        print(f"❌ Erreur Synthèse : {e}")
        resultats["Synthèse hebdo"] = "❌"

    # ---------------------------------------------------------
    # BILAN
    # ---------------------------------------------------------
    elapsed = round(time.time() - start_time, 2)
    print("\n" + "=" * 70)
    print(f" 🎉 PIPELINE EXÉCUTÉ EN {elapsed} SECONDES")
    print("=" * 70)
    print("\n📋 Résumé d'exécution :")
    for etape, statut in resultats.items():
        print(f"   {statut}  {etape}")
    print()


if __name__ == "__main__":
    main()