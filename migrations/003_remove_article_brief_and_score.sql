-- Remove redundant fields from news_articles.
-- relevance_score lives on story_clusters (single source of truth via cluster_id join).
-- brief is cluster-level, never per-article.

alter table news_articles drop column if exists brief;
alter table news_articles drop column if exists relevance_score;
