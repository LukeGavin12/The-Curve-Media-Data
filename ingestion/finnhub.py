"""
Finnhub fetcher — pulls general financial news and the IPO calendar.
Docs: https://finnhub.io/docs/api
"""

import logging
from datetime import datetime, timezone, timedelta

import httpx

from config import FINNHUB_KEY, MAX_ARTICLES_PER_SOURCE
from ingestion.fetcher import _guid
from ingestion.storage import get_sources, log_source_run

logger = logging.getLogger(__name__)

BASE_URL = "https://finnhub.io/api/v1"

# Finnhub news categories
NEWS_CATEGORIES = [
    {"category": "general", "label": "Finnhub General", "source_category": "finance"},
    {"category": "merger", "label": "Finnhub M&A", "source_category": "business"},
]


def fetch_finnhub_news(news_sources: list[dict]) -> list[dict]:
    """Fetch news articles from Finnhub for the given source list."""
    if not FINNHUB_KEY:
        logger.warning("FINNHUB_KEY not set — skipping Finnhub news fetch")
        return []

    all_articles = []
    limit = MAX_ARTICLES_PER_SOURCE or 50

    for feed in [{"category": s["url"], "label": s["name"], "source_category": s["category"]} for s in news_sources]:
        try:
            resp = httpx.get(
                f"{BASE_URL}/news",
                params={"category": feed["category"], "token": FINNHUB_KEY},
                timeout=15,
            )
            resp.raise_for_status()
            items = resp.json()
        except Exception as exc:
            logger.warning("Finnhub news category '%s' failed: %s", feed["category"], exc)
            log_source_run(feed["label"], feed["source_category"], "error", 0, str(exc))
            continue

        for item in items[:limit]:
            url = item.get("url", "")
            title = (item.get("headline") or "").strip()
            if not url or not title:
                continue

            published_at = None
            if item.get("datetime"):
                published_at = datetime.fromtimestamp(
                    item["datetime"], tz=timezone.utc
                ).isoformat()

            all_articles.append({
                "guid": _guid(url, title),
                "source_name": feed["label"],
                "source_category": feed["source_category"],
                "title": title,
                "url": url,
                "summary": (item.get("summary") or "").strip(),
                "author": item.get("source"),
                "image_url": item.get("image"),
                "published_at": published_at,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "raw_tags": [item.get("category")] if item.get("category") else [],
                "status": "new",
            })

        feed_count = len([a for a in all_articles if a["source_name"] == feed["label"]])
        log_source_run(feed["label"], feed["source_category"], "ok", feed_count)
        logger.info("Finnhub '%s': %d articles", feed["label"], feed_count)

    return all_articles


def fetch_finnhub_ipo_calendar() -> list[dict]:
    """
    Fetch upcoming and recent IPOs from Finnhub's IPO calendar.
    Returns them as articles so they land in the same table.
    """
    if not FINNHUB_KEY:
        logger.warning("FINNHUB_KEY not set — skipping Finnhub IPO calendar fetch")
        return []

    today = datetime.now(timezone.utc)
    from_date = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    to_date = (today + timedelta(days=30)).strftime("%Y-%m-%d")  # include upcoming IPOs

    try:
        resp = httpx.get(
            f"{BASE_URL}/calendar/ipo",
            params={"from": from_date, "to": to_date, "token": FINNHUB_KEY},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning("Finnhub IPO calendar failed: %s", exc)
        log_source_run("Finnhub IPO Calendar", "ipo", "error", 0, str(exc))
        return []

    articles = []
    for ipo in data.get("ipoCalendar", []):
        company = ipo.get("name", "Unknown")
        symbol = ipo.get("symbol", "")
        date = ipo.get("date", "")
        price = ipo.get("price", "")
        shares = ipo.get("numberOfShares", "")
        exchange = ipo.get("exchange", "")
        status = ipo.get("status", "")

        title = f"IPO: {company} ({symbol}) — {date}"
        url = f"https://finnhub.io/ipo/{symbol or company.replace(' ', '-')}"

        summary_parts = [f"{company} ({symbol}) is scheduled to IPO on {date}"]
        if price:
            summary_parts.append(f"price: ${price}")
        if shares:
            summary_parts.append(f"shares: {int(shares):,}")
        if exchange:
            summary_parts.append(f"exchange: {exchange}")
        if status:
            summary_parts.append(f"status: {status}")

        articles.append({
            "guid": _guid(url, title),
            "source_name": "Finnhub IPO Calendar",
            "source_category": "ipo",
            "title": title,
            "url": url,
            "summary": ", ".join(summary_parts),
            "author": None,
            "image_url": None,
            "published_at": f"{date}T00:00:00+00:00" if date else None,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "raw_tags": ["ipo", symbol, exchange] if symbol else ["ipo"],
            "status": "new",
        })

    logger.info("Finnhub IPO calendar: %d entries", len(articles))
    log_source_run("Finnhub IPO Calendar", "ipo", "ok", len(articles))
    return articles


def fetch_finnhub() -> list[dict]:
    """Fetch all enabled Finnhub sources — news categories + IPO calendar."""
    sources = get_sources(source_type="finnhub")
    news_sources = [s for s in sources if s["url"] != "ipo_calendar"]
    has_ipo_calendar = any(s["url"] == "ipo_calendar" for s in sources)

    articles = fetch_finnhub_news(news_sources)
    if has_ipo_calendar:
        articles += fetch_finnhub_ipo_calendar()
    return articles
