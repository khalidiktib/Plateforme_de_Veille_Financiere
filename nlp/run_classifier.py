import time
import socket
from storage.repositories import (
    get_pending_classification,
    sauvegarder_classification,
    stats_classification
)
from nlp.classifier import classifier_document

def verifier_connexion():
    try:
        socket.getaddrinfo("aws-0-eu-west-3.pooler.supabase.com", 5432)
        print("✓ Connexion Supabase accessible")
    except socket.gaierror:
        print("✗ Supabase inaccessible — utilise le hotspot ou un VPN")
        exit(1)

def run_classifier_pipeline(limite: int = 400):
    print("=" * 50)
    print("Pipeline Classification & Impact (sur texte brut)")
    print("=" * 50)
    verifier_connexion()

    docs = get_pending_classification(limite)
    print(f"{len(docs)} documents à classifier\n")
    
    succes = 0
    erreurs = 0

    for doc in docs:
        try:
            print(f"Classification {doc.id} — {doc.titre[:45]}...", end=" ")

            # MODIFICATION ICI : On envoie le texte_nettoye complet au lieu du resume
            texte_a_analyser = getattr(doc, 'texte_nettoye', None) or doc.resume
            result = classifier_document(texte_a_analyser, doc.source)

            sauvegarder_classification(
                doc_id=doc.id,
                classification=result.get("classification", "NEUTRE"),
                niveau_impact=int(result.get("niveau_impact", 1)),
                justification_impact=result.get("justification_impact", "")
            )

            print(f"✓ {result.get('classification')} "
                  f"(Impact: {result.get('niveau_impact')}/3)")
            succes += 1
            time.sleep(1)

        except Exception as e:
            print(f"✗ ({e})")
            erreurs += 1

    print(f"\n→ {succes} classifiés | {erreurs} erreurs")

    # Résumé des résultats via la fonction repository
    stats = stats_classification()
    print("\n── Résultats ──────────────────")
    for row in stats:
        moyen = row.impact_moyen if row.impact_moyen is not None else 0.0
        print(f"{row.classification:15} {row.total:3} docs | Impact moyen: {moyen:.1f}")

if __name__ == "__main__":
    run_classifier_pipeline()