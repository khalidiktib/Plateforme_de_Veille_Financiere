import pandas as pd
import json
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

load_dotenv()

LOCAL_URL = os.getenv("DATABASE_URL")
SUPABASE_URL = "postgresql://postgres.bekjvudmczejrebmhtry:Fin_int%40l123456@aws-0-eu-west-3.pooler.supabase.com:5432/postgres"

def migrer():
    print("Connexion aux deux bases...")
    engine_local = create_engine(LOCAL_URL)
    engine_supabase = create_engine(SUPABASE_URL)

    print("Lecture des données locales...")
    df = pd.read_sql("SELECT * FROM documents", engine_local)
    print(f"{len(df)} documents trouvés")

    # Convertir metadata dict → JSON string
    df["metadata"] = df["metadata"].apply(
        lambda x: json.dumps(x) if isinstance(x, dict) else x
    )

    # Convertir score_risque en int
    df["score_risque"] = df["score_risque"].fillna(0).astype(int)
    df["score_risque"] = df["score_risque"].replace(0, None)

    print("Import sur Supabase...")
    df.to_sql(
        "documents",
        engine_supabase,
        if_exists="append",
        index=False,
        chunksize=10
    )
    print("✅ Migration terminée")

    with engine_supabase.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM documents")
        ).fetchone()[0]
    print(f"✅ {count} documents sur Supabase")

if __name__ == "__main__":
    migrer()