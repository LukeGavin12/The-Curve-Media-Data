-- Add source_id FK to news_articles.
-- A trigger keeps it in sync with source_name automatically — no pipeline changes needed.

alter table news_articles
  add column if not exists source_id bigint references sources(id);

-- Backfill existing rows
update news_articles a
set source_id = s.id
from sources s
where a.source_name = s.name
  and a.source_id is null;

create index if not exists idx_news_articles_source_id on news_articles (source_id);

-- Trigger: auto-set source_id on every insert or source_name update
create or replace function fn_set_article_source_id()
returns trigger language plpgsql as $$
begin
  new.source_id := (
    select id from sources where name = new.source_name limit 1
  );
  return new;
end;
$$;

drop trigger if exists tr_set_article_source_id on news_articles;

create trigger tr_set_article_source_id
before insert or update of source_name
on news_articles
for each row execute function fn_set_article_source_id();
