-- Add tags to story clusters
ALTER TABLE story_clusters
  ADD COLUMN IF NOT EXISTS tags text[] NOT NULL DEFAULT '{}';

-- Add available tags list to pipeline settings
ALTER TABLE pipeline_settings
  ADD COLUMN IF NOT EXISTS available_tags text[] NOT NULL DEFAULT '{}';

-- Seed with default tags
UPDATE pipeline_settings
SET available_tags = ARRAY['Markets', 'Companies', 'AI', 'Personal Finance', 'Policy', 'Global']
WHERE id = 1 AND available_tags = '{}';
