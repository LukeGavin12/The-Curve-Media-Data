"""
Utility: reset all clustering/scoring/briefing data for a given date
so the cluster → hybrid → score → brief stages can be re-run cleanly.

  python -m pipeline.reset_date --date 2026-04-04

What it does:
  - Deletes all story_clusters rows for the date
  - Resets news_articles.status → 'assessing' and clears cluster_id
    for articles fetched on that date that are past the filtering stage
"""

import argparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)

logger = logging.getLogger(__name__)

from pipeline.ingestion.storage import get_client, TABLE

CLUSTERS_TABLE = "story_clusters"


def reset_date(date: str) -> None:
    supabase = get_client()

    # Delete all clusters for the date
    resp = supabase.table(CLUSTERS_TABLE).delete().eq("date", date).execute()
    deleted_clusters = len(resp.data) if resp.data else 0
    logger.info("Deleted %d cluster rows for %s", deleted_clusters, date)

    # Reset articles fetched on that date back to 'assessing'
    resp = supabase.table(TABLE).update({
        "status": "assessing",
        "cluster_id": None,
    }).gte("fetched_at", f"{date}T00:00:00.000Z").lte(
        "fetched_at", f"{date}T23:59:59.999Z"
    ).in_("status", ["accepted", "rejected", "briefed", "published"]).execute()
    reset_articles = len(resp.data) if resp.data else 0
    logger.info("Reset %d articles to 'assessing' for %s", reset_articles, date)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, metavar="YYYY-MM-DD")
    args = parser.parse_args()
    reset_date(args.date)
