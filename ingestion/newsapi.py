"""
NewsAPI fetcher — pulls from newsapi.org/v2/everything filtered to
financial/business/startup topics.
Docs: https://newsapi.org/docs/endpoints/everything
"""

import logging
from datetime import datetime, timezone, timedelta

import httpx

from pipeline.config import NEWSAPI_KEY, MAX_ARTICLES_PER_SOURCE
from pipeline.ingestion.fetcher import _guid
from pipeline.ingestion.storage import get_sources, log_source_run

logger = logging.getLogger(__name__)

BASE_URL = "https://newsapi.org/v2/everything"

# Queries to run — each becomes its own "source" in the articles table
QUERIES = [
    {"q": "IPO OR initial public offering", "label": "NewsAPI IPO", "category": "ipo"},
    {"q": "startup funding OR venture capital OR series A OR series B", "label": "NewsAPI Startups", "category": "startups"},
    {"q": "financial markets OR stock market OR equities", "label": "NewsAPI Markets", "category": "markets"},
    {"q": "mergers acquisitions OR M&A", "label": "NewsAPI M&A", "category": "business"},
]

# Reputable financial domains to filter results
DOMAINS = (
    "reuters.com,bloomberg.com,ft.com,wsj.com,cnbc.com,"
    "techcrunch.com,crunchbase.com,fortune.com,economist.com"
)


def fetch_newsapi() -> list[dict]:
    """Fetch articles from NewsAPI for all configured queries."""
    if not NEWSAPI_KEY:
        logger.warning("NEWSAPI_KEY not set — skipping NewsAPI fetch")
        return []

    all_articles = []
    from_date = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")

    sources = get_sources(source_type="newsapi")
    queries = [{"q": s["url"], "label": s["name"], "category": s["category"]} for s in sources]

    for query in queries:
        try:
            resp = httpx.get(
                BASE_URL,
                params={
                    "q": query["q"],
                    "domains": DOMAINS,
                    "from": from_date,
                    "sortBy": "publishedAt",
                    "pageSize": min(MAX_ARTICLES_PER_SOURCE or 50, 100),
                    "language": "en",
                    "apiKey": NEWSAPI_KEY,
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("NewsAPI query '%s' failed: %s", query["q"], exc)
            log_source_run(query["label"], query["category"], "error", 0, str(exc))
            continue

        for article in data.get("articles", []):
            url = article.get("url", "")
            title = (article.get("title") or "").strip()
            if not url or not title or title == "[Removed]":
                continue

            all_articles.append({
                "guid": _guid(url, title),
                "source_name": query["label"],
                "source_category": query["category"],
                "title": title,
                "url": url,
                "summary": (article.get("description") or "").strip(),
                "author": article.get("author"),
                "image_url": article.get("urlToImage"),
                "published_at": article.get("publishedAt"),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "raw_tags": [],
                "status": "new",
            })

        query_count = len([a for a in all_articles if a["source_name"] == query["label"]])
        log_source_run(query["label"], query["category"], "ok", query_count)
        logger.info("NewsAPI '%s': %d articles", query["label"], query_count)

    return all_articles
