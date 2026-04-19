"""
Scheduler — runs the full daily pipeline at 5am UTC.

Single job:
  05:00 UTC daily → ingest → filter → cluster → hybrid → score → brief
"""

import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from ingestion.fetcher import fetch_all_sources
from ingestion.storage import upsert_articles
from filtering.filter import run_filtering
from clustering.cluster import run_clustering
from hybrid_clustering.hybrid_cluster import run_hybrid_clustering
from scoring.score import run_scoring
from tagging.tag import run_tagging

logger = logging.getLogger(__name__)


def run_ingestion() -> None:
    """Fetch all sources and store raw articles."""
    logger.info("Ingestion started")
    articles = fetch_all_sources()
    if articles:
        upsert_articles(articles)
    logger.info("Ingestion complete — %d articles fetched", len(articles))


def run_daily_pipeline() -> None:
    """
    Full daily pipeline (always processes yesterday's articles):
      1. Ingest from all sources (stored with today's fetched_at)
      2. Filter yesterday's new articles
      3. Cluster yesterday's assessing articles (Voyage AI)
      4. Hybrid pass — name clusters, assign singletons, form roundups (Claude)
      5. Score yesterday's pending clusters
      Briefing is manual — trigger from the admin UI.
    """
    from datetime import date
    today = date.today().isoformat()

    logger.info("=== Daily pipeline started (processing %s) ===", today)
    run_ingestion()
    run_filtering(run_date=today)
    run_clustering(run_date=today)
    run_hybrid_clustering(run_date=today)
    run_scoring(run_date=today)
    run_tagging(run_date=today)
    logger.info("=== Daily pipeline complete ===")


def start_scheduler() -> None:
    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(
        run_daily_pipeline,
        CronTrigger(hour=5, minute=0, timezone="UTC"),
        id="daily_pipeline",
        replace_existing=True,
    )
    logger.info("Scheduler started — daily pipeline runs at 05:00 UTC")
    scheduler.start()
