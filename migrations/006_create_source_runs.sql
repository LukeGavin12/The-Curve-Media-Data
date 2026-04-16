-- Tracks every source fetch attempt per pipeline run.
-- One row per source per run — status 'ok' or 'error'.

create table if not exists source_runs (
  id              bigserial   primary key,
  run_date        date        not null,
  source_name     text        not null,
  source_category text        not null,
  status          text        not null check (status in ('ok', 'error')),
  article_count   integer     not null default 0,
  error_message   text,
  fetched_at      timestamptz not null default now()
);

create index if not exists idx_source_runs_date on source_runs (run_date desc);
create index if not exists idx_source_runs_name on source_runs (source_name);
