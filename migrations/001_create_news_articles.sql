-- Run once in your Supabase SQL editor to create the articles table

create type article_status as enum (
    'new',          -- just ingested, not yet assessed
    'assessing',    -- scoring/clustering in progress
    'accepted',     -- passed scoring, included in a story cluster
    'rejected',     -- filtered out (low relevance, duplicate story, etc.)
    'briefed',      -- brief has been generated and is ready
    'published'     -- brief has been surfaced to users
);

create table if not exists news_articles (
    id            bigserial primary key,
    guid          text        not null unique,       -- sha256(url|title) for deduplication
    source_name   text        not null,
    source_category text      not null,
    title         text        not null,
    url           text        not null,
    summary       text,
    author        text,
    image_url     text,
    published_at  timestamptz,
    fetched_at    timestamptz not null default now(),
    raw_tags      text[],
    status        article_status not null default 'new',
    status_reason text,                                    -- optional note on why rejected etc.

    -- Fields populated by later pipeline stages
    relevance_score  numeric,
    cluster_id       text,
    brief            text,
    processed_at     timestamptz
);

create index if not exists idx_news_articles_published_at on news_articles (published_at desc);
create index if not exists idx_news_articles_source      on news_articles (source_name);
create index if not exists idx_news_articles_cluster     on news_articles (cluster_id);
create index if not exists idx_news_articles_status      on news_articles (status);
