import time
from nlp.summarizer import resumer_document
from storage.repositories import get_pending, marquer_resume

def run_nlp_pipeline(limite: int = 50):
    print("=" * 50)
    print("Pipeline NLP — Résumé automatique")
    print("=" * 50)
    
    docs = get_pending(limite=limite)
    print(f"{len(docs)} documents à traiter\n")
    
    succes = 0
    erreurs = 0

    for doc in docs:
        try:
            print(f"Résumé {doc.id} — {doc.titre[:50]}...", 
                  end=" ")
            resume = resumer_document(
                doc.texte_nettoye,
                doc.source,
                doc.type_document if hasattr(doc, 'type_document') 
                else "document"
            )
            marquer_resume(doc.id, resume)
            print("✓")
            succes += 1
            time.sleep(2)
        except Exception as e:
            err = str(e)
            # Si rate limit → attendre et réessayer une fois
            if "429" in err and "retry" in err.lower():
                print(f"⏳ Rate limit — pause 60s...")
                time.sleep(60)
                try:
                    resume = resumer_document(
                        doc.texte_nettoye,
                        doc.source,
                        doc.type_document
                    )
                    marquer_resume(doc.id, resume)
                    print(f"✓ (après retry)")
                    succes += 1
                except:
                    print(f"✗ (échec retry)")
                    erreurs += 1
            else:
                print(f"✗ ({e})")
                erreurs += 1

    print(f"\n→ {succes} résumés générés | {erreurs} erreurs")

if __name__ == "__main__":
    run_nlp_pipeline()