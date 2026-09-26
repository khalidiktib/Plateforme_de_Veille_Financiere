import time
from storage.repositories import get_pending_signals, sauvegarder_signal
from nlp.signal_extractor import extraire_signaux

def run_signals_pipeline(limite: int = 50):
    print("=" * 50)
    print("Pipeline Extraction Signaux Faibles Enrichis")
    print("=" * 50)

    docs = get_pending_signals(limite)
    print(f"{len(docs)} documents à traiter\n")
    succes, erreurs = 0, 0

    for doc in docs:
        try:
            print(f"Signaux {doc.id} — {doc.titre[:40]}...", end=" ")
            result = extraire_signaux(doc.texte_nettoye, doc.source)

            # Appel propre via repository
            sauvegarder_signal(doc.id, result)

            statut = "📡 SIGNAL DÉTECTÉ" if result.get("est_signal_faible") else "⚪ Neutre"
            print(f"✓ [{result.get('secteur')}] {statut}")
            succes += 1
            time.sleep(1)

        except Exception as e:
            print(f"✗ ({e})")
            erreurs += 1

    print(f"\n→ {succes} traités | {erreurs} erreurs")

if __name__ == "__main__":
    run_signals_pipeline()