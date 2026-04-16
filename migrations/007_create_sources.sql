-- Canonical source registry. The pipeline reads from this table at runtime.
-- To add/edit/disable a source, use the admin UI — no code change needed.

create table if not exists sources (
  id          bigserial   primary key,
  name        text        not null unique,
  url         text,         -- RSS feed URL | NewsAPI query string | Finnhub category key
  category    text        not null,
  source_type text        not null check (source_type in ('rss', 'newsapi', 'finnhub')),
  enabled     boolean     not null default true,
  created_at  timestamptz not null default now()
);

create index if not exists idx_sources_type    on sources (source_type);
create index if not exists idx_sources_enabled on sources (enabled);

-- ── RSS sources ────────────────────────────────────────────────────────────
insert into sources (name, url, category, source_type) values
  ('Reuters Business',             'https://feeds.reuters.com/reuters/businessNews',                 'business', 'rss'),
  ('Reuters Finance',              'https://feeds.reuters.com/reuters/financialsNews',               'finance',  'rss'),
  ('CNBC Finance',                 'https://www.cnbc.com/id/10000664/device/rss/rss.html',           'finance',  'rss'),
  ('CNBC Economy',                 'https://www.cnbc.com/id/20910258/device/rss/rss.html',           'economy',  'rss'),
  ('MarketWatch',                  'https://feeds.marketwatch.com/marketwatch/topstories/',          'markets',  'rss'),
  ('Financial Times',              'https://www.ft.com/?format=rss',                                'finance',  'rss'),
  ('BBC Business',                 'https://feeds.bbci.co.uk/news/business/rss.xml',                'business', 'rss'),
  ('The Economist Finance',        'https://www.economist.com/finance-and-economics/rss.xml',       'finance',  'rss'),
  ('Investing.com News',           'https://www.investing.com/rss/news.rss',                        'markets',  'rss'),
  ('Seeking Alpha',                'https://seekingalpha.com/feed.xml',                             'markets',  'rss'),
  ('TechCrunch',                   'https://techcrunch.com/feed/',                                  'startups', 'rss'),
  ('TechCrunch Startups',          'https://techcrunch.com/category/startups/feed/',                'startups', 'rss'),
  ('Crunchbase News',              'https://news.crunchbase.com/feed/',                             'startups', 'rss'),
  ('VentureBeat',                  'https://venturebeat.com/feed/',                                 'startups', 'rss'),
  ('Renaissance Capital IPO News', 'https://www.renaissancecapital.com/feeds/iponews.xml',          'ipo',      'rss'),
  ('WSJ Markets',                  'https://feeds.a.dj.com/rss/RSSMarketsMain.xml',                 'markets',  'rss'),
  ('WSJ Business',                 'https://feeds.a.dj.com/rss/WSJcomUSBusiness.xml',               'business', 'rss'),
  ('The Economist Business',       'https://www.economist.com/business/rss.xml',                    'business', 'rss'),
  ('Fortune',                      'https://fortune.com/feed/',                                     'business', 'rss'),
  ('Morning Brew',                 'https://www.morningbrew.com/daily/feed.rss',                    'business', 'rss'),
  ('Techpresso',                   'https://techpresso.co/feed',                                    'startups', 'rss')
on conflict (name) do nothing;

-- ── NewsAPI sources (url = search query) ──────────────────────────────────
insert into sources (name, url, category, source_type) values
  ('NewsAPI IPO',      'IPO OR initial public offering',                                     'ipo',      'newsapi'),
  ('NewsAPI Startups', 'startup funding OR venture capital OR series A OR series B',         'startups', 'newsapi'),
  ('NewsAPI Markets',  'financial markets OR stock market OR equities',                      'markets',  'newsapi'),
  ('NewsAPI M&A',      'mergers acquisitions OR M&A',                                        'business', 'newsapi')
on conflict (name) do nothing;

-- ── Finnhub sources (url = category key or 'ipo_calendar') ────────────────
insert into sources (name, url, category, source_type) values
  ('Finnhub General',      'general',      'finance',  'finnhub'),
  ('Finnhub M&A',          'merger',       'business', 'finnhub'),
  ('Finnhub IPO Calendar', 'ipo_calendar', 'ipo',      'finnhub')
on conflict (name) do nothing;
