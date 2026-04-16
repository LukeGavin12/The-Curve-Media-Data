"""
Stage 2 — Filtering.

Picks up all status='new' articles and runs three cheap, fast checks (no LLM).

Checks (in order):
  1. Near-duplicate title detection  — Levenshtein ratio >= 0.85 → reject
  2. Minimum summary length          — < 8 words → reject
  3. Language detection              — non-English → reject

Pass  → status = assessing
Fail  → status = rejected  +  status_reason
"""

import logging
from collections import defaultdict
from typing import Any

from rapidfuzz.distance import Levenshtein
from langdetect import detect, LangDetectException

from ingestion.storage import get_client, TABLE

logger = logging.getLogger(__name__)

MIN_SUMMARY_WORDS = 8
DUPE_RATIO = 0.85   # Levenshtein similarity threshold for near-duplicate titles


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _fetch_new_articles(run_date: str) -> list[dict[str, Any]]:
    """Return status='new' articles fetched on run_date."""
    client = get_client()
    response = (
        client.table(TABLE)
        .select("guid, title, summary")
        .eq("status", "new")
        .gte("fetched_at", f"{run_date}T00:00:00.000Z")
        .lte("fetched_at", f"{run_date}T23:59:59.999Z")
        .execute()
    )
    return response.data or []


_BATCH_SIZE = 50  # keep URL length well within PostgREST limits (GUIDs are 64 chars each)


def _chunked(lst: list, size: int):
    for i in range(0, len(lst), size):
        yield lst[i: i + size]


def _apply_results(passing: list[str], rejections: dict[str, list[str]]) -> None:
    """
    Batch-write results back to Supabase in chunks to stay within URL length limits.
      passing    — list of guids → status = assessing
      rejections — {reason: [guid, ...]} → status = rejected
    """
    client = get_client()

    for chunk in _chunked(passing, _BATCH_SIZE):
        client.table(TABLE).update({"status": "assessing"}).in_("guid", chunk).execute()

    for reason, guids in rejections.items():
        for chunk in _chunked(guids, _BATCH_SIZE):
            client.table(TABLE).update(
                {"status": "rejected", "status_reason": reason}
            ).in_("guid", chunk).execute()


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def _check_summary_length(summary: str | None) -> str | None:
    """Return a rejection reason string, or None if the article passes."""
    if not summary:
        return "No summary"
    word_count = len(summary.split())
    if word_count < MIN_SUMMARY_WORDS:
        return f"Summary too short ({word_count} words, minimum {MIN_SUMMARY_WORDS})"
    return None


def _check_language(title: str, summary: str | None) -> str | None:
    """Return a rejection reason string, or None if the article passes."""
    text = f"{title} {summary or ''}".strip()
    try:
        lang = detect(text)
        if lang != "en":
            return f"Non-English content (detected: {lang})"
    except LangDetectException:
        # Detection failed — let it through rather than silently dropping
        pass
    return None


def _find_near_duplicate_guids(articles: list[dict[str, Any]]) -> set[str]:
    """
    O(n²) pairwise title comparison across the batch.
    Keeps the first occurrence of each near-duplicate cluster; rejects the rest.
    Fine for daily batch sizes (typically a few hundred articles).
    """
    rejected: set[str] = set()
    seen: list[dict] = []  # articles that have 'won' their cluster so far

    for article in articles:
        title = (article.get("title") or "").lower().strip()
        is_dupe = any(
            Levenshtein.normalized_similarity(title, (prior.get("title") or "").lower().strip()) >= DUPE_RATIO
            for prior in seen
        )
        if is_dupe:
            rejected.add(article["guid"])
        else:
            seen.append(article)

    return rejected


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_filtering(run_date: str | None = None) -> None:
    """
    Stage 2 filtering. Run after ingestion, before clustering.

    Transitions:
      new → assessing  (all checks pass)
      new → rejected   (any check fails, reason recorded in status_reason)
    """
    from datetime import date, timedelta
    target_date = run_date or (date.today() - timedelta(days=1)).isoformat()
    logger.info("Filtering started for %s", target_date)

    articles = _fetch_new_articles(target_date)
    if not articles:
        logger.info("Filtering: no new articles to process")
        return

    logger.info("Filtering %d new articles", len(articles))

    # Near-duplicate detection is a batch operation — run once across all articles
    dupe_guids = _find_near_duplicate_guids(articles)

    passing: list[str] = []
    rejections: dict[str, list[str]] = defaultdict(list)

    for article in articles:
        guid = article["guid"]
        title = article.get("title") or ""
        summary = article.get("summary") or ""

        # Check 1 — near-duplicate title
        if guid in dupe_guids:
            rejections["Near-duplicate title"].append(guid)
            continue

        # Check 2 — summary length
        reason = _check_summary_length(summary)
        if reason:
            rejections[reason].append(guid)
            continue

        # Check 3 — language
        reason = _check_language(title, summary)
        if reason:
            rejections[reason].append(guid)
            continue

        passing.append(guid)

    _apply_results(passing, rejections)

    total_rejected = sum(len(v) for v in rejections.values())
    logger.info(
        "Filtering complete -- %d passed (-> assessing), %d rejected",
        len(passing),
        total_rejected,
    )
    for reason, guids in rejections.items():
        logger.info("  Rejected (%s): %d articles", reason, len(guids))
