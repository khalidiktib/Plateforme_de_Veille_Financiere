-- Activer pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- Table principale
CREATE TABLE IF NOT EXISTS documents (
    id               SERIAL PRIMARY KEY,
    source           VARCHAR(20) NOT NULL,
    type_document    VARCHAR(100),
    titre            TEXT,
    url_source       TEXT,
    date_publication DATE,
    langue           VARCHAR(5) DEFAULT 'fr',
    texte_nettoye    TEXT,
    hash             VARCHAR(64) UNIQUE NOT NULL,
    resume           TEXT,
    statut_nlp       VARCHAR(20) DEFAULT 'pending',
    date_collecte    TIMESTAMP DEFAULT NOW(),
    metadata         JSONB
);

-- Index pour les requêtes fréquentes
CREATE INDEX IF NOT EXISTS idx_source 
    ON documents(source);
CREATE INDEX IF NOT EXISTS idx_date   
    ON documents(date_publication);
CREATE INDEX IF NOT EXISTS idx_statut 
    ON documents(statut_nlp);
CREATE INDEX IF NOT EXISTS idx_hash   
    ON documents(hash);