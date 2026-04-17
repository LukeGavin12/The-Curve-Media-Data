-- Add 'included' and 'excluded' to article_status enum.
-- These replace 'assessing' (pass) and 'rejected' (fail) from the filtering stage.

ALTER TYPE article_status ADD VALUE IF NOT EXISTS 'included';
ALTER TYPE article_status ADD VALUE IF NOT EXISTS 'excluded';

-- Backfill existing rows
UPDATE news_articles SET status = 'included' WHERE status = 'assessing';
UPDATE news_articles SET status = 'excluded' WHERE status = 'rejected';
