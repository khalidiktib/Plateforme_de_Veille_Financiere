-- On renomme score_risque en niveau_impact pour garder l'historique 
ALTER TABLE documents 
RENAME COLUMN score_risque TO niveau_impact;

ALTER TABLE documents 
ADD COLUMN IF NOT EXISTS justification_impact TEXT;