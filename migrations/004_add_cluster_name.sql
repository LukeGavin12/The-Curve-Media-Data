-- Add a human-readable name to story clusters.
-- Populated at clustering time from the anchor article's title.

alter table story_clusters add column if not exists name text;
