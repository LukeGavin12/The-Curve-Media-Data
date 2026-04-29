"""
Scraper — fetches full article HTML and extracts clean text.

Uses httpx for HTTP and trafilatura for main-content extraction.
Attaches per-source cookie string when available.
"""

import logging
from dataclasses import dataclass
from typing import Optional

import httpx
import trafilatura

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.5",
}

SCRAPE_TIMEOUT = 20
MIN_WORD_COUNT = 150  # below this = paywalled stub or login wall


@dataclass
class ScrapeResult:
    status: str              # "scraped" | "paywalled" | "failed"
    full_text: Optional[str]
    word_count: int
    error: Optional[str]


def scrape_article(url: str, cookie_string: str | None = None) -> ScrapeResult:
    """
    Fetch url and extract main article text.
    cookie_string: raw Cookie header value from sources.cookies.
    Never raises — all errors returned as ScrapeResult(status="failed").
    """
    try:
        headers = {**HEADERS}
        if cookie_string:
            headers["Cookie"] = cookie_string

        with httpx.Client(
            headers=headers,
            timeout=SCRAPE_TIMEOUT,
            follow_redirects=True,
        ) as client:
            resp = client.get(url)
            resp.raise_for_status()
            html = resp.text

        text = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=False,
            no_fallback=False,
        )

        if not text or len(text.split()) < MIN_WORD_COUNT:
            return ScrapeResult(
                status="paywalled",
                full_text=None,
                word_count=0,
                error="Content below minimum threshold — likely paywalled or login wall",
            )

        return ScrapeResult(
            status="scraped",
            full_text=text,
            word_count=len(text.split()),
            error=None,
        )

    except httpx.HTTPStatusError as exc:
        return ScrapeResult(
            status="failed",
            full_text=None,
            word_count=0,
            error=f"HTTP {exc.response.status_code}",
        )
    except Exception as exc:
        return ScrapeResult(
            status="failed",
            full_text=None,
            word_count=0,
            error=str(exc)[:200],
        )
