ALTER TABLE pipeline_settings
  ADD COLUMN IF NOT EXISTS research_score_threshold numeric NOT NULL DEFAULT 0.60;
