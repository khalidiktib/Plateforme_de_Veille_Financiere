CREATE TABLE IF NOT EXISTS alertes_synthese (
    id SERIAL PRIMARY KEY,
    date_generation TIMESTAMP DEFAULT NOW(),
    niveau VARCHAR(20),
    titre TEXT,
    message TEXT,
    sources_citees JSONB
);

CREATE INDEX IF NOT EXISTS idx_alertes_date 
    ON alertes_synthese(date_generation);