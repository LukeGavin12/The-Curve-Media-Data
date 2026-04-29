ALTER TABLE news_articles
  ADD COLUMN IF NOT EXISTS full_text        text,
  ADD COLUMN IF NOT EXISTS word_count       integer,
  ADD COLUMN IF NOT EXISTS scrape_status    text CHECK (scrape_status IN ('scraped','failed','paywalled')),
  ADD COLUMN IF NOT EXISTS scraped_at       timestamptz,
  ADD COLUMN IF NOT EXISTS deep_summary     text,
  ADD COLUMN IF NOT EXISTS key_facts        jsonb,
  ADD COLUMN IF NOT EXISTS relevance_notes  text,
  ADD COLUMN IF NOT EXISTS summarised_at    timestamptz;
