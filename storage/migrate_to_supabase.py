import pandas as pd
import json
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

load_dotenv()

LOCAL_URL = os.getenv("DATABASE_URL")
SUPABASE_URL = os.getenv("SUPABASE_URL")

def migrer():
    if not SUPABASE_URL:
        raise ValueError(
            "SUPABASE_URL manquant dans .env — "
            "ajoute-le temporairement pour la migration"
        )

    print("Connexion aux deux bases...")
    engine_local = create_engine(LOCAL_URL)
    engine_supabase = create_engine(SUPABASE_URL)

    print("Lecture des données locales...")
    df = pd.read_sql("SELECT * FROM documents", engine_local)
    print(f"{len(df)} documents trouvés")

    if df.empty:
        print("Aucune donnée à migrer.")
        return

    df["metadata"] = df["metadata"].apply(
        lambda x: json.dumps(x) if isinstance(x, dict) else x
    )
    if "score_risque" in df.columns:
        df["score_risque"] = df["score_risque"].astype("Int64")

    print("Import sur Supabase...")
    df.to_sql(
        "documents", engine_supabase,
        if_exists="append", index=False, chunksize=10
    )
    print("✅ Migration terminée")

    with engine_supabase.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM documents")
        ).fetchone()[0]
    print(f"✅ {count} documents sur Supabase")

if __name__ == "__main__":
    migrer()