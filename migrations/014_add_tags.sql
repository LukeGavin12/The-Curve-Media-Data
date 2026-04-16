-- Add topic tags to story clusters
ALTER TABLE story_clusters
  ADD COLUMN IF NOT EXISTS tags text[] NOT NULL DEFAULT '{}';

-- Add geographic tags to story clusters
ALTER TABLE story_clusters
  ADD COLUMN IF NOT EXISTS geo_tags text[] NOT NULL DEFAULT '{}';

-- Add available topic tags list to pipeline settings
ALTER TABLE pipeline_settings
  ADD COLUMN IF NOT EXISTS available_tags text[] NOT NULL DEFAULT '{}';

-- Add available geo tags list to pipeline settings
ALTER TABLE pipeline_settings
  ADD COLUMN IF NOT EXISTS available_geo_tags text[] NOT NULL DEFAULT '{}';

-- Seed default topic tags
UPDATE pipeline_settings
SET available_tags = ARRAY['Markets', 'Companies', 'AI', 'Personal Finance', 'Policy']
WHERE id = 1 AND available_tags = '{}';

-- Seed default geo tags
UPDATE pipeline_settings
SET available_geo_tags = ARRAY['UK', 'US', 'Aus/NZ', 'ROW']
WHERE id = 1 AND available_geo_tags = '{}';
