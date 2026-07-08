"""
db.py

Configure la connexion à PostgreSQL via SQLAlchemy.
Fournit une session de base de données réutilisable pour tout le projet
et une fonction permettant de tester la connexion à la base.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
from config.settings import DATABASE_URL

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

@contextmanager
def get_session():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

def test_connexion():
    with get_session() as s:
        result = s.execute(text("SELECT version()")).fetchone()
        print(f"✓ Connecté : {result[0]}")

if __name__ == "__main__":
    test_connexion()