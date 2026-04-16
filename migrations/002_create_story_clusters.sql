-- Run in your Supabase SQL editor after 001_create_news_articles.sql

create type cluster_status as enum (
    'pending',    -- just created, awaiting scoring
    'scoring',    -- scoring in progress
    'accepted',   -- score >= 0.4, ready for brief generation
    'rejected',   -- score < 0.4, not relevant enough
    'briefed',    -- editorial brief has been generated
    'published',  -- brief has been surfaced to users
    'archived'    -- no longer active
);

create table if not exists story_clusters (
    id                bigserial primary key,
    cluster_id        text        not null unique,   -- uuid assigned at clustering time
    date              date        not null,           -- pipeline run date
    anchor_article_id bigint      references news_articles(id),
    article_count     integer     not null default 1,
    relevance_score   numeric,                        -- populated by Stage 4
    score_reason      text,                           -- populated by Stage 4
    brief             text,                           -- populated by Stage 5
    cluster_status    cluster_status not null default 'pending',
    created_at        timestamptz not null default now(),
    briefed_at        timestamptz,
    published_at      timestamptz
);

create index if not exists idx_story_clusters_date          on story_clusters (date desc);
create index if not exists idx_story_clusters_cluster_id    on story_clusters (cluster_id);
create index if not exists idx_story_clusters_status        on story_clusters (cluster_status);
create index if not exists idx_story_clusters_score         on story_clusters (relevance_score desc);
